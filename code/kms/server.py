#!flask/bin/python
from flask import Flask, request, abort, jsonify, make_response
from chacha20poly1305 import ChaCha20Poly1305
from flask_httpauth import HTTPBasicAuth
from cryptography.fernet import Fernet
import paho.mqtt.client as mqtt
from datetime import datetime
import threading
import hashlib
import base64
import click
import time
import json
import hmac
import os
import sys

from sys import path
path.append( "../" ) # Add path to get utils.py
import utils as utils # Include different common fucntions.

KMS_ID                  = "kms-muii"
TOPIC_FILE              = 'registeredDeviceTopics.json'
SECRET_FILE             = 'secrets.json'
HASH_KEY                = b'kkpo-kktua'

topicsPublishNewKeys    = {}
secretRegisteredDevices = {}

app                     = Flask( __name__ )
auth                    = HTTPBasicAuth()
 
class FlaskThread( threading.Thread ):

    @auth.get_password
    def get_password( username ):
        """
            Provides the password for an user by a given username.
            Authentication method.
            Reference: 
            https://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask
        """
        if username == "platform":

            return "platform-MUII"
        return None
       
    @app.route( '/register-device', methods=['POST'] )
    @auth.login_required
    def register( ):
        """
            Registers a new device into the KMS according
            to the JSON provided by the platform.
        """
        global topicsPublishNewKeys, secretRegisteredDevices
        if not request.json or not 'id' in request.json or \
        not 'key_topic' in request.json or \
        not 'shared_key' in request.json or \
        not 'symmetric' in request.json: 
            
            abort( 400 )
        topicsPublishNewKeys[request.json["id"]] = request.json['key_topic']
        secretRegisteredDevices[request.json["id"]] = {
            "secrets": {
                "0": request.json["shared_key"]
            },
            "symmetric": request.json["symmetric"]
        }
        # Save into `registeredDeviceTopics.json` file
        with open( TOPIC_FILE, 'w' ) as file:

            json.dump( topicsPublishNewKeys, file, indent=4 )
        # Save into `secret.json` file
        with open( SECRET_FILE, 'w' ) as file:
            json.dump( secretRegisteredDevices, file, indent=4 )
        return jsonify( { "status": "OK" } ), 201
        
    @app.route( '/remove-device', methods=['POST'] )
    @auth.login_required
    def remove( ):
        """
            Removes a device from the KMS according to the given ID.
        """
        global topicsPublishNewKeys, secretRegisteredDevices
        if not request.json or not 'id' in request.json: 
            
            abort( 400 )
        # Delete from both dictionaries.
        del topicsPublishNewKeys[request.json["id"]]
        del secretRegisteredDevices[request.json["id"]]
        # Save into `registeredDeviceTopics.json` file
        with open( TOPIC_FILE, 'w' ) as file:

            json.dump( topicsPublishNewKeys, file, indent=4 )
        # Save into `secret.json` file
        with open( SECRET_FILE, 'w' ) as file:

            json.dump( secretRegisteredDevices, file, indent=4 )
        return jsonify( { "status": "OK" } ), 201
    
    @app.route( '/get-key', methods=['POST'] )
    @auth.login_required
    def get_key( ):
        """
            Returns the keys for an specified ID.
        """
        global secretRegisteredDevices
        if not request.json or not 'id' in request.json:
            
            abort( 400 )
        return jsonify( secretRegisteredDevices[request.json["id"]] ), 201

    @app.route( '/get-all-keys', methods=['POST'] )
    @auth.login_required
    def get_all_keys( ):
        """
            Returns all keys for all devices.
        """
        global secretRegisteredDevices
        return jsonify( secretRegisteredDevices ), 201

    @auth.error_handler
    def unauthorized( ):
        
        return make_response( jsonify( { 'error': 'Unauthorized access' } ), 401 )

    @app.errorhandler( 404 )
    def not_found( error ):

        return make_response( jsonify( { 'error': 'Not found' } ), 404 )
     
    def run( self ):
        
        app.run()

