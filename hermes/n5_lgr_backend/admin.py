from django.contrib import admin
from .models import TestDevice, TestSerialData

admin.site.register(TestDevice)
admin.site.register(TestSerialData)
