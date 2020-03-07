import click
import paho.mqtt.client as mqtt
import time

KEY_ID = "device-IoT"
KEY_SECRET = "deviceMUII"

REGISTRATION_TOPIC = "register"

def on_connect_noIO(client, userdata, flags, rc):

  print( "Hi, I don't have any input nor output :(" )
  print("Connected with result code " + str( rc ))
  # TODO: Register noIO Device

def on_connect_I(client, userdata, flags, rc):

  print( "Hi, I have an keyboard entrance :)" )
  print("Connected with result code " + str( rc ))
  # TODO: Register I Device

def on_connect_O(client, userdata, flags, rc):

  print( "Hi, I have a display >:D" )
  print("Connected with result code " + str( rc ))
  # TODO: Register O Device

def on_message( client, userdata, msg ):

  print( msg.topic + " " + str( msg.payload ) )
  # TODO: Messages coming from two topics can be received. One topic is generated to negotiate the key (with a timeout specified). The other is for rotating the key, with KMS. 

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send data." )
@click.option( '-P', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send data." )
@click.option( '-u', '--user', 'user', required=True, type=str, help="The user to connect to the MQTT Serve.")
@click.option( '-p', '--password', 'password', required=True, type=str, prompt=True, hide_input=True, help="The password for the user to connect to the MQTT Serve. If you do not include this option, a prompt will appear to you introduce the password.")
@click.option( '-t', '--device-type', 'typeDevice', type=click.Choice(['noIO','I','O']), default="noIO", help="The type of the device. Your choice will affect the way your device connects to the platform. noIO - without any entrance nor output; I - with one keyboard input available; O - the O letter indicates a device with one display." )
def connect( server, port, user, password, typeDevice ):
  """
    Start device and connect it to the platform.
  """
  client = mqtt.Client()  
  if ( typeDevice == "noIO" ):

    client.on_connect = on_connect_noIO   
  elif ( typeDevice == "I" ):

    client.on_connect = on_connect_I
  else: # typeDevice == O

    client.on_connect = on_connect_O

  client.on_message = on_message
  client.username_pw_set( KEY_ID, KEY_SECRET )
  client.connect( server, port, 60 )

  client.loop_start()

  while True:

    client.publish( REGISTRATION_TOPIC, "Hello World!", 1 )
    time.sleep(20)
    # TODO: Wait till key to cypher is negotiated.


if __name__ == '__main__':
  
  connect()