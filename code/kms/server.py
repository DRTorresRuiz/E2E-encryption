#!flask/bin/python
from flask import Flask, request, abort, jsonify, make_response
from cryptography.fernet import Fernet
from flask_httpauth import HTTPBasicAuth
import paho.mqtt.client as mqtt
import threading
import click
import time
import json
import os
import sys

sys.path.append('')
import utils

CLIENT_ID               = "kms-muii"
TOPIC_FILE = 'registeredDeviceTopics.json'

topicsPublishNewKeys    = {}
secretRegisteredDevices = {}

app                     = Flask( __name__ )
auth                    = HTTPBasicAuth()
 
class FlaskThread( threading.Thread ):

    @auth.get_password
    def get_password( username ):
        # Ref: https://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask
        # TODO-MAYBE: Token Authentication method (?) https://realpython.com/python-random/#osurandom-about-as-random-as-it-gets
        if username == "platform":

            return "platform-MUII"
        return None
       
    @app.route( '/register-device', methods=['POST'] )
    @auth.login_required
    def register( ):
        global topicsPublishNewKeys

        if not request.json or not 'id' in request.json: abort( 400 )
        
        topicsPublishNewKeys[request.json["id"]] = request.json['key_topic']
        # Save into `registeredDeviceTopics.json` file
        with open( TOPIC_FILE, 'w' ) as file:
            json.dump( topicsPublishNewKeys, file, indent=4 )
        return jsonify( {"key_topics": topicsPublishNewKeys} ), 201
        
    @app.route( '/remove-device', methods=['POST'] )
    @auth.login_required
    def remove( ):
        global topicsPublishNewKeys

        if not request.json or not 'id' in request.json: abort( 400 )
        
        # TODO: Contorl that the id exists.
        del topicsPublishNewKeys[request.json["id"]]
        del secretRegisteredDevices[request.json["id"]]
        # Save into `registeredDeviceTopics.json` file
        with open( TOPIC_FILE, 'w' ) as file:
            json.dump( topicsPublishNewKeys, file, indent=4 )
        return jsonify( {"key_topics": topicsPublishNewKeys} ), 201
        
    @auth.error_handler
    def unauthorized( ):
        return make_response( jsonify( {'error': 'Unauthorized access'} ), 401 )

    @app.errorhandler( 404 )
    def not_found( error ):
        return make_response( jsonify( {'error': 'Not found'} ), 404 )
     
    # TODO: SEPARATE TASKS in routes
    # - [x] Register new device.
    # - [ ] TODO: Send keys to all topics.
    # - [x] Remove devices.
    # - [ ] TODO: Send a specific key to the platform.
    # - [ ] TODO: Send all keys to the platform.
    
    def run( self ):
        app.run()

def on_connect( client, userdata, flags, rc ):

  print( "KMS is ready to work." )
  print( "Connected with result code " + str( rc ) )
  # TODO: Read all devices already connected.

def start_flask():
    # Starting flask thread. RESTful service.
    flaskThread = FlaskThread()
    flaskThread.daemon = True # Need to be a daemon to close it with Ctrl+C
    flaskThread.start()

def load_registered_device_topics():
    # Load from the `registerDeviceTopics.json` file to get the topics
    # where to publish the keys for a device. If the file does not exit, 
    # it will be created.
    if not os.path.exists( TOPIC_FILE ):
        # If file does not exit, it will be created.
        with open( TOPIC_FILE, 'w') as file: file.write("{}") 
    with open( TOPIC_FILE ) as file:
        # Group previous devices registered
        data = json.load( file )
    return data 

@click.group()
def cli():
    pass

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def connect( server, port, user, password ):
    """
        Start KMS. It will start the RESTful at port 5000 and start the Key Rotation process.
    """
    global topicsPublishNewKeys
    global secretRegisteredDevices

    start_flask()  
    # Load the information saved of the registered devices.
    topicsPublishNewKeys = load_registered_device_topics()
    #secretRegisteredDevices = load_registered_device_secrets()
    # Connect to MQTT Server.    
    client = mqtt.Client( client_id=CLIENT_ID )
    client.on_connect = on_connect
    client.username_pw_set( user, password )
    client.connect( server, port, 60 )
    client.loop_start()

    while True:    
        # TODO: Reset keys after a while for each device
        for device, topic in topicsPublishNewKeys.items(): 
            # TODO: For each device, change its key depending on the algorithm requested by the device.



            #fernetKey = utils.simpleFernetGenKey()
            chachaKey = utils.chacha20P1305GenKey()

            print( device, '->', topic )
            new_key = {
                "id": CLIENT_ID,
                "deviceID": device,
                "topic": topic,
                "key": fernetKey.decode("UTF-8") ,
                "protocol": "TEST"
            }

"""             new_key = {
                "id": CLIENT_ID,
                "deviceID": device,
                "topic": topic,
                "key": chachaKey.decode("UTF-8") ,
                "protocol": "TEST"
            } """
            print("key", new_key["key"])
            #encrypted_msg = utils.fernetEncrypt(fernetKey, json.dumps(new_key).encode())
            
            utils.send( client, None, new_key )
        time.sleep( 10 )

if __name__ == '__main__':
  # This main process only include the `connect` command.
  # If you need help to run this command, check: `python server.py connect --help`
  cli.add_command( connect )
  cli()
   