from cryptography.fernet import Fernet
import asyncio
import json
import threading
import time as t
from datetime import datetime
from random import random

import click
import paho.mqtt.client as mqtt
import sys

sys.path.append('')
import utils

# Topic used to connect to the platform through the MQTT Server.
REGISTRATION_TOPIC = "register" 

symetric_key       = ""                    # Symetric Key used for encryption
data_topic         = ""                    # Topic used to send values from sensors.
key_topic          = ""                    # Topic used to receives values from KMS.
connected          = asyncio.Semaphore(0)  # Semaphore to control the connection with the Platform
verificationCode   = "000000"              # Only valid for noIO Devices
codeIntroduced     = False
fail               = False

@click.group()
def cli():
  pass

def send( client, msg ):
    # This function sends a message to an specified topic.
    # Returns True if message was sent correctly, otherwise False. 
    # The `msg` need to include the `topic` parameter.
    topic = msg.get("topic", "")
    if topic != "":

        client.publish( topic, json.dumps( msg ) )
        return True
    else:

        print( "The following message couldn't be sent: ", msg )
        return False

def on_connect( client, userdata, flags, rc ):
    # Once connected to the MQTT Server, this device sends 
    # a registration request through the REGISTRATION_TOPIC.
    # And, subscribe to this topic to start the registration process.
    registration_request = {
        # This message starts the registration process.
        "id": userdata["id"],
        "type": userdata["type"],
        "topic": REGISTRATION_TOPIC,
        "msg": 1 # This is the first message of the registration process.
        # TODO: Add another information for the registration process.
    }
    client.subscribe( REGISTRATION_TOPIC ) 
    send( client, registration_request ) # Send the registration request.
    # TODO: Persistence of the connection.

def introduceCode( client, userdata ):

    code = input( "Enter the code provided by the platform: " )
    key_confirmation = {
        "id": userdata["id"],
        "type": userdata["type"],
        "topic": REGISTRATION_TOPIC,
        "msg": 7, 
        "code": code
        # TODO: Add another information for the registration process.
    }
    send( client, key_confirmation ) 

def on_registration( client, userdata, json_message ):
    global connected, verificationCode, data_topic, key_topic, fail

    number = int( json_message.get( "msg", 0 ) )
    deviceType = userdata["type"]
    if number == 2:
        # Receive message with information to build the key.
        # Send KEY + 30 to confirm.
        key_confirmation = {
            "id": userdata["id"],
            "type": deviceType,
            "topic": REGISTRATION_TOPIC,
            "msg": 3,
            "key": "Hey, I am a key" # TODO: Implement
            # TODO: Add another information for the registration process.
        }
        #print( json_message )
        send( client, key_confirmation )
    if number == 4:
        # Send confirmation of the key
        key_confirmation = {
            "id": userdata["id"],
            "type": deviceType,
            "topic": REGISTRATION_TOPIC,
            "msg": 5
            # TODO: Add another information for the registration process.
        }
        send( client, key_confirmation )
        #print( json_message )
        # Now, depending of the type of device we do...
        if deviceType == "O":
            # Generate an verificationCode
            verificationCode = str( round( random() * 1000000 ) )
            print( "Introduce this code into your device: ", str( verificationCode ) )
        elif deviceType == "I":
            # Introduce the code provided by the platform and send it.
            introduceCodeThread = threading.Thread(target=introduceCode, args=[client, userdata])
            introduceCodeThread.start()                   
    if number == 6 and deviceType != "I":

        if verificationCode == json_message.get( "code", "" ):
            #print( json_message )    
            # Send confirmation of the key
            code_confirmation = {
                "id": userdata["id"],
                "type": userdata["type"],
                "topic": REGISTRATION_TOPIC,
                "msg": 7,
                "status": "OK"
                # TODO: Add another information for the registration process.
            }
            send( client, code_confirmation )    
        else:
            
            error = {
                "id": userdata["id"],
                "type": userdata["type"],
                "topic": REGISTRATION_TOPIC,
                "msg": 7,
                "status": "ERROR"
                # TODO: Add another information for the registration process.
            }
            send( client, error )
            print( "Verification code does not match." )
            fail = True

        #print( json_message )
    if number == 8:

        data_topic = json_message.get( "data_topic", "" )
        key_topic = json_message.get( "key_topic", "" )
        if data_topic != "" and key_topic != "":
            # Send confirmation of the key
            code_confirmation = {
                "id": userdata["id"],
                "type": userdata["type"],
                "topic": REGISTRATION_TOPIC,
                "msg": 9
                # TODO: Add another information for the registration process.
            }
            send( client, code_confirmation )
            client.subscribe( key_topic ) # Start subscription to KMS
        else:
            print( "Connection failed." )
            fail = True

        #print( json_message )

        client.unsubscribe( REGISTRATION_TOPIC )
        connected.release()

