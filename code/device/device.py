import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import click
import json
import time

REGISTRATION_TOPIC     = "register"

data_topic             = ""                                                # Topic used to send data - provided by platform in tmp_registration_topic
key_management_topic   = ""                                                # Topic used for key rotation with KMS - provided by platform in tmp_registration_topic
connected              = False                                             # If it is connected to the platform and kms correctly.
synchronized           = False                                             # If it has finished the process of connection
authenticated          = False
authFailed             = False
firstKeyNegotiated     = False
verificationCode       = 0

def on_message( client, userdata, msg ):
  # Device will only accept messages received from the `key_management_topic` (Rotation Key Algorithm from KMS)
  # and from the REGISTRATION_TOPIC as it is needed to connect it to the platform.
  global synchronized
  global authenticated
  global authFailed
  global data_topic
  global key_management_topic
  global firstKeyNegotiated
  
  if msg.topic == key_management_topic: # Rotation Key Topic
    # TODO: Replace symmetric key.
    print( msg.topic + " " + str( msg.payload ) )
  elif msg.topic == data_topic:
    # TODO: Platform will sent a message through this channel
    # to let device know that has been removed from the platform.
    # TODO: If removed, data_topic will be again "". And `connected` 
    # variable will be FALSE to stop sending values.
    # TODO: If removed, key_management_topic will also be set to "" and
    # the subscription to this topic should stop.
    print( msg.topic + " " + str( msg.payload ) )
  elif msg.topic == REGISTRATION_TOPIC: # Accept and Config Parameters Connection Topic
    # TODO: Make sure the data is sent by the platform.
    connection_config = json.loads( str( msg.payload.decode("utf-8") ) )
    if connection_config.get( "id", userdata["id"] ) != userdata["id"]: # Not reading data that this device sent. Avoiding loops.
      print( connection_config )
      if authenticated:
        # Establish data_topic and key_management
        data_topic = connection_config["data_topic"]
        key_management_topic = connection_config["key_topic"]
        # TODO: Check other params to ensure connection with platform.
        synchronized=True
      elif not authenticated and connection_config.get( "infoKeys", "" ) != "":
        # TODO: Save key to encrypt.
        print( connection_config )
        firstKeyNegotiated = True
      elif not authenticated and connection_config.get( "code", "" ) != "": 
        # Receive output message.
        if int( connection_config.get("code", 0) ) == verificationCode:
          new_message = {
            "id": userdata["id"],
            "type": userdata["type"],
            "confirmationCode": "OK"
          }
          client.publish( REGISTRATION_TOPIC, json.dumps( new_message ) )
          authenticated = True
        else:
          new_message = {
            "id": userdata["id"],
            "type": userdata["type"],
            "confirmationCode": "FAILED"
          }
          client.publish( REGISTRATION_TOPIC, json.dumps( new_message ) )
          authFailed = True
      
  
def connection_request( client, userdata ):
  # Send information to the topic REGISTRATION_TOPIC through MQTT client, so platform
  # may start the connection process. Userdata should contain the information required 
  # by the platform to start a connection.
  data_registration = {
    # Data information to send to platform.
    "id": userdata["id"],
    "type": userdata["type"]
  }
  # Publish into REGISTRATION_TOPIC, previously defined, to start the 
  # process of the connection with the system (platform and KMS)
  client.publish( REGISTRATION_TOPIC, json.dumps( data_registration ) ) # Sends a JSON with data_registration
  print( "Registration request successfully sent." )

def connection_process( client, userdata ):
  global connected
  global synchronized
  global key_management_topic

  
  client.subscribe( REGISTRATION_TOPIC )
  # Waiting for first key
  now = datetime.now()
  difference = 0
  print( "Negotiating key..." )
  while not firstKeyNegotiated and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )

  # Wait answer from the platform in the REGISTRATION TOPIC.
  now = datetime.now()
  difference = 0
  print( "Attempting to connect..." )
  while not synchronized and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )
  client.unsubscribe( REGISTRATION_TOPIC )
  
  if synchronized: 
    # Subscribe to key_management_topic and send message of confirmation.
    client.subscribe( key_management_topic ) # Start subscription to KMS
    confimation_message = {
      # Build message of confirmation
      "id": userdata["id"]
    }
    client.publish( REGISTRATION_TOPIC, json.dumps( confimation_message ) ) # Confirmation message to the platform.
    # If the platform has given a correct answer, the
    # device will start to send data.
    connected = True
    print( "Successfully connected." )


