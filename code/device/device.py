from cryptography.hazmat.primitives.serialization import PublicFormat, Encoding, load_pem_public_key
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import threading
import time as t
import asyncio
import base64
import click
import json

# Add path to get utils.py
from sys import path
path.append("../") 
import utils as utils # Include different common functions.

# Topic used to connect to the platform through the MQTT Server.
REGISTRATION_TOPIC = "register" 

data_topic         = ""                    # Topic used to send values from sensors.
key_topic          = ""                    # Topic used to receives values from KMS.
encriptor          = None

#####
### Parameters used for the registration process
#####
connected          = asyncio.Semaphore(0)  # Semaphore to control the connection with the Platform
verificationCode   = "000000"              # "000000" is only valid for noIO Devices
msg_2              = False
msg_4              = False
msg_6              = False
connection_failed  = False
parameters         = utils.dhParameters()
private_key        = parameters.generate_private_key()
public_key         = private_key.public_key()
shared_key         = ""

@click.group()
def cli():
  pass

def add_header_message( message, userdata, topic, msg_number=0 ):
    """
        This functions adds information about the device
        to send it to the platform.
    """
    message["id"]       = userdata["id"]
    message["type"]     = userdata["type"]
    message["topic"]    = topic
    if msg_number != 0:

        message["msg"]  = msg_number
    return message

def on_connect( client, userdata, flags, rc ):
    """ 
        Once connected to the MQTT Server, this device sends 
        a registration request through the REGISTRATION_TOPIC.
        And, subscribe to this topic to start the registration process. 
    """
    global parameters, public_key

    # TODO: Persistence of the connection.

    g = parameters.parameter_numbers().g
    p = parameters.parameter_numbers().p
    
    registration_request = {
        "auth": {
            "symmetric": userdata["symmetric"],
            "asymmetric": userdata["asymmetric"],
            "g": g,
            "p": p,
            "public_key": public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode( "utf-8" )
        }
    }
    message = add_header_message( registration_request, userdata, REGISTRATION_TOPIC, 1 )
    client.subscribe( REGISTRATION_TOPIC ) 
    utils.send( client, None, message ) # Send the registration request.

def introduceCode( client, userdata ):
    """

    """
    global encriptor    
    code = input( "Enter the code provided by the platform: " )
    code_confirmation = { "code": code }
    message = add_header_message( code_confirmation, userdata, REGISTRATION_TOPIC, 7 )
    utils.send( client, encriptor, message ) 

def on_registration( client, userdata, json_message ):
    """

    """
    global connected, connection_failed, verificationCode
    global data_topic, key_topic
    global msg_2, msg_4, msg_6
    global shared_key, encriptor
    number = int( json_message.get( "msg", 0 ) )
    deviceType = userdata["type"]
    symmetricAlgorithm = userdata["symmetric"]
    #TODO: asymmetricAlgorithm = userdata["asymmetric"]
    if number == 2:
        # Receive message with information to build the key.
        auth = json_message.get( "auth", "" )
        if auth != "": 
            
            platform_pub_key = auth.get( "public_key", "" )
            if platform_pub_key != "":

                # Generate shared key
                platform_pub_key = utils.load_key( platform_pub_key )
                shared_key = utils.dhGenSharedKey( private_key, platform_pub_key )
                # Create encriptor as specified
                if symmetricAlgorithm == "fernet":

                    encriptor = Fernet( base64.urlsafe_b64encode( shared_key ) )
                elif symmetricAlgorithm == "chacha":

                    print( "chacha not implemented yet." )
                if encriptor != None:
                    # Send KEY + 30 to show rightful to the platform.
                    key = shared_key+"30".encode()
                    key_confirmation = { "payload": str( key ) }
                    message = add_header_message( key_confirmation, userdata, REGISTRATION_TOPIC, 3 )
                    utils.send( client, encriptor, message )
                    msg_2 = True       
        if not msg_2:
            
            utils.send_error( client, REGISTRATION_TOPIC, "Platform can not be verified." )
            connection_failed = True
    elif msg_2 and number == 4:
        # Send confirmation of the key
        if encriptor != None:

            keyPlusTwenty = shared_key+"20".encode()
            keyReceived = json_message.get( "payload", "" )
            if str( keyPlusTwenty ) == keyReceived:
                # Confirmed authority of the platform
                confirmation_message = { "status": "OK" }
                message = add_header_message( confirmation_message, userdata, REGISTRATION_TOPIC, 5 )
                utils.send( client, encriptor, message ) 
                # Now, depending of the type of device we do...
                if deviceType == "O":
                    # Generate an verificationCode
                    verificationCode = str( round( random() * 1000000 ) )
                    print( "Introduce this code into your device: ", str( verificationCode ) )
                elif deviceType == "I":
                    # Introduce the code provided by the platform and send it.
                    introduceCodeThread = threading.Thread(target=introduceCode, args=[client, userdata])
                    introduceCodeThread.start()
                msg_4 = True
        if not msg_4:

            utils.send_error( client, REGISTRATION_TOPIC, "Verification code does not match." )
            connection_failed = True
    elif msg_4 and number == 6 and deviceType != "I":

        if encriptor != None:

            if verificationCode == json_message.get( "code", "" ):
                # Send confirmation of the key
                confirmation_message = { "status": "OK" }
                message = add_header_message( confirmation_message, userdata, REGISTRATION_TOPIC, 7 )
                utils.send( client, encriptor, message )
                msg_6 = True
        if not msg_6:

            utils.send_error( client, REGISTRATION_TOPIC, "Verification code does not match." )
            connection_failed = True
    elif number == 8:

        data_topic = json_message.get("data_topic", "")
        key_topic = json_message.get("key_topic", "")
        if data_topic != "" and key_topic != "":
            # Send confirmation of the key
            confirmation_message = { "status": "OK" }
            message = add_header_message( confirmation_message, userdata, REGISTRATION_TOPIC, 9 )
            utils.send( client, encriptor, message )
            client.subscribe( key_topic ) # Start subscription to KMS
        else:

            utils.send_error( client, REGISTRATION_TOPIC, "Connection Error" )
            connection_failed = True
        client.unsubscribe( REGISTRATION_TOPIC )
        connected.release()

def on_secure( client, userdata, json_message ):
    # TODO: Manage new keys.
    print( "Managing new keys received, ", json_message )

def on_message( client, userdata, msg ):
    # This function receives different messages from topics to which this device
    # is subscribed. 
    global data_topic, key_topic, encriptor
    message = utils.get_message( str( msg.payload.decode( "utf-8" ) ), encriptor )
    if message != "":
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

def connect_MQTT( userdata, serverinfo ):
    """ Connection to MQTT Server. """
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
    while flag.locked() and not connection_failed and difference < time:
        
        difference = ( datetime.now() - now ).total_seconds()

def send_data( client, userdata ):

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
    print( "[", datetime.now() ,"] Value sent: ", new_message )
    utils.send( client, encriptor, new_message )

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
        Run the simulation of an IoT Device.\n
        This command start with the process of synchronization of an IoT Device with the platform.
        Once the device is synchronized and registered in the platform, it will start sending
        values of its sensors to the platform. The data sent is encrypted by using an specified 
        symmetric algorithm. There is a KMS that manage the Key Rotation for these algorithms. 
        Diffie-Hellman (DH) and other alternatives are used for shared key generation during 
        registration process.
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
    wait_til( connected, 120, "Waiting for connecting..." )
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
    # ADD HERE A NEW COMMNAD.
    cli()
