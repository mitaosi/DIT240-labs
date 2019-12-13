# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: John Doe
# ------------------------------------------------------------------------------------------------------
import traceback
import sys
import time
import json
import argparse
import operator
from threading import Thread
from datetime import datetime

from bottle import Bottle, run, request, template
import requests

OK = 200
BAD_REQUEST = 400
INTERNAL_SERVER_ERROR = 500

class Entry(object):
    def __init__(self, action, sequence_number, node_id, time, entry = None, status= None):

        self.action = action
        self.sequence_number = sequence_number
        self.entry = entry
        self.node_id = node_id
        self.time = time
        self.status = status

        #The time_stamp for when it got the latest modify request. 
        self.mod_time = datetime(2000, 1, 1)

        return

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    board = {} 
    entrys_in_board = {}            #Stores all entrys in board with more information in the form of an Entry object. 
    modify_remove_requests = []     #Stores modify/remove actions for entries that haven´t arrived. 

    sequence_number = 1           
    node_id = None
    vessel_list = {}


    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # You will probably need to modify them
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, from_node, time_stamp, is_propagated_call=False):
        global board, sequence_number, entrys_in_board
        success = False
        try:

            #In the case where there allready is a entry at the sequence number, we will compare the two time_stamps for 
            #when the entry was first recieved. In the case where the new entry actuallly should be in front of the old one
            #we try adding the old element at the next spot using add_new_element_to_store. Then we modify the entry at the
            #sequence number to the new value. In the case where the next spot also is occupied the function might call
            #itself a few times until the last value have found a new spot last in the board.  
            if int(entry_sequence) in board.keys():

                old_entry = entrys_in_board[int(entry_sequence)]
                date_new = datetime.strptime(str(time_stamp), '%Y-%m-%d %H:%M:%S.%f')
                date_old = datetime.strptime(str(old_entry.time), '%Y-%m-%d %H:%M:%S.%f')

                #in the case where the new element actually is older
                if date_new < date_old or (date_old == date_new and from_node < old_entry.node_id):

                    add_new_element_to_store(int(entry_sequence)+1, old_entry.entry, old_entry.node_id, old_entry.time, True)
                    modify_element_in_store(int(entry_sequence), element, date_new)

                    #We also wan´t to make sure to change the entry information stored in the entrys_in_board dict when then new
                    #entry took the spot. 
                    entrys_in_board[int(entry_sequence)] = Entry("add", entry_sequence, from_node, time_stamp, element)

                    return

                else:
                    add_new_element_to_store(int(entry_sequence)+1, element, from_node, time_stamp, True)
                    return

            #Lastsly if there is no entry at the given entry_sequence we can just add the new entry. 
            board[int(entry_sequence)] = element
            #We also wan´t to make sure to save the new entry as an Entry object in the dict so we can find
            #the information of the entry later on.
            entrys_in_board[int(entry_sequence)] = Entry("add", entry_sequence, from_node, time_stamp, element)
            success = True
            sequence_number += 1

            print board

        except Exception as e:
            print "Det blev fel vid försök att lägga till något."
            print e
        return success


    def modify_element_in_store(entry_sequence, element, is_propagated_call=False):
        global board
        success = False

        try:
            board[int(entry_sequence)] = element
            success = True
            print "Modified spot: " + str(entry_sequence) + " too: "+ str(element)

        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, entrys_in_board
        success = False

        try:
        	del board[int(entry_sequence)]
        	success = True

        except Exception as e:
            print e

        entrys_in_board[int(entry_sequence)].status = "removed"
        return success

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
                res = 0
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload=None, req='POST'):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            #if int(vessel_id) == 4 and int(node_id) == 1:
                #time.sleep(6)
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    #Method that creates separete threads when propagating to all other vessels.
    def propagate_to_all_vessels(path, payload=None, req='POST'):
        thread = Thread(target=propagate_to_vessels, args=(path, payload, req))
        thread.daemon = True
        thread.start()

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()), members_name_string='Amanda Sjö& Qing Lin')
                                 
    @app.get('/board')
    def get_board():
        global board, node_id
        print board
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        global board, node_id, sequence_number
        try:

            new_entry = request.forms.get('entry')
            time_stamp = datetime.now()

            propagate_to_all_vessels("/propagate/add/{}/{}".format(sequence_number, node_id), {"entry": new_entry, "time": time_stamp })
            handle_action_recieved("add", sequence_number, node_id, new_entry, time_stamp)
     
            return True
        except Exception as e:
            print e
        return False


    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, entrys_in_board
        try:

            print "Recieved action!"
            action = request.forms.get("delete")
            entry = request.forms.get('entry')
            time_stamp = entrys_in_board.get(element_id).time
            node = entrys_in_board.get(element_id).node_id

            if action == "1":

                propagate_to_all_vessels("/propagate/remove/{}/{}".format(element_id, node), {"time": time_stamp})
                handle_action_recieved("remove", element_id, node, entry, time_stamp)

            else:
                mod_time = datetime.now()
                propagate_to_all_vessels("/propagate/modify/{}/{}".format(element_id, node), {"entry": entry, "time": time_stamp, "time_stamp" : mod_time})
                handle_action_recieved("modify", element_id, node, entry, time_stamp, mod_time)
                
            return True
        except Exception as e:
            print e
        return False

    @app.post('/propagate/<action>/<element_id>/<node_id>')
    def propagation_received(action, element_id, node_id):
        try: 

            entry_msg = request.forms.get("entry")
            time = request.forms.get("time")
            mod_time = False

            if action == "modify":
                mod_time = request.forms.get("time_stamp")

            handle_action_recieved(action, element_id, node_id, entry_msg, time, mod_time)

            return "Success"
        except Exception as e:
            print "Det blev fel vid den här grejen!"
            print e
        return "Internal Error"

    def handle_action_recieved(action, element_id, node_id, entry_msg, time_stamp, mod_time = False):
        global  modify_remove_requests, board, entrys_in_board
        try:

            if action == "add":
                #First we need to check if there is old modify/delete requests waiting for the new add request. 
                if modify_remove_requests:
                    print "Finns modify eller remove request kvar"
                    for entry in modify_remove_requests:
                        if str(entry.time) == str(time_stamp) and int(entry.node_id) == int(node_id):
                            print "hittade rätt!"
                            if entry.action == 'remove':
                                modify_remove_requests.remove(entry)
                                print modify_remove_requests
                                entrys_in_board[int(entry.sequence_number)] = Entry("add", entry.sequence_number, entry.node_id, time_stamp, entry_msg, "removed")
                                print "removed new entry"
                                return

                            elif entry.action == 'modify':
                                add_new_element_to_store(element_id, entry.entry, node_id, time_stamp)
                                print "added modified entry"
                                return

                #If no request was concerning the new or there where no old requests we can just try add the new entry.
                add_new_element_to_store( int(element_id), entry_msg, node_id, time_stamp, True)

            #In the case where we got remove/modify request but there is no matching entry in board, we will add
            #the request to the waiting list. 
            elif (action == "remove" or action == "modify"):

                print node_id
                print time_stamp
                for entries in entrys_in_board.values():

                    print entries.node_id
                    print entries.time
                    if int(entries.node_id) == int(node_id) and str(entries.time) == str(time_stamp): 

                        print "found a match"

                        if action == "remove" and not entries.status == "removed":
                            delete_element_from_store(entries.sequence_number, True)
                            return

                        elif action == "modify" and not entries.status == "removed":
                            mod_time = datetime.strptime(str(mod_time), '%Y-%m-%d %H:%M:%S.%f')
                            #entry_time = datetime.strptime(str(entries.mod_time), '%Y-%m-%d %H:%M:%S.%f')

                            if entries.mod_time < mod_time:
                                modify_element_in_store(entries.sequence_number, entry_msg, True)
                                entrys_in_board[int(entries.sequence_number)].mod_time = mod_time
                                entrys_in_board[int(entries.sequence_number)].entry = entry_msg
                                return

                        print "Elementet har redan tagits bort!"
                        return

                print "Sequence_number is not in board"
                modify_remove_requests.append(Entry(action, element_id, node_id, time_stamp, entry_msg))
            
            return "Success"
        except Exception as e:
            print "Det blev fel vid den här grejen!"
            print e
        return "Internal Error"


    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, node_id, app

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

        try:
            run(app, host=vessel_list[str(node_id)], port=port)
        except Exception as e:
            print e
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)