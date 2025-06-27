from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Node, Monitor, HttpMonitor, KeywordMonitor, ApiMonitor, MonitorLog, SslMonitor

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('is_send_daily_report', 'user_type')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('is_send_daily_report', 'user_type')}),
    )

admin.site.register(Node)
admin.site.register(Monitor)
admin.site.register(HttpMonitor)
admin.site.register(KeywordMonitor)
admin.site.register(ApiMonitor)
admin.site.register(MonitorLog)
admin.site.register(SslMonitor)