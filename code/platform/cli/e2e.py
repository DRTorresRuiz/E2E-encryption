from cryptography.hazmat.primitives.serialization import PublicFormat, Encoding, load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import dh, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import time as t
import requests
import asyncio
import base64
import click
import json
import os

from sys import path
path.append("../../") # Add path to get utils.py
import utils as utils # Include different common fucntions.

PLATFORM_ID            = "platform-cli-muii"
REGISTRATION_TOPIC     = "register"
REGISTERED_DEVICE_FILE = 'registeredDevices.json'
KMS_SERVER_URL         = "http://127.0.0.1:5000/"

#####
### Parameters used for the registration process
#####
connected              = asyncio.Semaphore(0)   # Semaphore to control the connection with the Device
msg_1                  = False
msg_3                  = False
msg_5                  = False
msg_7                  = False
verificationCode       = ""
connection_failed                   = False
newDevice              = {}
public_key             = ""
private_key            = ""
shared_key             = ""
symmetricAlgorithm     = ""
asymmetricAlgorithm    = ""
encriptor              = None

@click.group()
def cli():
  pass

def add_header_message( message, userdata, topic, msg_number=0 ):
    """
        This functions adds information about the device
        to send it to the platform.
    """
    message["id"]       = PLATFORM_ID
    message["topic"]    = topic
    if msg_number != 0:

        message["msg"]  = msg_number
    return message

