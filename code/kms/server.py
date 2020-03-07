#!flask/bin/python
import paho.mqtt.client as mqtt
from flask import Flask
import threading
import click
import time

KEY_ID = "keyManagementSystem"
KEY_SECRET = "KMS-MUII"

topicsPublishNewKeys = []
secretRegisteredDevices = []

app = Flask(__name__)
 
class FlaskThread( threading.Thread ):

    @app.route('/')
    def index():

        return "{ \"Hello\": \"World!\" }"

    # TODO: Add new Registered Device

    def run( self ):
        app.run()

def on_connect(client, userdata, flags, rc):

  print( "KMS is ready to work." )
  print( "Connected with result code " + str( rc ) )

def on_message( client, userdata, msg ):

  print( msg.topic + " " + str( msg.payload ))

@click.command()
@click.option( '-s', '--server', 'server', required=True, type=str, show_default=True, default='broker.shiftr.io', help="The MQTT Server to send keys." )
@click.option( '-p', '--port', 'port', required=True, type=int, show_default=True, default=1883, help="Port of theMQTT Server to send keys." )
def connect( server, port ):
    """
        Start KMS.
    """
    flaskThread = FlaskThread()
    flaskThread.daemon = True # Need to be a daemon to close it with Ctrl+C
    flaskThread.start()
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set( KEY_ID, KEY_SECRET )
    client.connect( server, port, 60 )

    client.loop_start()
    
    while True:    
        # TODO: Reset keys after a while for each device
        client.publish( "KEYS", "HEY, I'M A KEY", 2 ) # TODO: Publish in different topics
        time.sleep(30)

if __name__ == '__main__':
    connect()
   