def sync_noIO( client, userdata ):
  # Synchronization process for devices without input nor output methods.
  global synchronized
  global authenticated
  global verificationCode
  global connected

  connection_request( client, userdata ) # Send to request to be registered in the platform. And so, start the sync process.

  client.subscribe( REGISTRATION_TOPIC )
  verificationCode = 000000
  # print( "Introduce this code into your device: ", str( verificationCode ) )

  now = datetime.now()
  difference = 0
  print( "Waiting input code from the platform..." )
  while not authenticated and not authFailed and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )
  client.unsubscribe( REGISTRATION_TOPIC )

  if authenticated and not authFailed:
    connection_process( client, userdata )
  elif authFailed:
    print( "Process of authentication has failed. Bad code. Try again." )

def sync_I( client, userdata ):
  # Synchronization process for devices with an input method.
  global authenticated

  connection_request( client, userdata ) # Send to request to be registered in the platform. And so, start the sync process.

  code = input( "Introduce code provided by the platform: " )
  new_message = {
    "id": userdata["id"],
    "type": userdata["type"],
    "code": code
  }
  client.publish( REGISTRATION_TOPIC, json.dumps( new_message ) )
  authenticated = True

  connection_process( client, userdata )

def sync_O( client, userdata ):
  # Synchronization process for devices with an output method.
  global authenticated
  global verificationCode
  global authFailed

  connection_request( client, userdata ) # Send to request to be registered in the platform. And so, start the sync process.

  client.subscribe( REGISTRATION_TOPIC )
  verificationCode = round( random() * 1000000 )
  print( "Introduce this code into your device: ", str( verificationCode ) )
  
  now = datetime.now()
  difference = 0
  print( "Waiting input code from the platform..." )
  while not authenticated and not authFailed and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )
  client.unsubscribe( REGISTRATION_TOPIC )

  if authenticated and not authFailed:
    connection_process( client, userdata )
  elif authFailed:
    print( "Process of authentication has failed. Bad code. Try again." )

@click.group()
def cli():
  pass

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send data." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send data." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
@click.option( '-t', '--device-type', 'typeDevice', type=click.Choice(['noIO','I','O']), default="noIO", help="The type of the device. Your choice will affect the way your device connects to the platform. noIO - without any entrance nor output; I - with one keyboard input available; O - the O letter indicates a device with one display." )
@click.option( '-i', '--identification', 'idDevice', type=str, default="", help="The Device ID you want to use. If not specified, it will be generated randomly." )
def connect( server, port, user, password, typeDevice, idDevice ):
  """
    Start an IoT device and connect it to the platform.
  """
  global connected
  userdata = {
    # Data information about the device.
    "id": idDevice if idDevice != "" else "device-" + str( round( random() * 1000000 ) ),
    "type": typeDevice
  }
  
  # Connection to MQTT Server.
  client = mqtt.Client( client_id=userdata["id"], userdata=userdata )  
  client.on_message = on_message
  client.username_pw_set( user, password )
  client.connect( server, port, 60 )
  client.loop_start()

  # TODO: Check if Device is already registered and get information.
  # Sync process. It depends on the type of the device.
  if typeDevice == "noIO":
    # Start sync process for devices without input nor output methods.
    sync_noIO( client, userdata )
  elif typeDevice == "I":
    # Start sync process for devices with an input method.
    sync_I( client, userdata )
  else: # typeDevice == O
    # Start sync process for devices with an output method.
    sync_O( client, userdata )
  
  # After a successful connection, the device will publish into the topic specified by the platform.
  while connected and not authFailed:

    if data_topic != "" : 
      # TODO: Obtain Key to cypher.
      # TODO: cypher according the algorithm negotiated with the platform.
      new_value = random()
      client.publish( data_topic, new_value )
      print( "[", datetime.now() ,"] Send value: ", new_value )
      
      time.sleep( 20 )
    else: connected=False
  
  # Connection Error. End of the process.
  print( "Something was wrong during the connection process. Please attempt to connect to the platform again." )
    
if __name__ == '__main__':
  # This main process only include the `connect` command.
  # If you need help to run this command, check: `python device.py connect --help`
  cli.add_command( connect )
  cli()