def on_secure( client, userdata, json_message ):
    global symetric_key
    
    #decrypted_json_message = utils.fernetDecrypt(symetric_key, json_message)
    symetric_key = json_message["key"]  
    print("symetric_key",symetric_key)
    print( "Managing new keys received, ", json_message )

def on_message( client, userdata, msg ):
    # This function receives different messages from topics to which this device
    # is subscribed. 
    global data_topic, key_topic

    # The message received is loaded as a dictionary by using json library.
    message = json.loads( str( msg.payload.decode( "utf-8" ) ) )
    deviceID = message.get( "id", userdata["id"] ) # Get the id of the device that sent a message.
    if deviceID != userdata["id"]: # If it is different of the id of this device, we treat it.
        
        topic = message.get( "topic", "" )
        if topic == REGISTRATION_TOPIC:

            on_registration( client, userdata, message )
        elif key_topic != "" and topic == key_topic:
            on_secure( client, userdata, message ) 

def connect_MQTT( userdata, serverinfo ):
    # Connection to MQTT Server.
    client = mqtt.Client( client_id=userdata["id"], userdata=userdata )  
    client.on_message = on_message
    client.on_connect = on_connect
    client.username_pw_set( serverinfo["username"], serverinfo["password"] )
    client.connect( serverinfo["server"], serverinfo["port"], 60 )
    client.loop_start()
    return client

def wait_til( flag, time ):
    
    now = datetime.now()
    difference = 0
    print( "Waiting for connecting..." )
    while flag.locked() and not fail and difference < time:
        
        difference = ( datetime.now() - now ).total_seconds()

def send_data( client, userdata ):

    global symetric_key
    
    new_message = {
        "id": userdata["id"],
        "type": userdata["type"],
        "topic": data_topic,
        "values": {
            "sensor1": random(),
            "sensor2": random()
        }
        # TODO: Add another information for the registration process.
    }

    if symetric_key != "":
        if userdata["symmetric"] == "fernet": 
            utils.send(client, Fernet(symetric_key), new_message) 
        elif userdata["symmetric"] == 'chacha': 
            print("chacha")
            #utils.send(client, symetric_key, new_message, header) 


    print( "[", datetime.now() ,"] Value sent: ", new_message )
    #send( client, new_message )


@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send data." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send data." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-t', '--device-type', 'typeDevice', type=click.Choice(['noIO','I','O']), default="noIO", help="The type of the device. Your choice will affect the way your device connects to the platform. noIO - without any entrance nor output; I - with one keyboard input available; O - the O letter indicates a device with one display." )
@click.option( '-i', '--identification', 'idDevice', type=str, default="", help="The Device ID you want to use. If not specified, it will be generated randomly." )
@click.option( '-T', '--time', 'time', type=int, default=10, show_default=True, help="Time passed to send new data from device to platform." )
@click.option( '-c', '--symmetric', 'symmetricAlgorithm', type=click.Choice(['fernet', 'chacha']), default="fernet", help="The symmetric algorithm used to send the data to platform.")
@click.option( '-a', '--asymmetric', 'asymmetricAlgorithm', type=click.Choice(['dh', 'ecdh']), default="dh", help="The asymmetric algorithm used to establish the communication.")
def start( server, port, user, password, typeDevice, idDevice, time, symmetricAlgorithm, asymmetricAlgorithm ):
    """
        Start an IoT device and connect it to the platform.
    """
    global connected

    # Group data received    
    userdata = {
        # Data information about the Device
        "id": idDevice if idDevice != "" else "device-" + str( round( random() * 1000000 ) ),
        "type": typeDevice,
        "symmetric": symmetricAlgorithm,
        "asymmetric": asymmetricAlgorithm
    }
    serverinfo = {
        # Information to connect to the MQTT Server
        "username": user,
        "password": password,
        "server": server,
        "port": port
    }
    client = connect_MQTT( userdata, serverinfo )
    # Wait until connection established with the platform
    # TODO: Device Persistence
    wait_til( connected, 120 ) # Wait 2 minutes for connecting...
    
    while not connected.locked():
        # If connected, send new data.
        if data_topic != "":

            send_data( client, userdata )
        t.sleep(time)
    # If not connected, close the process.
    print( "This device is not connected. Ending process." )

if __name__ == '__main__':
    # This main process only include the `connect` command.
    # If you need help to run this command, check: `python device.py connect --help`
    cli.add_command( start )
    # Add here a new command for devices.
    cli()
