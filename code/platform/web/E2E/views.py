from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
import paho.mqtt.client as mqtt
from django.utils.datastructures import MultiValueDictKeyError
import asyncio
import threading

import sys
sys.path.append('../cli/')
#from ...cli.e2e import register
from e2e import register,connect_MQTT,getRegisteredDevices,wait_til
import utils as utils


import json

CLIENT_ID              = "platform"
server                 = 'broker.shiftr.io'
CLIENT_PASS             = "platform-MUII"
REGISTRATION_TOPIC      = "/register"
KMS_SERVER_URL         = "http://127.0.0.1:5000/"
HASH_KEY               = b'kkpo-kktua'
REGISTERED_DEVICE_FILE  = "../cli/registeredDevices.json"
encriptor              = None



def home(request):
    return render(request, 'index.html')

def error(request):
    return render(request, 'error.html')      

def platform(request):
    if request.method == "POST":
      username = request.POST.get('inputUsername', False)
      password = request.POST.get('inputPassword', False)
      if username==CLIENT_ID and password == CLIENT_PASS:  
    # validate the received values
        listDeviceTopic = {}
        with open(r'../cli/registeredDevices.json') as json_file:
          data = json.load(json_file)
          for p in data:
            listDeviceTopic[p]= data[p]['data_topic']
        return render(request, 'platform.html', context={'listDeviceTopic':listDeviceTopic} )
      else: 
        return render(request, 'error.html')
    else:
      return render(request, 'platform.html')

def registerNewDevice( request ):
    """
        Allow a new device to connect to your platform.
    """
    newDevice = {}
    connected = asyncio.Semaphore(0)
    request.session['connected'] = connected
    request.session['newDevice']      = newDevice
    
    client = connect_MQTT( 'broker.shiftr.io', 1883, 'platform', 'platform-MUII', 'on_registrationDevice' )
    client.subscribe( REGISTRATION_TOPIC ) 
    connected = request.session.get('connected')
    connected.release()
    wait_til( connected, 120, "Waiting for connecting..." )
    
    client.unsubscribe( REGISTRATION_TOPIC )
    if not connected.locked():
        
        devices = getRegisteredDevices()
        # Add the new registered device.
        with open( REGISTERED_DEVICE_FILE, 'w' ) as file:
      
            devices[newDevice["id"]] = {
                "data_topic": newDevice["data_topic"],
                "type": newDevice["type"],
                "symmetric": newDevice["symmetric"]
            }
            json.dump( devices, file, indent=4 )
        # Registered Devices into KMS
        post_message = {
            # Data information to sent to KMS
            "id": newDevice["id"],
            "key_topic": newDevice["key_topic"],
            "symmetric": newDevice["symmetric"],
            "shared_key": newDevice["shared_key"]
        }
        message = request.post( KMS_SERVER_URL+"register-device", json = post_message, auth=( user, password ) )
        print( "Device successfully added to KMS: ", message.json() )
        print( newDevice.get("id"), " registration completed." )
    else:

        print( "Device registration could not be completed." )
    return render(request, 'platform.html')
  
      
def on_registrationDevice( client, userdata, msg ):
    """
        Method used for the registration process of a device.
    """


def getMessage(request):
    #Method used for decrypt message got by mqtt
    postData = request.POST.get('param', False)
    #postData = request.form
    #json = str(postData['param'].value)
    print(postData)
   # get_message( message, encriptor, HASH_KEY )
    return render(request, 'platform.html')     