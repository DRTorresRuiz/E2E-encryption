import paho.mqtt.client as mqtt
from datetime import datetime
from random import random
import click
import json
import time

REGISTRATION_TOPIC     = "register"

data_topic             = ""                                                # Topic used to send data - provided by platform in tmp_registration_topic
key_management_topic   = ""                                                # Topic used for key rotation with KMS - provided by platform in tmp_registration_topic
connected              = False                                             # If it is connected to the platform correctly.
synchronized           = False


def on_message( client, userdata, msg ):
  global synchronized
  global data_topic
  global key_management_topic

  print(msg.payload)
  if ( msg.topic == key_management_topic ): # Rotation Key Topic
    # TODO: Replace symmetric key.
    print( msg.topic + " " + str( msg.payload ) )
  elif ( msg.topic == REGISTRATION_TOPIC ): # Accept and Config Parameters Connection Topic
    
    connection_config = json.loads( str( msg.payload.decode("utf-8") ) )
    if ( connection_config.get("id", userdata["id"]) != userdata["id"] ):

      data_topic = connection_config["data_topic"]
      key_management_topic = connection_config["key_topic"]
      
      client.subscribe( key_management_topic )

      new_msg = {
        "id": userdata["id"]
      }
      client.publish( REGISTRATION_TOPIC, json.dumps( new_msg ) )
      synchronized=True
  
def sync_noIO( client, userdata ):
  global synchronized
  global connected

  data_registration = {

    "id": userdata["id"],
    "type": userdata["type"]
  }

  client.publish( REGISTRATION_TOPIC, json.dumps(data_registration) )
  print( "Registration request successfully sent.")
  
  client.subscribe( REGISTRATION_TOPIC )
  now = datetime.now()
  difference = 0
  while ( not synchronized and difference < 120 ):
    print( "Attempting to connect... Sync:" + str(synchronized) )
    difference = ( datetime.now() - now ).total_seconds()
    time.sleep(2)
  client.unsubscribe( REGISTRATION_TOPIC )
  connected = True

def sync_I( client, userdata ):
  print("Hi, device I")

def sync_O( client, userdata ):
  print("Hi, device O") 

@click.group()
def cli():
  pass

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send data." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send data." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve.")
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password.")
@click.option( '-t', '--device-type', 'typeDevice', type=click.Choice(['noIO','I','O']), default="noIO", help="The type of the device. Your choice will affect the way your device connects to the platform. noIO - without any entrance nor output; I - with one keyboard input available; O - the O letter indicates a device with one display." )
def connect( server, port, user, password, typeDevice ):
  """
    Start an IoT device and connect it to the platform.
  """
  
  userdata = {

    "id": "device-" + str( round( random() * 1000000 ) ),
    "type": typeDevice
  }

  client = mqtt.Client( client_id=userdata["id"], userdata=userdata )  
  client.on_message = on_message
  client.username_pw_set( user, password )
  client.connect( server, port, 60 )
  client.loop_start()

  if ( typeDevice == "noIO" ):

    sync_noIO( client, userdata )
  elif ( typeDevice == "I" ):

    sync_I( client, userdata )
  else: # typeDevice == O

    sync_O( client, userdata )
  
  
  while True:

    if ( data_topic != "" ): 
      new_value = random()
      client.publish( data_topic, new_value )
      print("VALUE PUBLISHED: ", new_value)
      # TODO: Wait till key to cypher is negotiated.
    time.sleep(20)
    
if __name__ == '__main__':
  cli.add_command(connect)
  cli()