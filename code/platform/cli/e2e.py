from cryptography.hazmat.primitives.serialization import PublicFormat, \
    Encoding, load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import dh, rsa
from cryptography.hazmat.backends import default_backend
from chacha20poly1305 import ChaCha20Poly1305
from cryptography.fernet import Fernet
import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import tinyec.ec as ec
import time as t
import requests
import asyncio
import hashlib
import base64
import click
import hmac
import json
import os
import re

from sys import path
path.append("../../") # Add path to get utils.py
import utils as utils # Include different common fucntions.

PLATFORM_ID            = "platform-cli-muii"
REGISTRATION_TOPIC     = "register"
REGISTERED_DEVICE_FILE = 'registeredDevices.json'
KMS_SERVER_URL         = "http://127.0.0.1:5000/"
HASH_KEY               = b'kkpo-kktua'

#####
### Parameters used for the listening process
#####
topics_subscribed      = []

#####
### Parameters used for the registration process
#####
connected              = asyncio.Semaphore(0)   # Semaphore to control the connection with the Device
msg_1                  = False
msg_3                  = False
msg_5                  = False
msg_7                  = False
verificationCode       = ""
connection_failed      = False
newDevice              = {}
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
    message["timestamp"]= str( datetime.now() )
    if msg_number != 0:

        message["msg"]  = msg_number
    
    header = {
        "id": PLATFORM_ID,
        "topic": topic,
        "timestamp": message["timestamp"]
    }
    message["sign"] = hmac.new(HASH_KEY, json.dumps( header ).encode(), hashlib.sha384).hexdigest()

    return message

def print_error_registration( error_message ):
    """

    """
    global connection_failed
    print( "ERROR: ", error_message )
    connection_failed = True

def on_receive_message_1( client, userdata, msg ):
    """

    """
    global encriptor, shared_key
    global asymmetricAlgorithm, symmetricAlgorithm
    # Received message 1 for the registration process       
    auth = msg.get( "auth", "" )
    if auth != "":
        
        asymmetricAlgorithm = auth.get( "asymmetric", "" ) 
        if asymmetricAlgorithm == "dh":

            g = auth.get( "g", "" )
            p = auth.get( "p", "" )
            device_pub_key = auth.get( "public_key", "" )
            if g == "" and p == "" and device_pub_key == "":
                # Cannot be empty.
                return False
            # Generate private key and public key for platform in the registration process
            pn = dh.DHParameterNumbers( p, g )
            parameters = pn.parameters(default_backend())
            private_key, public_key = utils.dhGenKeys(parameters)
            # Generate shared key
            device_pub_key = utils.load_key( device_pub_key )
            shared_key = utils.dhGenSharedKey( private_key, device_pub_key )

            # Building message two.
            answer_registration_request = {
                "auth": {
                    "public_key": public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode( "utf-8" )
                }                        
            }
        elif asymmetricAlgorithm == "ecdh":
            
            x = auth.get( "x", "" )
            y = auth.get( "y", "" )
            if x == "" and y == "":
                # Cannot be empty.
                return False
            private_key, public_key = utils.ecdhGenKeys(utils.curve)
            device_pub_key = ec.Point( utils.curve, x, y )
            shared_key = utils.ecdhGenSharedKey( private_key, device_pub_key )
            
            # Building message two.
            answer_registration_request = {
                "auth": {
                    "x": public_key.x,
                    "y": public_key.y
                }                        
            }

        if shared_key == "":
            # Cannot be empty.
            return False
        symmetricAlgorithm = auth.get( "symmetric", "" )
        if symmetricAlgorithm == "fernet":

            encriptor = Fernet( base64.urlsafe_b64encode( shared_key ) )
        elif symmetricAlgorithm == "chacha":
            
            encriptor = ChaCha20Poly1305( shared_key )
        
        message = add_header_message( answer_registration_request, userdata, REGISTRATION_TOPIC, 2 )
        utils.send( client, None, message )
        return True
    return False

