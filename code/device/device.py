from cryptography.hazmat.primitives.serialization import PublicFormat, \
    Encoding, load_pem_public_key
from cryptography.hazmat.backends import default_backend
from chacha20poly1305 import ChaCha20Poly1305
from cryptography.fernet import Fernet
import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import tinyec.ec as ec
import threading
import time as t
import asyncio
import hashlib
import base64
import click
import hmac
import json
import os

# Add path to get utils.py
from sys import path
path.append("../") 
import utils as utils # Include different common functions.

# Topic used to connect to the platform through the MQTT Server.
REGISTRATION_TOPIC = "register" 
HASH_KEY           = b'kkpo-kktua'

data_topic         = ""                    # Topic used to send values from sensors.
key_topic          = ""                    # Topic used to receives values from KMS.
encriptor          = None                  # Used to encrypt and decrypt

#####
### Parameters used for the registration process
#####
connected          = asyncio.Semaphore(0)  # Control registration process.
verificationCode   = "000000"              # "000000" is only valid for noIO Devices.
msg_2              = False                 # Flag for received message 2.
msg_4              = False                 # Flag for received message 4.
msg_6              = False                 # Flag for received message 6.
connection_failed  = False                 # Flag to check failures during connection.
private_key        = None                  # Private key for Key Exchange
shared_key         = ""                    # First key after DH or ECDH

def add_header_message( message, userdata, topic, msg_number=0 ):
    """
        This functions adds information about the device
        to send it to the platform.
    """
    message["id"]       = userdata["id"]
    message["type"]     = userdata["type"]
    message["topic"]    = topic
    message["timestamp"]= str( datetime.now())
    if msg_number != 0:

        message["msg"]  = msg_number
    header = {
        "id": userdata["id"],
        "topic": topic,
        "timestamp": message["timestamp"]
    }
    message["sign"] = hmac.new( HASH_KEY, json.dumps( header ).encode(), \
        hashlib.sha384 ).hexdigest()
    return message

def send_confirmation_message( client, userdata, topic, number_of_message, new_key ):
    """
        Sends a confirmation message from the specified topic.
        You can send a new_key for the Ephemeral Key algorithm. 
    """
    global encriptor
    confirmation_message = { "status": "OK" }
    if new_key != "":
        
        confirmation_message["new_key"] = new_key
    message = add_header_message( confirmation_message, userdata, \
        REGISTRATION_TOPIC, number_of_message )
    utils.send( client, encriptor, message )

def on_connect( client, userdata, flags, rc ):
    """ 
        Once connected to the MQTT Server, this device sends 
        a registration request through the REGISTRATION_TOPIC.
        And, subscribe to this topic to start the registration process. 
    """
    global private_key
    if userdata["asymmetric"] == "dh":
        
        parameters         = utils.dhParameters()
        private_key        = parameters.generate_private_key()
        public_key         = private_key.public_key()
        g                  = parameters.parameter_numbers().g
        p                  = parameters.parameter_numbers().p
        registration_request = {
            "auth": {
                "symmetric": userdata["symmetric"],
                "asymmetric": userdata["asymmetric"],
                "g": g,
                "p": p,
                "public_key": public_key.public_bytes( Encoding.PEM,\
                    PublicFormat.SubjectPublicKeyInfo ).decode( "utf-8" )
            }
        }
    elif userdata["asymmetric"] == "ecdh":

        private_key, public_key = utils.ecdhGenKeys( utils.curve )
        registration_request = {
            "auth": {
                "symmetric": userdata["symmetric"],
                "asymmetric": userdata["asymmetric"],
                "x": public_key.x,
                "y": public_key.y
            }
        }
    message = add_header_message( registration_request, userdata,\
        REGISTRATION_TOPIC, 1 )
    client.subscribe( REGISTRATION_TOPIC ) 
    # Send the registration request.
    utils.send( client, None, message )

