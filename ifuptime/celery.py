
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ifuptime.settings')

app = Celery('ifuptime')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

app.conf.beat_schedule = {
    'batch-save-monitor-logs-every-30-seconds': {
        'task': 'monitoring.tasks.batch_save_monitor_logs',
        'schedule': 30.0, # Run every 30 seconds
    },
    'clean-old-monitor-logs-daily': {
        'task': 'monitoring.tasks.clean_old_monitor_logs',
        'schedule': crontab(hour=0, minute=0), # Run daily at midnight
    },
    'send-heartbeat-every-minute': {
        'task': 'monitoring.tasks.send_heartbeat',
        'schedule': crontab(minute='*/1'), # Run every minute
    },
    'send-daily-report-emails-early-morning': {
        'task': 'monitoring.tasks.send_daily_report_emails',
        'schedule': crontab(hour=1, minute=0), # Run daily at 1 AM
    },
}