def on_registration( client, userdata, msg ):
    """
        Method used for the registration process of a device.
    """
    global connected, connection_failed, newDevice
    global verificationCode
    global msg_1, msg_3, msg_5, msg_7
    global public_key, private_key, shared_key
    global symmetricAlgorithm, asymmetricAlgorithm, encriptor
    message = utils.get_message( str( msg.payload.decode( "utf-8" ) ), encriptor )
    if message != "":
        
        topic = message.get( "topic", "" )
        if topic == REGISTRATION_TOPIC:

            error = message.get( "error", "" )
            if error != "":
                # We have received an error message from a device during registration
                print( "ERROR: ", error )
                connection_failed = True
            # Get the id of the device that sent a message.
            deviceID = message.get( "id", PLATFORM_ID )
            if not connection_failed and deviceID != PLATFORM_ID:
                # If it is different of the platform id, we treat it.
                # We do not want to read our own messages.
                number = int( message.get( "msg", 0 ) )
                if number == 1:
                    # Received message 1 for the registration process       
                    auth = message.get( "auth", "" )
                    if auth != "":

                        g = auth.get( "g", "" )
                        p = auth.get( "p", "" )
                        device_pub_key = auth.get( "public_key", "" )
                        symmetricAlgorithm = auth.get( "symmetric", "" )
                        asymmetricAlgorithm = auth.get( "asymmetric", "" ) 
                        if g != "" and p != "" and device_pub_key != "" and \
                            symmetricAlgorithm != "" and asymmetricAlgorithm != "":
                            # Generate private key and public key for platform in the registration process
                            pn = dh.DHParameterNumbers( p, g )
                            parameters = pn.parameters(default_backend())
                            private_key, public_key = utils.dhGenKeys(parameters)
                            # Generate shared key
                            device_pub_key = utils.load_key( device_pub_key )
                            shared_key = utils.dhGenSharedKey( private_key, device_pub_key )
                            if symmetricAlgorithm == "fernet":

                                encriptor = Fernet( base64.urlsafe_b64encode( shared_key ) )
                            elif symmetricAlgorithm == "chacha":

                                print( "chacha not implemented yet." )
                            # Building message two.
                            answer_registration_request = {
                                "auth": {
                                    "public_key": public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode( "utf-8" )
                                }                        
                            }
                            message = add_header_message( answer_registration_request, userdata, REGISTRATION_TOPIC, 2 )
                            utils.send( client, None, message )
                            msg_1 = True
                    if not msg_1:

                        print( "ERROR: Registration request incomplete." )
                        connection_failed = True
                elif msg_1 and number == 3:
                    # Received a message with the KEY generated + 30, to ensure the
                    # rightful of the device to connect. Send KEY Received + 20.
                    if encriptor != None:
                        
                        keyPlusThirty = shared_key+"30".encode()
                        keyReceived = message.get( "payload", "" )
                        if str( keyPlusThirty ) == keyReceived:

                            key = shared_key+"20".encode()
                            key_confirmation = { "payload": str( key ) }
                            message = add_header_message( key_confirmation, userdata, REGISTRATION_TOPIC, 4 )
                            utils.send( client, encriptor, message )
                            msg_3 = True
                    if not msg_3:
                        
                        print( "ERROR: Keys does not match." )
                        connection_failed = True
                elif msg_3 and number == 5:
                    # If receive confirmation, introduce code and send to device.
                    if encriptor != None:

                        if message.get( "status", "ERROR" ) == "OK":

                            deviceType = message.get( "type", "" )
                            if deviceType != "" and deviceType == "I":
                                
                                verificationCode = str( round( random() * 1000000 ) )
                                print( "Introduce this code into your device: ", str( verificationCode ) )
                            else:

                                code = input( "Enter the code provided by the device: " )
                                code_confirmation = { "code": code }
                                message = add_header_message( code_confirmation, userdata, REGISTRATION_TOPIC, 6 )
                                utils.send( client, encriptor, message )
                            msg_5 = True
                    if not msg_5:
                        
                        print( "ERROR: Code does not match." )
                        connection_failed=True
                elif msg_5 and number == 7:
                    # If Device has input, we will receive a code so we compare it
                    # with the verificationCode obtained before. If it has not input,
                    # we will receive a confimation, and if everything is ok,
                    # we will send the data_topic and key_topic.
                    if encriptor != None:

                        validDevice = False
                        deviceType = message.get( "type", "" )
                        if deviceType != "" and deviceType == "I":

                            if verificationCode == message.get( "code", "" ):

                                validDevice = True
                        else:

                            if message.get( "status", "ERROR" ) == "OK":

                                validDevice = True   
                        if validDevice:
                            
                            data_topic = "data-" + deviceID + "-" + str( round( random() * 1000000 ) )
                            key_topic = "key-" + deviceID + "-" + str( round( random() * 1000000 ) )
                            topic_message = { 
                                "data_topic": data_topic,
                                "key_topic": key_topic
                            }
                            message = add_header_message( topic_message, userdata, REGISTRATION_TOPIC, 8 )
                            utils.send( client, encriptor, message )
                            newDevice = {
                                "id": deviceID,
                                "type": deviceType,
                                "data_topic": data_topic,
                                "key_topic": key_topic,
                                # TODO: Add SHARED_KEY
                            }
                            msg_7 = True
                    if not msg_7:

                        print( "ERROR: Connection failed." )
                        connection_failed = True
                elif msg_7 and number == 9:
                    # We received a confirmation of the topics reception from the device.
                    # TODO: Last verification
                    connected.release()

def connect_MQTT( server, port, user, password, message_handler ):
    """ Connection to MQTT Server."""
    client = mqtt.Client( client_id=PLATFORM_ID )
    client.on_message = message_handler
    client.username_pw_set( user, password )
    client.connect( server, port, 60 )
    client.loop_start()
    return client

def wait_til( flag, time, message ):
    """
        This functions stay awaiting till 
        one of the conditions happen.
    """
    global connection_failed 
    now = datetime.now()
    difference = 0
    print( message )
    while flag.locked() and not connection_failed and difference < time:
        
        difference = ( datetime.now() - now ).total_seconds()