def introduceCode( client, userdata ):
    """
        This function prompts when this device type is input.
        You will need to introduce a verification code to 
        authenticate the connection.
    """
    global encriptor    
    code = input( "Enter the code provided by the platform: " )
    code_confirmation = { "code": code }
    symmetricAlgorithm = userdata["symmetric"]
    # Generate the new key to be used by the platform to encrypt next message.
    code_confirmation["new_key"] = utils.generate_new_key( symmetricAlgorithm )
    message = add_header_message( code_confirmation, userdata, REGISTRATION_TOPIC, 7 )
    utils.send( client, encriptor, message )
    # After sending the message, modify encriptor with the new key before generated.
    encriptor = utils.modify_encriptor( code_confirmation["new_key"],\
        symmetricAlgorithm ) 

def on_received_message_2( client, userdata, msg ):
    """
        Processing message 2 of the registration process. 
        This message is sent by the platform. 
        The first shared key is generated in this function after 
        getting the public key generated by the platform for the hand-shake.
        Then, this function sends the message 3 of the registration
        process to the platform. This message contains the first 
        shared key modified to be verified by the platform.
    """
    # Receive message with information to build the key.
    global encriptor, shared_key, private_key
    auth = msg.get( "auth", "" )
    if auth != "": 
            
        if userdata["asymmetric"] == "dh":

            platform_pub_key = auth.get( "public_key", "" )
            if platform_pub_key == "":
                # Cannot be empty.
                return False
            # Generate shared key
            platform_pub_key = utils.load_key( platform_pub_key )
            shared_key = utils.dhGenSharedKey( private_key, platform_pub_key )
        elif userdata["asymmetric"] == "ecdh":
            
            x = auth.get( "x", "" )
            y = auth.get( "y", "" )
            if x == "" and y == "":
                # Cannot be empty.
                return False
            platform_pub_key = ec.Point( utils.curve, x, y )
            shared_key = utils.ecdhGenSharedKey( private_key, platform_pub_key )
        # Create encriptor as specified
        if userdata["symmetric"] == "fernet":

            encriptor = Fernet( base64.urlsafe_b64encode( shared_key ) )
        elif userdata["symmetric"] == "chacha":

            encriptor = ChaCha20Poly1305( shared_key )
        if encriptor != None:
            # Send KEY + 30 to show rightful to the platform.
            key = shared_key+"30".encode()
            key_confirmation = { "payload": str( key ) }
            # Generate the new key to be used by the platform to encrypt next message.
            key_confirmation["new_key"] = utils.generate_new_key( userdata["symmetric"] )
            message = add_header_message( key_confirmation, userdata,\
                REGISTRATION_TOPIC, 3 )
            utils.send( client, encriptor, message )
            # After sending the message, modify encriptor with the new
            #  key before generated.
            encriptor = utils.modify_encriptor( key_confirmation["new_key"],\
                userdata["symmetric"] )
            return True
    return False

def on_received_message_4( client, userdata, msg ):
    """
        Platform sends the first shared key + 20 to be verified by 
        the device. After receiving this message, the device
        will introduce or show a verification code depending on 
        the type of the device.
    """
    global encriptor, verificationCode
    if encriptor != None:
        # Send shared key + 20 as the confirmation of the message.
        keyPlusTwenty = shared_key+"20".encode()
        keyReceived = msg.get( "payload", "" )
        if str( keyPlusTwenty ) == keyReceived:
            # Confirmed authority of the platform
            new_key = msg.get( "new_key", "" )
            if new_key != "":
                # Get the new_key to encrypt next message.
                encriptor = utils.modify_encriptor( new_key, userdata["symmetric"] )
            # Generate the new key to be used by the platform to encrypt next message.
            new_key_generated = utils.generate_new_key( userdata["symmetric"] )                
            send_confirmation_message( client, userdata, REGISTRATION_TOPIC,\
                5, new_key_generated )
            # After sending the message, modify encriptor with the 
            # new key before generated.
            encriptor = utils.modify_encriptor( new_key_generated,\
                userdata["symmetric"] ) 
            # Now, depending of the type of device we do...
            if userdata["type"] == "O":
                # Generate an verificationCode
                verificationCode = str( round( random() * 1000000 ) )
                print( "Introduce this code into your device: ",\
                     str( verificationCode ) )
            elif userdata["type"] == "I":
                # Introduce the code provided by the platform and send it.
                introduceCodeThread = threading.Thread(target=introduceCode,\
                    args=[client, userdata])
                introduceCodeThread.start()
            return True
    return False

