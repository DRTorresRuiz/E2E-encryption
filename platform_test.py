import paho.mqtt.client as mqtt
from datetime import datetime
import click
import json
import time

client_id = "kktua"
connection_process = True
msg_1 = False
msg_3 = False

def on_message( client, userdata, msg ):
    global client_id
    global connection_process
    global msg_1, msg_3

    if msg.topic == "register":
        received_message = json.loads( msg.payload )

        if received_message.get( "id", "" ) != client_id:
             
            if received_message.get("msg", 0) == 1:
                print( msg.topic, " - ", msg.payload )
                new_message={
                    "id": client_id,
                    "msg": 2
                }
                msg_1 = True
                client.publish( "register", json.dumps( new_message ) )
            elif msg_1 and received_message.get("msg", 0) == 3:
                print( msg.topic, " - ", msg.payload )
                new_message={
                    "id": client_id,
                    "msg": 4
                }
                client.publish( "register", json.dumps( new_message ) )
                msg_3 = True
            elif msg_3 and received_message.get("msg", 0) == 5:
                print( msg.topic, " - ", msg.payload )
                connection_process=False

client = mqtt.Client( client_id=client_id )  
client.on_message = on_message
client.username_pw_set( "platform", "platform-MUII" )
client.connect( "broker.shiftr.io", 1883, 60 )
client.loop_start()

now = datetime.now()
difference = 0
client.subscribe( "register" )
while connection_process and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )
client.unsubscribe( "register" )
print( "CONNECTED" )