def on_receive_message_3( client, userdata, msg ):
    """

    """
    global encriptor, shared_key
    global asymmetricAlgorithm, symmetricAlgorithm
    # Received a message with the KEY generated + 30, to ensure the
    # rightful of the device to connect. Send KEY Received + 20.
    if encriptor != None:

        new_key = msg.get( "new_key", "" )
        if new_key != "":
            
            encriptor = utils.modify_encriptor( new_key, symmetricAlgorithm )
        keyPlusThirty = shared_key+"30".encode()
        keyReceived = msg.get( "payload", "" )
        if str( keyPlusThirty ) == keyReceived:

            key = shared_key+"20".encode()
            key_confirmation = { "payload": str( key ) }
            key_confirmation["new_key"] = utils.generate_new_key( symmetricAlgorithm )
            message = add_header_message( key_confirmation, userdata, REGISTRATION_TOPIC, 4 )
            utils.send( client, encriptor, message )
            encriptor = utils.modify_encriptor( key_confirmation["new_key"], symmetricAlgorithm )
            return True
    return False

def on_receive_message_5( client, userdata, msg ):
    """

    """
    global encriptor
    global symmetricAlgorithm, verificationCode
    # If receive confirmation, introduce code and send to device.
    if encriptor != None:

        if msg.get( "status", "ERROR" ) == "OK":
            new_key = msg.get( "new_key", "" )
            if new_key != "":

                encriptor = utils.modify_encriptor( new_key, symmetricAlgorithm )

            deviceType = msg.get( "type", "" )
            if deviceType != "" and deviceType == "I":
                
                verificationCode = str( round( random() * 1000000 ) )
                print( "Introduce this code into your device: ", str( verificationCode ) )
            else:

                code = input( "Enter the code provided by the device: " )
                code_confirmation = { "code": code }
                code_confirmation["new_key"] = utils.generate_new_key( symmetricAlgorithm )
                message = add_header_message( code_confirmation, userdata, REGISTRATION_TOPIC, 6 )
                utils.send( client, encriptor, message )
                encriptor = utils.modify_encriptor( code_confirmation["new_key"], symmetricAlgorithm ) 
            return True
    return False

def on_receive_message_7( client, userdata, msg ):
    """

    """
    global encriptor, newDevice
    global symmetricAlgorithm, verificationCode
    # If Device has input, we will receive a code so we compare it
    # with the verificationCode obtained before. If it has not input,
    # we will receive a confimation, and if everything is ok,
    # we will send the data_topic and key_topic.
    if encriptor != None:

        validDevice = False
        deviceType = msg.get( "type", "" )
        if deviceType != "" and deviceType == "I":

            if verificationCode == msg.get( "code", "" ):

                validDevice = True
        else:

            if msg.get( "status", "ERROR" ) == "OK":

                validDevice = True   
        if validDevice:
            new_key = msg.get( "new_key", "" )
            if new_key != "":

                encriptor = utils.modify_encriptor( new_key, symmetricAlgorithm )

            data_topic = "data-" + msg.get( "id" ) + "-" + str( round( random() * 1000000 ) )
            key_topic = "key-" + msg.get( "id" ) + "-" + str( round( random() * 1000000 ) )
            topic_message = { 
                "data_topic": data_topic,
                "key_topic": key_topic
            }
            topic_message["new_key"] = utils.generate_new_key( symmetricAlgorithm )
            message = add_header_message( topic_message, userdata, REGISTRATION_TOPIC, 8 )
            utils.send( client, encriptor, message )
            encriptor = utils.modify_encriptor( topic_message["new_key"], symmetricAlgorithm ) 
            newDevice = {
                "id": msg.get( "id" ),
                "type": deviceType,
                "data_topic": data_topic,
                "key_topic": key_topic,
                "symmetric": symmetricAlgorithm,
                "shared_key": topic_message["new_key"]
            }
            return True
    return False

def on_registration( client, userdata, msg ):
    """
        Method used for the registration process of a device.
    """
    global connected, connection_failed
    global msg_1, msg_3, msg_5, msg_7
    message, trustworthy = utils.get_message( str( msg.payload.decode( "utf-8" ) ), encriptor, HASH_KEY )
    if message != "" and trustworthy:
        
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
                    
                    msg_1 = on_receive_message_1( client, userdata, message )
                    if not msg_1:

                        print_error_registration( "Registration request incomplete." )
                elif msg_1 and number == 3:
                    
                    msg_3 = on_receive_message_3( client, userdata, message )
                    if not msg_3:
                        
                        print_error_registration( "Keys does not match." )
                elif msg_3 and number == 5:
                    
                    msg_5 = on_receive_message_5( client, userdata, message )
                    if not msg_5:
                        
                        print_error_registration( "Code does not match." )
                elif msg_5 and number == 7:
                    
                    msg_7 = on_receive_message_7( client, userdata, message )
                    if not msg_7:

                        print_error_registration( "Connection failed." )
                elif msg_7 and number == 9:
                    # We received a confirmation of the topics reception from the device.
                    connected.release()
    if not trustworthy:
        
        print_error_registration( "Corrupt message received. Closing process." )

