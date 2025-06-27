import aiohttp
import asyncio
import json
from datetime import datetime
from .models import Monitor, HttpMonitor, KeywordMonitor, ApiMonitor, MonitorLog
from django.conf import settings
import redis
import os
import socket

# Initialize Redis client
redis_client = redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

async def run_monitor_check_async(monitor_id):
    try:
        monitor = await Monitor.objects.aget(id=monitor_id)
    except Monitor.DoesNotExist:
        print(f"Monitor with ID {monitor_id} does not exist.")
        return

    is_up = False
    response_time = 0.0
    status_code = None
    response_content = None

    # Get node name from environment variable
    node_name = os.environ.get('MONITORING_NODE_NAME', 'unknown_node')

    try:
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            if monitor.monitor_type == 'http':
                http_monitor = await HttpMonitor.objects.aget(monitor=monitor)
                async with session.get(monitor.target, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                    status_code = response.status
                    is_up = (status_code == http_monitor.expected_status_code)

            elif monitor.monitor_type == 'keyword':
                keyword_monitor = await KeywordMonitor.objects.aget(monitor=monitor)
                async with session.get(monitor.target, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                    status_code = response.status
                    response_content = await response.text()
                    is_up = (status_code == keyword_monitor.expected_status_code and keyword_monitor.keyword in response_content)

            elif monitor.monitor_type == 'api':
                api_monitor = await ApiMonitor.objects.aget(monitor=monitor)
                headers = {} if not api_monitor.headers else json.loads(api_monitor.headers)
                body_data = {} if not api_monitor.body_data else json.loads(api_monitor.body_data)

                if api_monitor.method == 'GET':
                    async with session.get(monitor.target, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        end_time = datetime.now()
                        response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                        status_code = response.status
                        response_content = await response.text()

                elif api_monitor.method == 'POST':
                    async with session.post(monitor.target, headers=headers, json=body_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        end_time = datetime.now()
                        response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                        status_code = response.status
                        response_content = await response.text()

                status_code_match = (status_code == api_monitor.expected_status_code)
                keyword_match = True
                if api_monitor.response_keyword:
                    keyword_match = (api_monitor.response_keyword in response_content)
                is_up = (status_code_match and keyword_match)

    except aiohttp.ClientError as e:
        print(f"Request failed for monitor {monitor.name}: {e}")
        is_up = False
    except json.JSONDecodeError as e:
        print(f"JSON decode error for monitor {monitor.name}: {e}")
        is_up = False
    except Exception as e:
        print(f"An unexpected error occurred for monitor {monitor.name}: {e}")
        is_up = False

    # Prepare log data and push to Redis list for batch processing
    log_data = {
        'monitor_id': monitor.id,
        'timestamp': datetime.now().isoformat(),
        'is_up': is_up,
        'response_time': response_time,
        'status_code': status_code,
        'response_content': response_content,
        'node_name': node_name # Add node name to log data
    }
    redis_client.rpush('monitor_logs_queue', json.dumps(log_data))
    print(f"Monitor {monitor.name} check completed. Status: {'Up' if is_up else 'Down'}. Log pushed to Redis from {node_name}.")