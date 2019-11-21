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
from threading import Thread
from random import randint

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

    # Each post entry gets a sequence number
    new_id = 1
    node_id = None
    vessel_list = {}

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # You will probably need to modify them
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id
        success = False
        try:
            board[entry_sequence] = element
            success = True
        except Exception as e:
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call=False):
        global board, node_id
        success = False

        print "The modified entry is " + str(modified_element)
        try:
            board[int(entry_sequence)] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call=False):
        global board, node_id
        success = False

        print "Delete!!"
        try:
            del board[int(entry_sequence)]
            # board.pop(entry_sequence)
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
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload=None, req='POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

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
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()), members_name_string='Amanda Sjö & Qing Lin')
                                 
    @app.get('/board')
    def get_board():
        global board, node_id
        print (board)
        return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, node_id, new_id
        try:
            new_entry = request.forms.get('entry')
            add_new_element_to_store(new_id, new_entry):
            # When a new entry has been added to the current board,the other vessels 
            # need to be informed as well
            propagate_to_all_vessels("/propagate/add/{}".format(new_id), {"entry": new_entry})
            new_id += 1
            # you might want to change None here
            # you should propagate something
            # Please use threads to avoid blocking
            # thread = Thread(target=???,args=???)
            # For example: thread = Thread(target=propagate_to_vessels, args=....)
            # you should create the thread as a deamon with thread.daemon = True
            # then call thread.start() to spawn the thread
            return True
        except Exception as e:
            print e
        return False

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        # Receive an action to perform to the board
        try:
            action = request.forms.get('action')
            entry = request.forms.get("entry")

            print "Action is: " + str(action)
            print entry

            # 1 to delete;0 to modify
            if action == "1":
                print "Deleting element " + str(element_id) + " " + str(entry)
            	delete_element_from_store(element_id)
                propagate_to_all_vessels("/propagate/remove/{}".format(element_id))

            elif action == "0":
            	modify_element_in_store(element_id, entry)
                propagate_to_all_vessels("/propagate/modify/{}".format(element_id), {"entry": entry})
                
            return True
        except Exception as e:
            print e
        return False

    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        global new_id
        try: 
            new_entry = request.body.getvalue()
            print "The action performed is " + str(action)
            print "Element_id " + str(element_id)

            if action == "add":
                add_new_element_to_store(element_id, new_entry, True)
                new_id = element_id + 1

            elif action == "remove":
            	print "removing element with id " + str(element_id)
                delete_element_from_store(element_id, True)

            elif action == "modify":
                modified_entry = request.body.getvalue("entry")
                modify_element_in_store(element_id, modified_entry, True) 
            return "Success"
        except Exception as e:
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
        for i in range(1, args.nbv):
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