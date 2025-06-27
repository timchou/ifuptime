import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
from .models import Monitor, HttpMonitor, KeywordMonitor, ApiMonitor, MonitorLog, SslMonitor
from django.conf import settings
import redis
import os
import socket
import ssl
from OpenSSL import crypto # Correct import for crypto
import OpenSSL.SSL # For OpenSSL.SSL.Error

# Initialize Redis client
redis_client = redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

async def get_ssl_certificate_info(hostname, port=443):
    context = ssl.create_default_context()
    reader = None
    writer = None
    try:
        # Use asyncio.open_connection with ssl=context to perform TLS handshake
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port, ssl=context),
            timeout=10
        )
        
        # Get the SSL object from the writer's extra info
        ssl_object = writer.get_extra_info('ssl_object')
        if not ssl_object:
            raise ValueError("SSL handshake failed or no SSL object found.")

        # Get the peer certificate in binary form
        # getpeercert(binary_form=True) returns the DER encoded certificate
        der_cert = ssl_object.getpeercert(binary_form=True)
        
        # Load the certificate using pyOpenSSL
        x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, der_cert)

        # Get expiration date
        not_after_bytes = x509.get_notAfter()
        not_after_str = not_after_bytes.decode('utf-8')
        # Example format: 20250625120000Z
        valid_to = datetime.strptime(not_after_str, '%Y%m%d%H%M%SZ')

        # Calculate days remaining
        days_remaining = (valid_to - datetime.now()).days

        return {
            'valid_to': valid_to,
            'days_remaining': days_remaining,
            'error': None
        }
    except (ssl.SSLError, ConnectionRefusedError, asyncio.TimeoutError, OpenSSL.SSL.Error, ValueError) as e:
        return {
            'valid_to': None,
            'days_remaining': None,
            'error': str(e)
        }
    except Exception as e:
        return {
            'valid_to': None,
            'days_remaining': None,
            'error': f"An unexpected error occurred: {e}"
        }
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()

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
    ssl_valid_to = None
    ssl_days_remaining = None
    ssl_error = None

    # Get node name from environment variable
    node_name = os.environ.get('MONITORING_NODE_NAME', 'unknown_node')

    try:
        if monitor.monitor_type == 'http':
            http_monitor = await HttpMonitor.objects.aget(monitor=monitor)
            async with aiohttp.ClientSession() as session:
                start_time = datetime.now()
                response = await session.get(monitor.target, timeout=aiohttp.ClientTimeout(total=10))
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                status_code = response.status
                is_up = (status_code == http_monitor.expected_status_code)

        elif monitor.monitor_type == 'keyword':
            keyword_monitor = await KeywordMonitor.objects.aget(monitor=monitor)
            async with aiohttp.ClientSession() as session:
                start_time = datetime.now()
                response = await session.get(monitor.target, timeout=aiohttp.ClientTimeout(total=10))
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                status_code = response.status
                response_content = await response.text()
                is_up = (status_code == keyword_monitor.expected_status_code and keyword_monitor.keyword in response_content)

        elif monitor.monitor_type == 'api':
            api_monitor = await ApiMonitor.objects.aget(monitor=monitor)
            headers = {} if not api_monitor.headers else json.loads(api_monitor.headers)
            body_data = {} if not api_monitor.body_data else json.loads(api_monitor.body_data)

            async with aiohttp.ClientSession() as session:
                start_time = datetime.now()
                if api_monitor.method == 'GET':
                    response = await session.get(monitor.target, headers=headers, timeout=aiohttp.ClientTimeout(total=10))
                elif api_monitor.method == 'POST':
                    response = await session.post(monitor.target, headers=headers, json=body_data, timeout=aiohttp.ClientTimeout(total=10))
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000 # milliseconds
                status_code = response.status
                response_content = await response.text()

            status_code_match = (status_code == api_monitor.expected_status_code)
            keyword_match = True
            if api_monitor.response_keyword:
                keyword_match = (api_monitor.response_keyword in response_content)
            is_up = (status_code_match and keyword_match)

        elif monitor.monitor_type == 'ssl':
            # Extract hostname from target URL
            from urllib.parse import urlparse
            parsed_url = urlparse(monitor.target)
            hostname = parsed_url.hostname
            if not hostname:
                raise ValueError("Invalid URL for SSL monitoring: No hostname found.")

            ssl_info = await get_ssl_certificate_info(hostname)
            ssl_valid_to = ssl_info['valid_to']
            ssl_days_remaining = ssl_info['days_remaining']
            ssl_error = ssl_info['error']

            if ssl_error:
                is_up = False # SSL check failed
            elif ssl_days_remaining is not None and ssl_days_remaining < 7: # Less than 7 days remaining
                is_up = False # Consider it down for alert purposes
            else:
                is_up = True # SSL certificate is valid and has enough time remaining

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
        'node_name': node_name,
        'ssl_valid_to': ssl_valid_to.isoformat() if ssl_valid_to else None,
        'ssl_days_remaining': ssl_days_remaining,
        'ssl_error': ssl_error
    }
    redis_client.rpush('monitor_logs_queue', json.dumps(log_data))
    print(f"Monitor {monitor.name} check completed. Status: {'Up' if is_up else 'Down'}. Log pushed to Redis from {node_name}.")