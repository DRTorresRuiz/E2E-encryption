import paho.mqtt.client as mqtt
from datetime import datetime
import click
import json
import time

client_id  = "123134"
connection_process = True
msg_2 = False
msg_4 = False

def on_message( client, userdata, msg ):
    global client_id
    global connection_process
    global msg_2, msg_4

    if msg.topic == "register":
        received_message = json.loads( msg.payload )

        if received_message.get( "id", "" ) != client_id:

            if received_message.get("msg", 0) == 2:
                print( msg.topic, " - ", msg.payload )
                new_message={
                    "id": client_id,
                    "msg": 3
                }
                client.publish( "register", json.dumps( new_message ) )
                msg_2 = True
            elif msg_2 and received_message.get("msg", 0) == 4:
                print( msg.topic, " - ", msg.payload )
                new_message={
                    "id": client_id,
                    "msg": 5
                }
                client.publish( "register", json.dumps( new_message ) )
                connection_process=False
            
client = mqtt.Client( client_id=client_id)  
client.on_message = on_message
client.username_pw_set( "device-IoT", "deviceMUII" )
client.connect( "broker.shiftr.io", 1883, 60 )
client.loop_start()

new_message={
    "id": client_id,
    "msg": 1
}
client.publish( "register", json.dumps( new_message ) )

now = datetime.now()
difference = 0
client.subscribe( "register" )
while connection_process and difference < 120:

    difference = ( datetime.now() - now ).total_seconds()
    time.sleep( 1 )
client.unsubscribe( "register" )
print( "CONNECTED" )
