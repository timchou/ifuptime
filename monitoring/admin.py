
from django.contrib import admin
from .models import User, Node, Monitor, HttpMonitor, KeywordMonitor, ApiMonitor, MonitorLog

admin.site.register(User)
admin.site.register(Node)
admin.site.register(Monitor)
admin.site.register(HttpMonitor)
admin.site.register(KeywordMonitor)
admin.site.register(ApiMonitor)
admin.site.register(MonitorLog)