def on_received_message_6( client, userdata, msg ):
    """
        If the type of the device is different of input,
        this message will be used to verified the introduced 
        code by the platform. After verifying successfully 
        it will send a confirmation to the platform.
    """
    global encriptor, verificationCode
    if encriptor == None:

        return False
    if verificationCode == msg.get( "code", "" ):
        # Send confirmation of the key
        new_key = msg.get( "new_key", "" )
        if new_key != "":
            # Get the new_key to encrypt next message.
            encriptor = utils.modify_encriptor( new_key, userdata["symmetric"] )
        # Generate the new key to be used by the platform to encrypt next message.
        new_key_generated = utils.generate_new_key( userdata["symmetric"] )                
        send_confirmation_message( client, userdata, REGISTRATION_TOPIC, 7,\
            new_key_generated )
        # After sending the message, modify encriptor with the new key before generated.
        encriptor = utils.modify_encriptor( new_key_generated, userdata["symmetric"] ) 
        return True
    return False

def on_received_message_8( client, userdata, msg ):
    """
        Message 8 sent by the platform will contain
        the data_topic and the key_topic. This function
        will send a confirmation to the platform once these
        topics are saved by the device
    """
    global encriptor, data_topic, key_topic
    new_key = msg.get( "new_key", "" )
    if new_key != "":
        # Get the new_key to encrypt next message.
        encriptor = utils.modify_encriptor( new_key, userdata["symmetric"] )
    data_topic = msg.get( "data_topic", "" )
    key_topic = msg.get( "key_topic", "" )
    if data_topic != "" and key_topic != "":
        # Send confirmation of the key
        send_confirmation_message( client, userdata, REGISTRATION_TOPIC, 9, "" )
        client.subscribe( key_topic ) # Start subscription to KMS
        client.unsubscribe( REGISTRATION_TOPIC )
        return True
    return False

def send_error( client, topic, error_message ):
    """
        Sends an error message to the platform.
    """
    global connection_failed
    utils.send_error( client, REGISTRATION_TOPIC, error_message )
    connection_failed = True

def on_registration( client, userdata, json_message ):
    """
        This function handle each message received during
        registration process.
    """
    global connected, connection_failed
    global msg_2, msg_4, msg_6
    number = int( json_message.get( "msg", 0 ) )
    if number == 2:

        msg_2 = on_received_message_2( client, userdata, json_message )
        if not msg_2:

            send_error( client, REGISTRATION_TOPIC, "Platform can not be verified." )
    elif msg_2 and number == 4:

        msg_4 = on_received_message_4( client, userdata, json_message )
        if not msg_4:

            send_error( client, REGISTRATION_TOPIC, "Verification code does not match." )
    elif msg_4 and number == 6 and userdata["type"] != "I":

        msg_6 = on_received_message_6( client, userdata, json_message )
        if not msg_6:

            send_error( client, REGISTRATION_TOPIC, "Verification code does not match." )
    elif number == 8:

        if on_received_message_8( client, userdata, json_message ):

            connected.release()
        else:

            send_error( client, REGISTRATION_TOPIC, "Connection Error" )

def on_secure( client, userdata, json_message ):
    """
        Handles the new keys from KMS
    """
    global encriptor
    new_key = json_message.get( "key", "" )
    if new_key != "":

        if userdata["symmetric"] == "fernet":
        
            encriptor = Fernet( new_key.encode() )
        elif userdata["symmetric"] == "chacha":

            encriptor = ChaCha20Poly1305( new_key.encode( "latin-1" ) )
        #print( "Managing new keys received, ", json_message )
    
