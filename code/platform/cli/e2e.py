from cryptography.fernet import Fernet
import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import time as t
import requests
import asyncio
import click
import json
import os

PLATFORM_ID            = "platform-cli-muii"
REGISTRATION_TOPIC     = "register"
REGISTERED_DEVICE_FILE = 'registeredDevices.json'
KMS_SERVER_URL = "http://127.0.0.1:5000/"

connected              = asyncio.Semaphore(0)   # Semaphore to control the connection with the Device
msg_1                  = False
msg_3                  = False
msg_5                  = False
msg_7                  = False
verificationCode       = ""
fail                   = False
newDevice              = {}

@click.group()
def cli():
  pass

def send( client, msg ):
    # This function sends a message to an specified topic.
    # Returns True if message was sent correctly, otherwise False. 
    # The `msg` need to include the `topic` parameter.
    topic = msg.get( "topic", "" )
    if topic != "":

        client.publish( topic, json.dumps( msg ) )
        return True
    else:

        print( "The following message couldn't be sent: ", msg )
        return False

def on_registration( client, userdata, msg ):
    # Method used to registration process of a device.
    global connected, fail, newDevice
    global verificationCode
    global msg_1, msg_3, msg_5, msg_7

    # The message received is loaded as a dictionary by using json library.
    message = json.loads( str( msg.payload.decode( "utf-8" ) ) )
    deviceID = message.get( "id", PLATFORM_ID ) # Get the id of the device that sent a message.
    if deviceID != PLATFORM_ID: # If it is different of the platform id, we treat it.

        topic = message.get( "topic", "" )
        if topic == REGISTRATION_TOPIC:

            number = int( message.get( "msg", 0 ) )
            if number == 1:
                # Received message 1 for the registration process
                # Building message two.
                answer_registration_request = {
                    "id": PLATFORM_ID,
                    "topic": REGISTRATION_TOPIC,
                    "msg": 2
                    # TODO: Add another information for the registration process.
                }
                #print( message )
                send( client, answer_registration_request )
                msg_1 = True
            elif msg_1 and number == 3:
                # Received a message with the KEY generated + 30, to ensure the
                # rightful of the device to connect. Send KEY Received + 20.
                key_confirmation = {
                    "id": PLATFORM_ID,
                    "topic": REGISTRATION_TOPIC,
                    "msg": 4,
                    "key": "Hey, I am a key" # TODO: Implement
                    # TODO: Add another information for the registration process.
                }
                send( client, key_confirmation )
                #print( message )
                msg_3 = True
            elif msg_3 and number == 5:
                # If receive confirmation, introduce code and send to device.
                # TODO: Check for valid confirmation.
                #print( message )
                deviceType = message.get( "type", "" )
                if deviceType != "" and deviceType == "I":
                    
                    verificationCode = str( round( random() * 1000000 ) )
                    print( "Introduce this code into your device: ", str( verificationCode ) )
                else:

                    code = input( "Enter the code provided by the device: " )
                    key_confirmation = {
                        "id": PLATFORM_ID,
                        "topic": REGISTRATION_TOPIC,
                        "msg": 6,
                        "code": code
                        # TODO: Add another information for the registration process.
                    }
                    send( client, key_confirmation )
                msg_5 = True
            elif msg_5 and number == 7:
                # If Device has input, we will receive a code so we compare it
                # with the verificationCode obtained before. If it has not input,
                # we will receive a confimation, and if everything is ok,
                # we will send the data_topic and key_topic.
                validDevice = False
                deviceType = message.get( "type", "" )
                if deviceType != "" and deviceType == "I":
                    
                    if verificationCode == message.get( "code", "" ):

                        validDevice = True
                else:
                    
                    if message.get( "status", "ERROR" ) == "OK":

                        validDevice = True
                        
                if validDevice:

                    topic_message = {
                        "id": PLATFORM_ID,
                        "topic": REGISTRATION_TOPIC,
                        "msg": 8,
                        "data_topic": "data-" + deviceID + "-" + str( round( random() * 1000000 ) ),
                        "key_topic": "key-" + deviceID + "-" + str( round( random() * 1000000 ) )
                        # TODO: Add another information for the registration process.
                    }
                    newDevice = {
                        "id": deviceID,
                        "type": deviceType,
                        "data_topic": topic_message["data_topic"],
                        "key_topic": topic_message["key_topic"],
                    }
                    send( client, topic_message )
                    msg_7 = True
                else:
                    fail = True
                    print( "Connection failed." )
                #print( message )
            elif msg_7 and number == 9:
                # We received a confirmation of the topics reception.
                # print( message )
                connected.release()

def connect_MQTT( server, port, user, password, message_handler ):
    # Make the connection to the MQTT Server.
    client = mqtt.Client( client_id=PLATFORM_ID )
    client.on_message = message_handler
    client.username_pw_set( user, password )
    client.connect( server, port, 60 )
    client.loop_start()
    return client

def wait_til( flag, time ):
    global fail

    now = datetime.now()
    difference = 0
    print( "Waiting for connecting..." )
    while flag.locked() and not fail and difference < time:

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
    
    wait_til( connected, 120 )
    
    client.unsubscribe( REGISTRATION_TOPIC )
    if not connected.locked():
        
        devices = getRegisteredDevices()
        # Add the new registered device.
        with open( REGISTERED_DEVICE_FILE, 'w' ) as file:
      
            devices[newDevice["id"]] = {
                "data_topic": newDevice["data_topic"] 
                # TODO: Include more information
            }
            json.dump( devices, file, indent=4 )

        # Registered Devices into KMS
        post_message = {
            # Data information to sent to KMS
            "id": newDevice["id"],
            "key_topic": newDevice["key_topic"]
            # TODO: Include information about algorithms
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
    # Add here a new command for devices.
    cli()