def add_header_message( message, topic ):
    """
        This functions adds information about the device
        to send it to the platform. It also include 
        a hash as a sign.
    """
    message["id"]       = KMS_ID
    message["topic"]    = topic
    message["timestamp"]= str( datetime.now() )
    header = {
        "id": KMS_ID,
        "topic": topic,
        "timestamp": message["timestamp"]
    }
    message["sign"] = hmac.new( HASH_KEY, json.dumps( header ).encode(), \
        hashlib.sha384 ).hexdigest()
    return message

def start_flask():
    """
        Starting flask thread. RESTful service.
    """
    flaskThread = FlaskThread()
    # Need to be a daemon to close it with Ctrl+C
    flaskThread.daemon = True 
    flaskThread.start()

def load_registered_device_topics():
    """ 
        Load from the `registerDeviceTopics.json` file to get the topics
        where to publish the keys for a device. If the file does not exit, 
        it will be created. 
    """
    if not os.path.exists( TOPIC_FILE ):
        # If file does not exit, it will be created.
        with open( TOPIC_FILE, 'w') as file: 
            
            file.write("{}") 
    with open( TOPIC_FILE ) as file:
        # Group previous devices registered
        data = json.load( file )
    return data 

def load_registered_device_secrets():
    """
        Load from the `secrets.json` file to get the topics
        where to publish the keys for a device. If the file does not exit, 
        it will be created.
    """
    if not os.path.exists( SECRET_FILE ):
        # If file does not exit, it will be created.
        with open( SECRET_FILE, 'w') as file: 
            
            file.write("{}") 
    with open( SECRET_FILE ) as file:
        # Group previous devices registered
        data = json.load( file )
    return data 

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, \
    show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, \
    show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, \
    help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, \
    prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve.\
    If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-t', '--time', 't', required=True, type=int, default=10, \
    help=" Time taken to send new keys." )
def connect( server, port, user, password, t ):
    """
        Start KMS. It will start the RESTful at port 5000 and start the Key Rotation process.
    """
    global topicsPublishNewKeys
    global secretRegisteredDevices
    # Initiate Flask as a new thread.
    start_flask() 
    # Load the information saved of the registered devices.
    topicsPublishNewKeys = load_registered_device_topics()
    secretRegisteredDevices = load_registered_device_secrets()
    # Connect to MQTT Server.    
    client = mqtt.Client( client_id=KMS_ID )
    client.username_pw_set( user, password )
    client.connect( server, port, 60 )
    client.loop_start()
    while True:    
        # Start key rotation process. Send a new key for each device according to
        # its symmetric algorithm specified.
        for device, topic in topicsPublishNewKeys.items(): 

            device_keys = secretRegisteredDevices[device]["secrets"]
            old_key = device_keys.get( "0", "" )
            if old_key != "":
                # Generates a new key
                if secretRegisteredDevices[device]["symmetric"] == "fernet":
                    
                    new_key = Fernet.generate_key().decode( "utf-8" ) 
                elif secretRegisteredDevices[device]["symmetric"] == "chacha":

                    new_key = os.urandom( 32 ).decode( "latin-1" )
                if new_key != "":
                    # Rotate keys. Discard the oldest key.
                    if device_keys.get( "1", "" ) != "":
                        
                        old_key = device_keys.get( "1" )
                        secretRegisteredDevices[device]["secrets"]["0"] = old_key
                    secretRegisteredDevices[device]["secrets"]["1"] = new_key
                    if secretRegisteredDevices[device]["symmetric"] == "fernet":
                        
                        encriptor = Fernet( old_key.encode() )
                    elif secretRegisteredDevices[device]["symmetric"] == "chacha":

                        encriptor = ChaCha20Poly1305( old_key.encode( "latin-1" ) )
                    # Send the new generated key to the device
                    secret_message = {
                        "deviceID": device,
                        "key": new_key
                    }
                    message = add_header_message( secret_message, topic )
                    utils.send( client, encriptor, message )
            else:

                print( "Device: ", device, " has not a first key. \
                    Remove it from list and connect it again.")
        
        # Save all changes into the `secret.json` file
        with open( SECRET_FILE, 'w' ) as file:

            json.dump( secretRegisteredDevices, file, indent=4 )
        time.sleep( t )

@click.group()
def cli():
    
    pass

if __name__ == '__main__':
    """
        This main process only include the `connect` command.
        If you need help to run this command, check: `python server.py connect --help`
    """
    cli.add_command( connect )
    cli()
   