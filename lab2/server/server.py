# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 2
# server/server.py
# Input: Node_ID total_number_of_ID
# Group: 4
# Student: Amanda Sjö & Qing Lin
# ------------------------------------------------------------------------------------------------------

import traceback
import sys
import time
import json
import argparse
import operator
import random
from threading import Thread

from ast import literal_eval

from bottle import Bottle, run, request, template
import requests

OK = 200
BAD_REQUEST = 400
INTERNAL_SERVER_ERROR = 500

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    # Board posts store in a Dictionary
    board = {} 

    node_id = None
    vessel_list = {}

    # Each post entry gets a sequence number
    sequence_number = 1
    #A variable to keep track of the leader id
    leader = 0
    #Variable that stores the random number for the vessel
    random_number = 0
    #Dict that stores all random numbers for all different vessels
    vessel_random_list = {}
    is_leader = False
    #Boolean used to make sure the vessel only sends it´s random number to the neighbour one time
    have_sent_random = False
    #Variable that saves the id for the neighbour
    next_node = None

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # You will probably need to modify them
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id, sequence_number
        success = False
        try:
            #Add new element with the sequence_number to board
            board[int(entry_sequence)] = element
            success = True
            #If the element was added correctly increase the sequence_number.
            sequence_number += 1
        except Exception as e:
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            #try change the element at the entry_sequence place on the board.
            board[int(entry_sequence)] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            #Try delete a entry in board at entry_sequence spot.
            del board[int(entry_sequence)]
            success = True
        except Exception as e:
            print e

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
            if res.status_code == 200:
                success = True
        except Exception as e:
            #If the vessel is disconnected we wan´t to inform the others also. 
            print "Could not contact vessel"
            new_ip = handle_disconnected_vessel(vessel_ip)
            #contact_vessel(new_ip, path, payload, req)
        return success

    def propagate_to_vessels(path, payload=None, req='POST'):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    #Method that contact all other vesseld of a disconnected vessel and handles it.
    def handle_disconnected_vessel(vessel_ip):
        global vessel_list, vessel_random_list

        disconeccted_vessel_id = 0

        #Get the vessel id from the vessel ip in the vessel_list
        for vessel_id, ip in vessel_list.items():
            if str(vessel_ip) == ip:
                disconeccted_vessel_id = vessel_id

        #Remove the vessel from the vessel_list or else it will try contact it when doing propagate_to_all_vessels.
        del vessel_list[str(disconeccted_vessel_id)]

        propagate_to_all_vessels('/vessel_disconnected/{}'.format(disconeccted_vessel_id))
        return vessel_disconnected(disconeccted_vessel_id)

    #Method that creates separete threads when propagating to all other vessels.
    def propagate_to_all_vessels(path, payload=None, req='POST'):

        thread = Thread(target=propagate_to_vessels, args=(path, payload, req))
        thread.daemon = True
        thread.start()

    #Method used to create separate thred when calling on cantact_vessel
    def contact_vessel_thread(vessel_ip, path, payload=None, req='POST'):

        thread = Thread(target=contact_vessel, args=(vessel_ip, path, payload, req))
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
        global board, node_id, leader, random_number, have_sent_random

        #Send it´s random number to neighbours so all can have it. We do this only the first time with the boolean have_sent_random.
        if not have_sent_random:
            entry = str(node_id)+"="+ str(random_number)
            contact_vessel_thread(vessel_list.get(next_node), "/leader_election", entry)
            have_sent_random = True

        if is_leader == True:
            return template('server/boardcontents_template.tpl',board_title='Vessel {} (Leader)'.format(node_id), board_dict=sorted(board.iteritems()))

        else:
            return template('server/boardcontents_template.tpl',board_title='Vessel {} (Not leader)'.format(node_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, node_id, sequence_number, is_leader, leader, vessel_list
        try:
            new_entry = request.forms.get('entry')

            #If the vessel is leader it should tell all to add the entry at the sequence number.
            if is_leader == True:
                #Propagate the new entry to the other vessels.
                propagate_to_all_vessels("/propagate/add/{}".format(sequence_number), {"entry": new_entry})
                add_new_element_to_store(sequence_number, new_entry)

            #If the vessle is not a leader it should inform the leader of the action.
            else:
                contact_vessel_thread(vessel_list.get(str(leader)), '/propagate/add/{}'.format(sequence_number), {"entry": new_entry})

            return True
        except Exception as e:
            print e
        return False

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global is_leader, leader
        try:
            action = request.forms.get("delete")
            entry = request.forms.get('entry')

            if is_leader == True:
                if action == "1":

                    delete_element_from_store(element_id)
                    propagate_to_all_vessels("/propagate/remove/{}".format(element_id))

                else:
                    modify_element_in_store(element_id, entry)
                    propagate_to_all_vessels("/propagate/modify/{}".format(element_id), {"entry": entry})

            if is_leader == False:

                if action == '1':
                    contact_vessel_thread(vessel_list.get(str(leader)), ("/propagate/remove/{}".format(element_id)), {"entry": entry})

                else:
                    contact_vessel_thread(vessel_list.get(str(leader)), ("/propagate/modify/{}".format(element_id)), {"entry": entry})
            
            return True
        except Exception as e:
            print e
        return False

    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        global node_id, is_leader, sequence_number
        try:

            print "Got entry"
            new_entry = request.forms.get('entry')

            #Depending on the action, perform the action.
            if action == "add":
                if is_leader:
                    propagate_to_all_vessels("/propagate/{}/{}".format(action, sequence_number), {"entry": new_entry})
                    add_new_element_to_store(sequence_number, new_entry, True)
                else:

                    add_new_element_to_store(element_id, new_entry, True)

            elif action == "remove":
                delete_element_from_store(element_id, True)
                if is_leader:
                    propagate_to_all_vessels("/propagate/{}/{}".format(action, element_id), {"entry": new_entry})

            elif action == "modify":
                modify_element_in_store(element_id, new_entry, True)
                if is_leader:
                    propagate_to_all_vessels("/propagate/{}/{}".format(action, element_id), {"entry": new_entry})

            return "Success"
        except Exception as e:
            print e
        return "Internal Error"

    #Method that handles the leader election. It will add the new entrys to the vessel_random_list and send new entrys to the
    #neighbour. When it have all entrys it will determine which node is leader by checking which have the largest random number.
    @app.post('/leader_election')
    def leader_recieved():
        global node_id, leader, vessel_random_list, is_leader, vessel_list
        try:
            print "Got leader post"

            #Getting the entry that is in the form 'node_id=random_number'
            random_entry_string = request.body.getvalue()
            entry = random_entry_string.split("=")

            #If the entry node isn´t allready in the list it should add it and also inform the neighbour of the entry.
            if not entry[0] in vessel_random_list:
                vessel_random_list[entry[0]] = entry[1]
                contact_vessel_thread(vessel_list.get(next_node), "/leader_election", random_entry_string)
            
            #When the two lists are the same size it means we have gotten all the vessels random numbers and we can determine the leader.
            if len(vessel_random_list) == len(vessel_list):
                max_number = 0
                for key in vessel_random_list.keys():
                    if(vessel_random_list.get(key) > max_number):
                        max_number = vessel_random_list.get(key)
                        leader = int(key)
                    
                print "The leader node is " + str(leader)
                if leader == node_id:
                    print "Jag är ledare!"
                    is_leader = True

            return "Success"
        except Exception as e:
            print e
        return "Internal Error"

    #Method that is used when a vessel is disconnected. It will remove the vessel from the lists and 
    #also if needed it will determine new neighbour and or leader. 
    @app.post('/vessel_disconnected/<vessel_id>')
    def vessel_disconnected(vessel_id):
        global vessel_random_list, vessel_list, next_node, leader, node_id, is_leader

        #Delete the vessel that have disconnected from lists if it exists.
        if str(vessel_id) in vessel_random_list:
            del vessel_random_list[str(vessel_id)]

        if str(vessel_id) in vessel_list:
            del vessel_list[str(vessel_id)]

    #Check if the disconnected vessel was either neighbour or leader and needs to be replaced.
        if next_node == vessel_id:

            if(len(vessel_list) > 1):
                print vessel_list
                print int(next_node)+1
                if str(int(next_node)+1) in vessel_list.keys():
                    next_node = str(int(next_node)+1)
                else:
                    next_node = '1'

            #In case of the vessel being the only conneted it should not get a new neighbour.
            else:
                print "There is only one node."
                next_node = 0
  
        if int(vessel_id) == int(leader):
            max_number = 0
            for key in vessel_random_list.keys():
                if(vessel_random_list.get(key) > max_number):
                    max_number = vessel_random_list.get(key)
                    leader = int(key)

            print "The new leader is vessel " + str(leader)
            if str(leader) == str(node_id):
                is_leader = True


    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, node_id, app, random_number, vessel_random_list, next_node

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

        #Determine the random number and add it to the vessel_list
        random_number = random.randint(0, 1000)
        print "The random number for the node is " + str(random_number)
        vessel_random_list[str(node_id)] = str(random_number)

        #Figure out neighbour by checking if the next number to the own node id exists in vessel_list.
        #Else the node is the last one and it should have node 1 as neighbour in order to create a ring.
        if str(node_id+1) in vessel_list:
            next_node = str(node_id+1)
        else:
            next_node = '1'

        time.sleep(2)
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