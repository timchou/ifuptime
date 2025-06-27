
from monitoring.models import MonitorLog

def recent_monitor_logs(request):
    if request.user.is_authenticated:
        # Get latest 5 monitor logs for the current user's monitors
        logs = MonitorLog.objects.filter(monitor__user=request.user).order_by('-timestamp')[:5]
        return {'recent_monitor_logs': logs}
    return {'recent_monitor_logs': []}
