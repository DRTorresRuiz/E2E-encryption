from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse



import json
import sys

sys.path.insert(1, r"C:\Users\Fernando\OneDrive\Documentos\Universidad\Máster\Segundo Cuatrimestre\Seguridad\E2E-encryption\code\platform\cli")
import e2e


def home(request):

    listDeviceTopic = {}
    with open(r'../cli/registeredDevices.json') as json_file:
      data = json.load(json_file)
      for p in data:
        listDeviceTopic[p]= data[p]['data_topic']
    return render(request, 'index.html', context={'listDeviceTopic':listDeviceTopic} )

def get_item(dictionary, key):
    return dictionary.get(key)