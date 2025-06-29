
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('normal', 'Normal User'),
        ('pro', 'Pro User'),
    ]
    email = models.EmailField(unique=True)
    is_send_daily_report = models.BooleanField(default=False, help_text="Whether to send daily monitoring reports to this user.")
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='normal', help_text="Type of user, affecting monitoring limits.")
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def max_monitors(self):
        return 200 if self.user_type == 'pro' else 10

    @property
    def min_frequency(self):
        return 300 if self.user_type == 'pro' else 600 # 5 minutes for pro, 10 minutes for normal

class Node(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Unique name for this monitoring node (e.g., Shanghai-Node-01)")
    location = models.CharField(max_length=255, blank=True, null=True, help_text="Geographical location of this node (e.g., Shanghai, Tokyo)")
    last_heartbeat = models.DateTimeField(null=True, blank=True, help_text="Timestamp of the last successful heartbeat from this node.")
    is_active = models.BooleanField(default=False, help_text="Indicates if the node is currently considered active.")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the node.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Update is_active based on last_heartbeat (e.g., within last 5 minutes)
        if self.last_heartbeat and (timezone.now() - self.last_heartbeat).total_seconds() < 300: # 5 minutes
            self.is_active = True
        else:
            self.is_active = False
        super().save(*args, **kwargs)

class Monitor(models.Model):
    MONITOR_TYPE_CHOICES = [
        ('http', 'HTTP(s)存活检测'),
        ('keyword', '关键字检测'),
        ('api', 'API检测'),
        ('ssl', 'SSL证书检测'), # New choice
    ]
    
    FREQUENCY_CHOICES = [
        (300, '5 minutes'),
        (600, '10 minutes'), # New frequency option
        (3600, '1 hour'),
        (43200, '12 hours'),
        (86400, '24 hours'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    monitor_type = models.CharField(max_length=10, choices=MONITOR_TYPE_CHOICES)
    target = models.CharField(max_length=2083) # URL or API endpoint
    frequency = models.PositiveIntegerField(choices=FREQUENCY_CHOICES, default=300) # in seconds
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class HttpMonitor(models.Model):
    monitor = models.OneToOneField(Monitor, on_delete=models.CASCADE, primary_key=True)
    expected_status_code = models.PositiveIntegerField(default=200)

class KeywordMonitor(models.Model):
    monitor = models.OneToOneField(Monitor, on_delete=models.CASCADE, primary_key=True)
    keyword = models.CharField(max_length=255)
    expected_status_code = models.PositiveIntegerField(default=200)

class ApiMonitor(models.Model):
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
    ]
    monitor = models.OneToOneField(Monitor, on_delete=models.CASCADE, primary_key=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='GET')
    headers = models.TextField(blank=True, null=True) # JSON format
    body_data = models.TextField(blank=True, null=True) # JSON format
    expected_status_code = models.PositiveIntegerField(default=200)
    response_keyword = models.CharField(max_length=255, blank=True, null=True)

class SslMonitor(models.Model):
    monitor = models.OneToOneField(Monitor, on_delete=models.CASCADE, primary_key=True)
    # No specific fields needed here for now, as target URL is in Monitor
    # We might add fields like expected_issuer, expected_subject if needed later

class MonitorLog(models.Model):
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE)
    node_name = models.CharField(max_length=255, blank=True, null=True) # New field to store node name
    timestamp = models.DateTimeField(auto_now_add=True)
    is_up = models.BooleanField()
    response_time = models.FloatField() # in milliseconds
    status_code = models.PositiveIntegerField(null=True, blank=True)
    response_content = models.TextField(blank=True, null=True)
    # New fields for SSL monitoring
    ssl_valid_to = models.DateTimeField(null=True, blank=True)
    ssl_days_remaining = models.IntegerField(null=True, blank=True)
    ssl_error = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.monitor.name} - {'Up' if self.is_up else 'Down'} at {self.timestamp}"
