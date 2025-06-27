from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegisterForm
from django.contrib.auth.decorators import login_required
from .models import Monitor, HttpMonitor, KeywordMonitor, ApiMonitor, MonitorLog, SslMonitor
from .utils import run_monitor_check_async
from .tasks import perform_monitor_check, send_test_email # Import send_test_email
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json
from datetime import datetime
from django.db.models import Q
from django.contrib import messages

def homepage_view(request):
    return render(request, 'homepage.html')

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard') # Redirect to a dashboard page after successful registration
    else:
        form = UserRegisterForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard_view(request):
    monitors = Monitor.objects.filter(user=request.user).order_by('-created_at')
    query = request.GET.get('q')
    if query:
        monitors = monitors.filter(Q(name__icontains=query) | Q(target__icontains=query))

    # Attach last log to each monitor
    for monitor in monitors:
        monitor.last_log = MonitorLog.objects.filter(monitor=monitor).order_by('-timestamp').first()

    context = {
        'monitors': monitors,
        'active_monitor_count': Monitor.objects.filter(user=request.user, is_active=True).count(),
        'max_monitors': request.user.max_monitors,
    }
    return render(request, 'dashboard.html', context)

@login_required
def monitor_create_view(request):
    user = request.user
    active_monitor_count = Monitor.objects.filter(user=user, is_active=True).count()

    if request.method == 'POST':
        # Check monitor limit
        if active_monitor_count >= user.max_monitors:
            messages.error(request, f"You have reached your limit of {user.max_monitors} active monitors.")
            return redirect('monitor_create')

        name = request.POST.get('name')
        monitor_type = request.POST.get('monitor_type')
        target = request.POST.get('target')
        frequency = int(request.POST.get('frequency')) # Convert to int

        # Check frequency limit
        if frequency < user.min_frequency:
            messages.error(request, f"Minimum frequency for your account type is {user.min_frequency / 60} minutes.")
            return redirect('monitor_create')

        monitor = Monitor.objects.create(
            user=request.user,
            name=name,
            monitor_type=monitor_type,
            target=target,
            frequency=frequency
        )

        if monitor_type == 'http':
            expected_status_code = request.POST.get('http_expected_status_code', 200)
            HttpMonitor.objects.create(
                monitor=monitor,
                expected_status_code=expected_status_code
            )
        elif monitor_type == 'keyword':
            keyword = request.POST.get('keyword')
            expected_status_code = request.POST.get('keyword_expected_status_code', 200)
            KeywordMonitor.objects.create(
                monitor=monitor,
                keyword=keyword,
                expected_status_code=expected_status_code
            )
        elif monitor_type == 'api':
            method = request.POST.get('api_method', 'GET')
            headers = request.POST.get('api_headers')
            body_data = request.POST.get('api_body_data')
            expected_status_code = request.POST.get('api_expected_status_code', 200)
            response_keyword = request.POST.get('api_response_keyword')

            # Validate JSON fields
            try:
                if headers: json.loads(headers)
            except json.JSONDecodeError:
                # Handle invalid JSON for headers
                pass # For now, just pass, but in a real app, you'd want to show an error
            try:
                if body_data: json.loads(body_data)
            except json.JSONDecodeError:
                # Handle invalid JSON for body_data
                pass # For now, just pass, but in a real app, you'd want to show an error

            ApiMonitor.objects.create(
                monitor=monitor,
                method=method,
                headers=headers,
                body_data=body_data,
                expected_status_code=expected_status_code,
                response_keyword=response_keyword
            )
        elif monitor_type == 'ssl':
            SslMonitor.objects.create(
                monitor=monitor
            )

        # Schedule the task with Celery Beat
        periodic_task_name = f'Monitor Check for {monitor.name} (ID: {monitor.id})'
        # Check if a task with this name already exists and delete it if so
        try:
            existing_task = PeriodicTask.objects.get(name=periodic_task_name)
            existing_task.delete()
        except PeriodicTask.DoesNotExist:
            pass

        schedule, created = IntervalSchedule.objects.get_or_create(
            every=frequency,
            period=IntervalSchedule.SECONDS,
        )

        PeriodicTask.objects.create(
            interval=schedule, # we set interval here
            name=periodic_task_name,
            task='monitoring.tasks.perform_monitor_check',
            args=json.dumps([monitor.id]),
            start_time=datetime.now()
        )

        return redirect('dashboard')
    context = {
        'min_frequency': user.min_frequency,
        'min_frequency_minutes': user.min_frequency / 60, # Calculate minutes here
        'max_monitors': user.max_monitors,
        'active_monitor_count': active_monitor_count,
    }
    return render(request, 'monitor_create.html', context)

