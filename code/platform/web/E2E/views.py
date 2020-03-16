from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
import paho.mqtt.client as mqtt
from django.utils.datastructures import MultiValueDictKeyError

import sys
sys.path.append('../cli/')
#from ...cli.e2e import register
from e2e import register


import json

CLIENT_ID              = "platform"
server                 = 'broker.shiftr.io/register'
CLIENT_PASS             = "platform-MUII"



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
def registerNewDevice(request):
    register( 'broker.shiftr.io', 1883, 'platform', 'platform-MUII')
         

      
