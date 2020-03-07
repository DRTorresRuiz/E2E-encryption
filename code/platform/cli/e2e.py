import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import requests
import threading
import click
import json
import time
import os

KEY_ID      = "platform"
KEY_SECRET  = "platform-MUII"

CLIENT_ID              = "platform-muii"
REGISTRATION_TOPIC     = "register"

# Variables for register a device
registration_attemp    = ""
deviceAttemp = False
deviceConnected = False

def on_connect(client, userdata, flags, rc):

  print( "Platform is ready to work." )
  print( "Connected with result code " + str( rc ) )

def on_message( client, userdata, msg ):

  print( msg.topic + " " + str( msg.payload ))

def on_message_register( client, userdata, msg ):
  global deviceConnected
  global deviceAttemp
  global registration_attemp 
 
  attemp = json.loads( str( msg.payload.decode("utf-8") ) )
  if ( attemp.get("id", CLIENT_ID) != CLIENT_ID ):

    if( not deviceAttemp and not deviceConnected and msg.topic == REGISTRATION_TOPIC ): 
      
      deviceAttemp = True
      registration_attemp = attemp
      new_msg = {
        "id": CLIENT_ID,
        "data_topic": "data-" + registration_attemp.get("id") + "-" + str( round( random() * 1000000 ) ),
        "key_topic": "key-" + registration_attemp.get("id") + "-" + str( round( random() * 1000000 ) )
      }
      registration_attemp["data_topic"] = new_msg["data_topic"]
      registration_attemp["key_topic"] = new_msg["key_topic"]
      client.publish( REGISTRATION_TOPIC, json.dumps( new_msg ) )
      print( "Data sent to device." )
    elif ( deviceAttemp and not deviceConnected and msg.topic == REGISTRATION_TOPIC ):

      deviceConnected=True
  else:

    print( "Discarting registration request: " + registration_attemp )

@click.group()
def cli():
  pass

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
def register( server, port ):
  global deviceAttemp
  global deviceConnected

  client = mqtt.Client( client_id=CLIENT_ID )
  client.on_message = on_message_register
  client.username_pw_set( KEY_ID, KEY_SECRET )
  client.connect( server, port, 60 )

  client.loop_start()

  client.subscribe( REGISTRATION_TOPIC )
  now = datetime.now()
  difference = 0
  while ( not deviceAttemp and difference < 120 ):
    print( "Attempting to connect to the device...")
    difference = ( datetime.now() - now ).total_seconds()
    time.sleep(2)

  # Waiting device to confirm...
  now = datetime.now()
  difference = 0
  while ( not deviceConnected and difference < 120 ):
    print( "Waiting answer of the device...")
    difference = ( datetime.now() - now ).total_seconds()
    time.sleep(2)
  client.unsubscribe( REGISTRATION_TOPIC )

  devices = {}
  filename = 'registeredDevices.json'
  if not os.path.exists( filename ):

    with open( filename, 'w') as file: file.write("{}") 
  
  with open(filename) as file:

    data = json.load(file)
    for key, value in data.items():
      devices[key] = value
  
  print(devices)

  with open(filename, 'w') as file:
    devices[registration_attemp["id"]] = {
      "data_topic": registration_attemp["data_topic"]
    }
      
    json.dump( devices, file, indent=4 )

  post_message = {
    "id": registration_attemp["id"],
    "key_topic": registration_attemp["key_topic"]
  }
  
  print(post_message)

  KMS_SERVER_URL = "http://127.0.0.1:5000/register-device"
  message = requests.post(KMS_SERVER_URL, json = post_message)
  print( "Device successfully added: ", message.json())
  

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
def connect( server, port ):

  client = mqtt.Client( client_id=CLIENT_ID )
  client.on_connect = on_connect
  client.on_message = on_message
  client.username_pw_set( KEY_ID, KEY_SECRET )
  client.connect( server, port, 60 )

  client.loop_start()
  
  filename = 'registeredDevices.json'
  if os.path.exists( filename ):
    with open(filename) as file:

      data = json.load(file)
      for key, value in data.items():
        client.subscribe( value["data_topic"] )

  while True:    
      # TODO: Reset keys after a while for each device
      # client.publish( "KEYS", "HEY, I'M A KEY", 2 ) # TODO: Publish in different topics
      time.sleep(1)

# TODO: SEPARATE TASKS in commands
# - Register new device
# - List devices / topics
# - Remove devices
# - Escuchar todos los topics 
# - Select and Read from an specific topic / device
# - Run web platform

if __name__ == '__main__':
  cli.add_command(connect)
  cli.add_command(register)
  cli()