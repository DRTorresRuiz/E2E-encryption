from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
import sys


def home(request):

    return render(request, 'index.html', context={} )