def connect_MQTT( server, port, user, password, message_handler ):
    """ 
        Connection to MQTT Server.
    """
    userdata ={
        "user": user,
        "password": password
    }
    client = mqtt.Client( client_id=PLATFORM_ID, userdata=userdata)
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
    while flag.locked() and \
        not connection_failed and difference < time:
        
        difference = ( datetime.now() - now ).total_seconds()

def getRegisteredDevices():
    """

    """
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
                "data_topic": newDevice["data_topic"],
                "type": newDevice["type"],
                "symmetric": newDevice["symmetric"]
            }
            json.dump( devices, file, indent=4 )
        # Registered Devices into KMS
        post_message = {
            # Data information to sent to KMS
            "id": newDevice["id"],
            "key_topic": newDevice["key_topic"],
            "symmetric": newDevice["symmetric"],
            "shared_key": newDevice["shared_key"]
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
    devices = getRegisteredDevices()
    if devices == {}:
        
        print ( "No devices registered." )
    else:
        
        print( json.dumps( devices, indent=4, sort_keys=True ) )

def get_data_message( payload, secrets, symmetricAlgorithm ):
    """

    """
    message = "" 
    if secrets != None and symmetricAlgorithm != None:

        key = secrets.get( "1", "" )
        if key != "":
            
            encriptor = utils.modify_encriptor( key, symmetricAlgorithm )
            message, trustworthy = utils.get_message( payload, encriptor, HASH_KEY )
            if message == "":
                key = secrets.get( "0", "" )
                if key != "":
                    encriptor = utils.modify_encriptor( key, symmetricAlgorithm )
                    message, trustworthy = utils.get_message( payload, encriptor, HASH_KEY )
    if not trustworthy:
        
        message = ""          
    return message 

def on_message( client, userdata, msg ):
    """
        Receiving from all topics subscribed.
    """
    global topics_subscribed
    if msg.topic in topics_subscribed:
         
        pattern = r'(device\-\d+)'
        match = re.search( pattern, msg.topic )
        if match:

            device_id = match.group()
            # Registered Devices into KMS
            secret_request = {
                # Data information to sent to KMS
                "id": device_id
            }
            secrets = requests.post( KMS_SERVER_URL+"get-key", json = secret_request, auth=( userdata["user"], userdata["password"] ) ).json()
            message = get_data_message( str( msg.payload.decode( "utf-8" ) ), secrets.get( "secrets", None), secrets.get( "symmetric", None ) )
            if message != "":
                print( message )

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def connect( server, port, user, password ):
    """

    """
    global topics_subscribed
    client = connect_MQTT( server, port, user, password, on_message )
    # Subscribe to all topics included in registeredDevices.json file.
    # TODO: Check if KMS is alive.
    # TODO: If KMS is alive, check if there is any non-registered device in KMS that should be registered and register it in KMS.
    filename = 'registeredDevices.json'
    if os.path.exists( filename ):
        with open( filename ) as file:

            data = json.load( file )
            for key, value in data.items():

                topics_subscribed.append( value["data_topic"] )
                client.subscribe( value["data_topic"] )
    while True:      # Keep Platform listening.
        pass

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

        topics_subscribed.append( topic )
        client.subscribe( topic )
        while True: # Keep Platform listening.
            pass
    else:
        
        print( "No topic selected." )

@click.command()
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-i', '--idDevice', 'idDevice', required=True, default="", type=str, help="Introduce the id of the device you want to remove." )
def remove_device( user, password, idDevice ):
    """

    """
    post_message = {
        # Data information to sent to KMS
        "id": idDevice
    }
    devices = getRegisteredDevices()
    # Add the new registered device.
    with open( REGISTERED_DEVICE_FILE, 'w' ) as file:
    
        del devices[idDevice]
        json.dump( devices, file, indent=4 )
    message = requests.post( KMS_SERVER_URL+"remove-device", json = post_message, auth=( user, password ) )
    if message.json().get( "status", "ERROR" ) == "OK":

        print( "Device have been removed from KMS successfully.")
    else:

        print( "Fail during removing device from KMS.")

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