@login_required
def run_check_view(request, monitor_id):
    perform_monitor_check.delay(monitor_id) # Use .delay() for async execution
    return redirect('dashboard')

@login_required
def monitor_detail_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, id=monitor_id, user=request.user)
    monitor_details = None
    if monitor.monitor_type == 'http':
        monitor_details = HttpMonitor.objects.get(monitor=monitor)
    elif monitor.monitor_type == 'keyword':
        monitor_details = KeywordMonitor.objects.get(monitor=monitor)
    elif monitor.monitor_type == 'api':
        monitor_details = ApiMonitor.objects.get(monitor=monitor)
    elif monitor.monitor_type == 'ssl':
        monitor_details = SslMonitor.objects.get(monitor=monitor)

    logs = MonitorLog.objects.filter(monitor=monitor).order_by('-timestamp')[:100] # Get latest 100 logs for chart

    context = {
        'monitor': monitor,
        'monitor_details': monitor_details,
        'logs': logs
    }
    return render(request, 'monitor_detail.html', context)

@login_required
def monitor_edit_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, id=monitor_id, user=request.user)
    monitor_details = None
    if monitor.monitor_type == 'http':
        monitor_details = HttpMonitor.objects.get(monitor=monitor)
    elif monitor.monitor_type == 'keyword':
        monitor_details = KeywordMonitor.objects.get(monitor=monitor)
    elif monitor.monitor_type == 'api':
        monitor_details = ApiMonitor.objects.get(monitor=monitor)
    elif monitor.monitor_type == 'ssl':
        monitor_details = SslMonitor.objects.get(monitor=monitor)

    user = request.user

    if request.method == 'POST':
        monitor.name = request.POST.get('name')
        monitor.target = request.POST.get('target')
        new_frequency = int(request.POST.get('frequency'))

        # Check frequency limit on edit
        if new_frequency < user.min_frequency:
            messages.error(request, f"Minimum frequency for your account type is {user.min_frequency / 60} minutes.")
            return redirect('monitor_edit', monitor_id=monitor.id)

        monitor.frequency = new_frequency
        monitor.is_active = request.POST.get('is_active') == 'on' # Handle checkbox
        monitor.save()

        # No specific fields to save for SslMonitor yet, but keep the structure
        # for future expansion if needed.

        # Update Celery Beat task if frequency changed
        periodic_task = PeriodicTask.objects.get(name=f'Monitor Check for {monitor.name} (ID: {monitor.id})')
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=monitor.frequency,
            period=IntervalSchedule.SECONDS,
        )
        periodic_task.interval = schedule
        periodic_task.enabled = monitor.is_active # Enable/disable task based on is_active
        periodic_task.save()

        return redirect('monitor_detail', monitor_id=monitor.id)

    context = {
        'monitor': monitor,
        'monitor_details': monitor_details,
        'min_frequency': user.min_frequency,
        'min_frequency_minutes': user.min_frequency / 60, # Calculate minutes here
    }
    return render(request, 'monitor_edit.html', context)

@login_required
def monitor_delete_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, id=monitor_id, user=request.user)
    if request.method == 'POST':
        # Delete associated Celery Beat task
        try:
            periodic_task = PeriodicTask.objects.get(name=f'Monitor Check for {monitor.name} (ID: {monitor.id})')
            periodic_task.delete()
        except PeriodicTask.DoesNotExist:
            pass # Task might not exist if it was never scheduled or already deleted

        monitor.delete()
        return redirect('dashboard')
    context = {
        'monitor': monitor
    }
    return render(request, 'monitor_confirm_delete.html', context)

@login_required
def user_settings_view(request):
    user = request.user
    if request.method == 'POST':
        user.is_send_daily_report = request.POST.get('is_send_daily_report') == 'on'
        user.save()
        messages.success(request, "Your settings have been updated successfully!") # Add success message
        return redirect('user_settings')
    context = {
        'user': user
    }
    return render(request, 'user_settings.html', context)

@login_required
def send_test_email_view(request):
    if request.method == 'POST':
        send_test_email.delay(request.user.id)
        messages.info(request, "Test email has been sent. Please check your inbox (and spam folder).")
    return redirect('user_settings')