def on_message( client, userdata, msg ):
    """
        This function receives and handles different messages
        from topics to which this device is subscribed. 
    """
    global data_topic, key_topic, encriptor, connection_failed
    message, trustworthy = utils.get_message( str( msg.payload.decode( "utf-8" ) ),\
        encriptor, HASH_KEY )
    if message != "" and trustworthy:
        # Get the id of the device that sent a message.
        deviceID = message.get( "id", userdata["id"] )
        if deviceID != userdata["id"]:
            # If it is different of the id of this device, we treat it.
            # We do not want to read our own messages.
            topic = message.get( "topic", "" )
            if key_topic != "" and topic == key_topic:
                # Messages received from KMS
                on_secure( client, userdata, message ) 
            elif topic == REGISTRATION_TOPIC:
                # Messages received for the registration process.
                on_registration( client, userdata, message )
    if not trustworthy:
        
        print( "Corrupt message received. Closing process." )
        connection_failed = True

def connect_MQTT( userdata, serverinfo ):
    """ 
        Connection to MQTT Server.
    """
    client = mqtt.Client( client_id=userdata["id"], userdata=userdata )  
    client.on_message = on_message
    client.on_connect = on_connect
    client.username_pw_set( serverinfo["username"], serverinfo["password"] )
    client.connect( serverinfo["server"], serverinfo["port"], 60 )
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

def send_data( client, userdata ):
    """
        Sends random data to the platform simulating 
        two sensors.
    """
    global encriptor
    new_message = {
        "values": {
            "sensor1": random(),
            "sensor2": random()
        }
    }
    message = add_header_message( new_message, userdata, data_topic )
    #print( "[", datetime.now() ,"] Value sent: ", new_message )
    utils.send( client, encriptor, message )

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True,\
    default='broker.shiftr.io', help="The MQTT Server to send data." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True,\
    default=1883, help="Port of theMQTT Server to send data." )
@click.option( '-u', '--user', 'user', required=True, type=str,\
    help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True,\
    hide_input=True, help="The password for the user to connect to the MQTT Serve. \
    If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-t', '--device-type', 'typeDevice', type=click.Choice(['noIO','I','O']),\
    default="noIO", help="The type of the device. Your choice will affect the way your \
    device connects to the platform. noIO - without any entrance nor output; I - with \
    one keyboard input available; O - the O letter indicates a device with one display." )
@click.option( '-i', '--identification', 'idDevice', type=str, default="",\
    help="The Device ID you want to use. If not specified, it will be generated randomly." )
@click.option( '-T', '--time', 'time', type=int, default=10, show_default=True,\
    help="Time passed to send new data from device to platform." )
@click.option( '-c', '--symmetric', 'symmetric', type=click.Choice(['fernet', 'chacha']),\
    default="fernet", help="The symmetric algorithm used to send the data to platform.")
@click.option( '-a', '--asymmetric', 'asymmetric', type=click.Choice(['dh', 'ecdh']),\
    default="dh", help="The asymmetric algorithm used to establish the communication.")
def start( server, port, user, password, typeDevice, idDevice, time, symmetric, asymmetric ):
    """
        Run the simulation of an IoT Device.\n
        This command start with the process of synchronization of an IoT 
        Device with the platform. Once the device is synchronized and registered
        in the platform, it will start sending values of its sensors to the platform.
        The data sent is encrypted by using an specified symmetric algorithm. 
        There is a KMS that manage the Key Rotation for these algorithms. 
        Diffie-Hellman (DH) and other alternatives are used for shared 
        key generation during registration process.
    """
    global connected
    # Group data received    
    userdata = {
        # Data information about the Device
        "id": idDevice if idDevice != "" else \
            "device-" + str( round( random() * 1000000 ) ),
        "type": typeDevice,
        "symmetric": symmetric,
        "asymmetric": asymmetric
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
    wait_til( connected, 120, "Waiting for connecting..." )
    while not connected.locked():
        # If connected, send new data.
        if data_topic != "":

            send_data( client, userdata )
        t.sleep(time)
    # If not connected, close the process.
    print( "This device is not connected. Ending process." )

@click.group()
def cli():
    
  pass

if __name__ == '__main__':
    """
        This main process only include the `connect` command.
        If you need help to run this command, 
        check: `python device.py connect --help`
    """
    cli.add_command( start )
    # ADD HERE A NEW COMMNAD.
    cli()