def getRegisteredDevices():

    devices = {}
    if not os.path.exists( REGISTERED_DEVICE_FILE ):
        # If file does not exit, it will be created.
        with open( REGISTERED_DEVICE_FILE, 'w') as file: file.write("{}") 
    with open( REGISTERED_DEVICE_FILE ) as file:
        # Group previous devices registered
        devices = json.load( file )
    return devices

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def register( server, port, user, password ):
    """
        Allow a new device to connect to your platform.
    """
    global connected, newDevice
    client = connect_MQTT( server, port, user, password, on_registration )
    client.subscribe( REGISTRATION_TOPIC ) 
    
    wait_til( connected, 120, "Waiting for connecting..." )
    
    client.unsubscribe( REGISTRATION_TOPIC )
    if not connected.locked():
        
        devices = getRegisteredDevices()
        # Add the new registered device.
        with open( REGISTERED_DEVICE_FILE, 'w' ) as file:
      
            devices[newDevice["id"]] = {
                "data_topic": newDevice["data_topic"] 
                # TODO: Include more information
                # TODO: Include symmetricAlgorithm
            }
            json.dump( devices, file, indent=4 )
        # Registered Devices into KMS
        post_message = {
            # Data information to sent to KMS
            "id": newDevice["id"],
            "key_topic": newDevice["key_topic"]
            # TODO: Include information about algorithms
            # TODO: Include shared KEY to send first key from KMS
        }
        message = requests.post( KMS_SERVER_URL+"register-device", json = post_message, auth=( user, password ) )
        print( "Device successfully added to KMS: ", message.json() )
        print( newDevice.get("id"), " registration completed." )
    else:

        print( "Device registration could not be completed." )

@click.command()
def list_devices():
    """

    """
    filename = 'registeredDevices.json'
    if os.path.exists( filename ):
        with open( filename ) as file:

            data = json.load( file )
            for key, value in data.items():
                print( "Device: ", key, " -> {\n\tData topic: ", value["data_topic"], "\n}" )

def on_message( client, userdata, msg ):
    # Receiving from all topics subscribed.
    # TODO: Ask KMS for Keys.
    print( msg.topic + " " + str( msg.payload ) )

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def connect( server, port, user, password ):
    """

    """
    client = connect_MQTT( server, port, user, password, on_message )
    # Subscribe to all topics included in registeredDevices.json file.
    # TODO: Check if KMS is alive.
    # TODO: If KMS is alive, check if there is any non-registered device in KMS that should be registered and register it in KMS.
    filename = 'registeredDevices.json'
    if os.path.exists( filename ):
        with open( filename ) as file:

            data = json.load( file )
            for key, value in data.items():
                client.subscribe( value["data_topic"] )
    while True:      # Keep Platform listening.
        pass

# - [x] Select and Read from an specific topic / device.
@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-t', '--topic', 'topic', required=True, default="", type=str, help="Introduce the input you want to subscribe." )
def listen_topic( server, port, user, password, topic ):
    """

    """
    client = connect_MQTT( server, port, user, password, on_message )
    if topic != "":

        client.subscribe( topic )
        while True: # Keep Platform listening.
            pass
    else:
        
        print( "No topic selected." )

# - [ ] TODO: Remove devices from list and KMS.
@click.command()
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-i', '--idDevice', 'idDevice', required=True, default="", type=str, help="Introduce the id of the device you want to remove." )
def remove_device( user, password, idDevice ):
    # TODO: Check if the device is registered in both platform and KMS.
    # TODO: Remove device from list
    post_message = {
        # Data information to sent to KMS
        "id": idDevice,
        # TODO: Include information
    }
    message = requests.post( KMS_SERVER_URL+"remove-device", json = post_message, auth=( user, password ) )

if __name__ == '__main__':
    # This main process include the commands for the platform cli.
    # If you need help, run: `python e2e.py --help`
    cli.add_command( connect )
    cli.add_command( listen_topic ) 
    cli.add_command( list_devices )
    cli.add_command( remove_device )
    cli.add_command( register )
    # ADD HERE A NEW COMMNAD.
    cli()