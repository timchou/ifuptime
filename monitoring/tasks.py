from celery import shared_task
import asyncio
import json
from django.conf import settings
import redis
from .models import MonitorLog, Monitor, Node
from datetime import timedelta
from django.utils import timezone
import os
import socket
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Import run_monitor_check_async locally within the task to avoid circular import
# from .utils import run_monitor_check_async # REMOVED TO AVOID CIRCULAR IMPORT

# Initialize Redis client
redis_client = redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

@shared_task
def perform_monitor_check(monitor_id):
    # Import run_monitor_check_async here to avoid circular dependency
    from .utils import run_monitor_check_async
    asyncio.run(run_monitor_check_async(monitor_id))

@shared_task
def batch_save_monitor_logs():
    print("Starting batch save of monitor logs...")
    logs_to_save = []
    while True:
        # Pop up to 100 logs from the queue at a time
        log_json = redis_client.lpop('monitor_logs_queue')
        if not log_json:
            break
        log_data = json.loads(log_json)
        logs_to_save.append(log_data)

        if len(logs_to_save) >= 100: # Batch size
            break

    if logs_to_save:
        monitor_logs_to_create = []
        for log_data in logs_to_save:
            try:
                monitor = Monitor.objects.get(id=log_data['monitor_id'])
                monitor_logs_to_create.append(MonitorLog(
                    monitor=monitor,
                    node_name=log_data.get('node_name'),
                    timestamp=log_data['timestamp'],
                    is_up=log_data['is_up'],
                    response_time=log_data['response_time'],
                    status_code=log_data['status_code'],
                    response_content=log_data['response_content']
                ))
            except Monitor.DoesNotExist:
                print(f"Monitor with ID {log_data['monitor_id']} not found for log entry.")

        if monitor_logs_to_create:
            # Bulk create logs
            created_logs = MonitorLog.objects.bulk_create(monitor_logs_to_create)
            print(f"Successfully saved {len(created_logs)} monitor logs in batch.")

            # Check for new down events and send emails
            for log in created_logs:
                if not log.is_up:
                    # Check previous log to see if it was up
                    previous_log = MonitorLog.objects.filter(
                        monitor=log.monitor,
                        timestamp__lt=log.timestamp
                    ).order_by('-timestamp').first()

                    if previous_log is None or previous_log.is_up: # Only send if it's a new down event
                        send_monitor_down_email.delay(log.monitor.id, log.id)
                        print(f"Triggered email for new down event: {log.monitor.name}")
    else:
        print("No monitor logs to save.")

@shared_task
def clean_old_monitor_logs():
    # Keep logs for the last 30 days
    cutoff_date = timezone.now() - timedelta(days=30)
    old_logs = MonitorLog.objects.filter(timestamp__lt=cutoff_date)
    deleted_count, _ = old_logs.delete()
    print(f"Cleaned {deleted_count} old monitor logs.")

@shared_task
def send_heartbeat():
    node_name = os.environ.get('MONITORING_NODE_NAME')
    node_location = os.environ.get('MONITORING_NODE_LOCATION', '')
    if not node_name:
        print("MONITORING_NODE_NAME environment variable not set. Skipping heartbeat.")
        return

    try:
        node, created = Node.objects.get_or_create(name=node_name)
        node.last_heartbeat = timezone.now()
        node.location = node_location
        # Attempt to get IP address (might not work in all Docker setups)
        try:
            node.ip_address = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            node.ip_address = None
        node.save()
        print(f"Heartbeat sent from node: {node_name}")
    except Exception as e:
        print(f"Error sending heartbeat from node {node_name}: {e}")

@shared_task
def send_monitor_down_email(monitor_id, log_id):
    try:
        monitor = Monitor.objects.get(id=monitor_id)
        log = MonitorLog.objects.get(id=log_id)
        user = monitor.user

        subject = f"Monitor Alert: {monitor.name} is Down!"
        from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@ifuptime.com'
        to_email = user.email

        context = {
            'monitor': monitor,
            'log': log,
            'user': user,
            'site_url': 'http://ifuptime.com', # Replace with your actual site URL
            'current_year': datetime.now().year,
        }

        html_content = render_to_string('email/monitor_down_notification.html', context)
        text_content = strip_tags(html_content) # Fallback for plain-text clients

        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        print(f"Sent downtime notification email for {monitor.name} to {user.email}")

    except Monitor.DoesNotExist:
        print(f"Monitor {monitor_id} not found for email notification.")
    except MonitorLog.DoesNotExist:
        print(f"MonitorLog {log_id} not found for email notification.")
    except Exception as e:
        print(f"Error sending email for monitor {monitor_id}: {e}")