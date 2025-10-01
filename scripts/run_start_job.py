#!/usr/bin/env python3
import requests, time, sys

url = 'http://127.0.0.1:5000/start_job'
payload = {'wallet_address': '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3', 'networks': ['arbitrum']}
print('Posting to', url, payload)
try:
    r = requests.post(url, json=payload, timeout=10)
except Exception as e:
    print('Failed to POST /start_job:', e)
    sys.exit(2)
print('Status', r.status_code)
print(r.text)
if r.status_code != 200:
    sys.exit(1)
job_id = r.json().get('job_id')
print('job_id', job_id)
status_url = f'http://127.0.0.1:5000/job_status/{job_id}'
start = time.time()
while True:
    try:
        sr = requests.get(status_url, timeout=10)
    except Exception as e:
        print('Failed to GET job_status:', e)
        time.sleep(2)
        continue
    if sr.status_code != 200:
        print('job_status returned', sr.status_code, sr.text)
        time.sleep(2)
        continue
    s = sr.json()
    print('status', s.get('status'), 'progress', s.get('progress'))
    if s.get('status') in ('completed','failed'):
        print('final', s)
        break
    if time.time() - start > 600:
        print('Timed out waiting for job to complete')
        break
    time.sleep(3)
