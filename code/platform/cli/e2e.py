import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import requests
import threading
import click
import json
import time
import os

CLIENT_ID              = "platform-cli-muii"
REGISTRATION_TOPIC     = "register"

# Variables for register a device
registration_attemp    = ""
deviceAttemp = False
deviceConnected = False
authenticated = False
authFailed = False
inputType = False
verificationCode = 0

def on_connect( client, userdata, flags, rc ):

  print( "Platform is ready to work." )
  print( "Connected with result code " + str( rc ) )

def on_message( client, userdata, msg ):
  # Receiving from all topics.
  print( msg.topic + " " + str( msg.payload ) )

def sync_I( client ):
  # Request message received from an external Device.
  global deviceAttemp
  global authenticated
  global authFailed
  global registration_attemp

  now = datetime.now()
  difference = 0
  print( "Waiting input code from the device..." )
  while not authenticated and not authFailed and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )
  print( registration_attemp )
  
  
def sync_O( client ):
  # Request message received from an external Device.
  global deviceAttemp
  global authenticated
  global registration_attemp

  now = datetime.now()
  difference = 0
  while not authenticated and not authFailed and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )

  
def on_message_register( client, userdata, msg ):
  # Method used to registration process of a device.
  global deviceConnected
  global deviceAttemp
  global authenticated
  global authFailed
  global inputType
  global verificationCode
  global registration_attemp 
 
  if msg.topic == REGISTRATION_TOPIC:

    attemp = json.loads( str( msg.payload.decode( "utf-8" ) ) )
    if attemp.get( "id", CLIENT_ID ) != CLIENT_ID and not deviceAttemp: # This means is not the platform itself.
      # TODO: Compare parameters of the request to see if it is a rightful device.
      registration_attemp = attemp 
      deviceAttemp = True

      if registration_attemp["type"] == "noIO": authenticated = True
      elif registration_attemp["type"] == "I": inputType = True
      elif registration_attemp["type"] == "O": inputType = False

      if not authenticated:
        if inputType:
          verificationCode = round( random() * 1000000 )
          print( "Introduce this code into your device: ", str( verificationCode ) )
        else:
          # Output Device authentication process
          code = input( "Enter the code provided by the device: " )
          new_message = {
            "id": CLIENT_ID,
            "code": code
          }
          client.publish( REGISTRATION_TOPIC, json.dumps( new_message ) )
          print( "Message sent. Waiting for confirmation." )
    elif deviceAttemp and attemp.get( "id", "" ) == registration_attemp["id"]:
      if not authenticated:
        if inputType:
          print( "Confirmation for input code..." )
          print( attemp )
          if int( attemp.get( "code", 0 ) ) == verificationCode:
            authenticated = True
          else: authFailed = True
        else:
          # Output Device authentication process
          print( "Confirmation for output code..." )
          print( attemp )
          if attemp.get( "confirmationCode", "" ) != "":

            if attemp.get( "confirmationCode" ) == "OK":
              authenticated = True
            else:
              authFailed = True
      else: # authenticated True
        # TODO: Check confirmation message.
        deviceConnected=True
    else: print( "Discarting registration request: " + attemp )

    if authenticated and not deviceConnected:
      new_msg = {
        "id": CLIENT_ID,
        "data_topic": "data-" + registration_attemp.get( "id" ) + "-" + str( round( random() * 1000000 ) ),
        "key_topic": "key-" + registration_attemp.get( "id" ) + "-" + str( round( random() * 1000000 ) )
      }
      registration_attemp["data_topic"] = new_msg["data_topic"]
      registration_attemp["key_topic"] = new_msg["key_topic"]
      client.publish( REGISTRATION_TOPIC, json.dumps( new_msg ) )
      print( "Data sent to device." )
    

def connect_MQTT( server, port, user, password, message_handler ):
  # Make the connection to the MQTT Server.
  client = mqtt.Client( client_id=CLIENT_ID )
  client.on_message = message_handler
  client.username_pw_set( user, password )
  client.connect( server, port, 60 )
  client.loop_start()
  return client

@click.group()
def cli():
  pass

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def register( server, port, user, password ):
  global deviceAttemp
  global deviceConnected
  global authenticated
  global authFailed
  global inputType

  client = connect_MQTT( server, port, user, password, on_message_register )

  # Waiting device to send information data to register.
  client.subscribe( REGISTRATION_TOPIC )
  now = datetime.now()
  difference = 0
  print( "Attempting to connect to the device..." )
  while not deviceAttemp and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )

  # If it not authenticated means that is a input or ouput device.
  # So, we need to follow additional steps.
  if not authenticated:
    if inputType:
      sync_I( client )
    else:
      sync_O( client )

  if authenticated and not authFailed:
    # Waiting device to confirm...
    now = datetime.now()
    difference = 0
    print( "Waiting answer of the device..." )
    while not deviceConnected and difference < 120:

      difference = ( datetime.now() - now ).total_seconds()
      time.sleep( 1 )
    client.unsubscribe( REGISTRATION_TOPIC )
    
    if deviceConnected:
      print( "Device connected." )

      # Check previous devices registered.
      devices = {} # To group all previous devices registered.
      filename = 'registeredDevices.json'
      if not os.path.exists( filename ):
        # If file does not exit, it will be created.
        with open( filename, 'w') as file: file.write("{}") 
      with open( filename ) as file:
        # Group previous devices registered
        devices = json.load( file )
      print( devices )
      
      # Add the new registered device.
      with open( filename, 'w' ) as file:
      
        devices[registration_attemp["id"]] = {
          "data_topic": registration_attemp["data_topic"]
        }
        json.dump( devices, file, indent=4 )
      
      # Send post message to KMS to add the device in the Key Rotation Process.
      # TODO: If KMS can not be reach, save into a document to send it later.
      post_message = {
        # Data information to sent to KMS
        "id": registration_attemp["id"],
        "key_topic": registration_attemp["key_topic"]
        # TODO: Include information about algorithms
      }
      KMS_SERVER_URL = "http://127.0.0.1:5000/register-device"
      message = requests.post( KMS_SERVER_URL, json = post_message, auth=( user, password ) )
      print( "Device successfully added to KMS: ", message.json() )
  elif authFailed:
      
    print( "Authentication process has failed. Bad code. Try again." )
  

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
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
      time.sleep( 10 )

# TODO: SEPARATE TASKS in commands
# - [x] Register new device.
# - [ ] TODO: List devices / topics.
# - [ ] TODO: Remove devices from list and KMS.
# - [x] Escuchar todos los topics.
# - [ ] TODO: Select and Read from an specific topic / device.

if __name__ == '__main__':
  # This main process include the commands for the platform cli.
  # If you need help, run: `python e2e.py --help`
  cli.add_command( connect )
  cli.add_command( register )
  cli()