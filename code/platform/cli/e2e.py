import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import requests
import threading
import click
import json
import time
import os

CLIENT_ID              = "platform-muii"
REGISTRATION_TOPIC     = "register"

# Variables for register a device
registration_attemp    = ""
deviceAttemp = False
deviceConnected = False

DevicesList =[] # List of devices
TopicsList =[] # List of topics


def on_connect( client, userdata, flags, rc ):

  print( "Platform is ready to work." )
  print( "Connected with result code " + str( rc ) )

def on_message( client, userdata, msg ):
  # Receiving from all topics.
  print( msg.topic + " " + str( msg.payload ) )

def on_message_register( client, userdata, msg ):
  # Method used to registration process of a device.
  global deviceConnected
  global deviceAttemp
  global registration_attemp 
 
  attemp = json.loads( str( msg.payload.decode( "utf-8" ) ) )
  if attemp.get( "id", CLIENT_ID ) != CLIENT_ID:
    # TODO: Compare parameters of the request to see if it is a rightful device.
    if not deviceAttemp and not deviceConnected and msg.topic == REGISTRATION_TOPIC: 
      # Request message received from an external Device.
      deviceAttemp = True
      registration_attemp = attemp
      new_msg = {
        "id": CLIENT_ID,
        "data_topic": "data-" + registration_attemp.get( "id" ) + "-" + str( round( random() * 1000000 ) ),
        "key_topic": "key-" + registration_attemp.get( "id" ) + "-" + str( round( random() * 1000000 ) )
      }
      registration_attemp["data_topic"] = new_msg["data_topic"]
      registration_attemp["key_topic"] = new_msg["key_topic"]
      client.publish( REGISTRATION_TOPIC, json.dumps( new_msg ) )
      print( "Data sent to device." )
    elif deviceAttemp and not deviceConnected and msg.topic == REGISTRATION_TOPIC: deviceConnected=True
  else: print( "Discarting registration request: " + registration_attemp )

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

  client = connect_MQTT( server, port, user, password, on_message_register )

  # Waiting device to send information data to register.
  client.subscribe( REGISTRATION_TOPIC )
  now = datetime.now()
  difference = 0
  while not deviceAttemp and difference < 120:

    print( "Attempting to connect to the device..." )
    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 10 )

  # Waiting device to confirm...
  now = datetime.now()
  difference = 0
  while not deviceConnected and difference < 120:

    print( "Waiting answer of the device..." )
    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 10 )
  client.unsubscribe( REGISTRATION_TOPIC )
  
  # Check previous devices registered.
  devices = {} # To group all previous devices registered.
  filename = 'registeredDevices.json'
  if not os.path.exists( filename ):
    # If file does not exit, it will be created.
    with open( filename, 'w') as file: file.write("{}") 
  with open( filename ) as file:
    # Group previous devices registered
    data = json.load( file )
    for key, value in data.items():
      devices[key] = value
  print( devices )
  
  # Add the new registered device.
  with open( filename, 'w' ) as file:
  
    devices[registration_attemp["id"]] = {
      "data_topic": registration_attemp["data_topic"]
    }
    json.dump( devices, file, indent=4 )
  
  # Send post message to KMS to add the device in the Key Rotation Process.
  post_message = {
    # Data information to sent to KMS
    "id": registration_attemp["id"],
    "key_topic": registration_attemp["key_topic"]
    # TODO: Include information about algorithms
  }
  KMS_SERVER_URL = "http://127.0.0.1:5000/register-device"
  message = requests.post( KMS_SERVER_URL, json = post_message, auth=( user, password ) )
  print( "Device successfully added to KMS: ", message.json() )
  

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def connect( server, port, user, password ):

  client = connect_MQTT( server, port, user, password, on_message )
  
  # Subscribe to all topics included in registeredDevices.json file.
  filename = 'registeredDevices.json'
  if os.path.exists( filename ):
    with open( filename ) as file:

      data = json.load( file )
      for key, value in data.items():
        client.subscribe( value["data_topic"] )

  while True:      # Keep Platform listening.
      time.sleep( 10 )


@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Server." )
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password." )
def getKeyFromKMS( server, port, user, password ):
      #TODO: Use de log in as other methods
  KMS_SERVER_URL = "http://127.0.0.1:5000/new-key"
  request_message = requests.get( KMS_SERVER_URL, auth=( user, password ) )
  print( "Device successfully added to KMS: ", request_message.json() )


@click.command()
def getDevicesList():
    #TODO: Use de log in as the other methods
    with open('registeredDevices.json') as json_file:
      data = json.load(json_file)
      for p in data:
        print(p)
        DevicesList.append(p)
    return DevicesList

@click.command()
def getTopicsList():
    #TODO: Use de log in as the other methods
    with open('registeredDevices.json') as json_file:
      data = json.load(json_file)
      for p in data:
          #print(data[p]['data_topic'])
          TopicsList.append(data[p]['data_topic'])
    return TopicsList
  
@click.command()
def startWebService():
    os.system("python ../web/manage.py runserver")  




# TODO: SEPARATE TASKS in commands
# - [x] Register new device.
# - [x] List devices / topics. CUIDADO (REVISAR, HECHO POR FERNANDO ;') 
# - [ ] Remove devices from list and KMS.
# - [ ] Escuchar todos los topics.
# - [ ] Select and Read from an specific topic / device.
# - [x] Run web platform (?) CUIDADO (REVISAR, HECHO POR FERNANDO ;')

if __name__ == '__main__':
  # This main process include the commands for the platform cli.
  # If you need help, run: `python e2e.py --help`
  cli.add_command( connect )
  cli.add_command( register )
  cli.add_command( getKeyFromKMS )
  cli.add_command(getDevicesList)
  cli.add_command(getTopicsList)
  cli.add_command(startWebService)  
  cli()