import paho.mqtt.client as mqtt
import threading
import click
import time

KEY_ID = "platform"
KEY_SECRET = "platform-MUII"

def on_connect(client, userdata, flags, rc):

  print( "Platform is ready to work." )
  print( "Connected with result code " + str( rc ) )
  client.subscribe( "register" )

def on_message( client, userdata, msg ):
  # TODO: Separate topics.
  print( msg.topic + " " + str( msg.payload ))

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
def connect( server, port ):

  client = mqtt.Client()
  client.on_connect = on_connect
  client.on_message = on_message
  client.username_pw_set( KEY_ID, KEY_SECRET )
  client.connect( server, port, 60 )

  client.loop_start()
  
  while True:    
      # TODO: Reset keys after a while for each device
      # client.publish( "KEYS", "HEY, I'M A KEY", 2 ) # TODO: Publish in different topics
      time.sleep(1)

# TODO: SEPARATE TASKS in commands
# - Register new device
# - List devices
# - Remove devices
# - Select and Read from an specific topic / device
# - Run web platform

if __name__ == '__main__':
  connect()