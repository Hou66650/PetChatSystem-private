"""Rodin Gen-2.5 transport. Never retry a paid submission automatically."""
import ipaddress
import json
import math
import os
import socket
from urllib.parse import urlsplit

import requests

BASE = 'https://api.hyper3d.com/api/v2/'
FORM = dict(tier='Gen-2.5-High', mesh_mode='Raw', quality_override='100000',
            geometry_file_format='glb', material='PBR', texture_mode='high')
LABELS = {'front':'F', 'left':'L', 'right':'R', 'back':'B'}


def call(action, payload):
    if action not in ('rodin', 'status', 'download'):
        raise ValueError('Unknown Rodin operation')
    with requests.Session() as session:
        session.trust_env = False
        kwargs = {'json': payload}
        if action == 'rodin':
            views = [(slot, payload[slot]) for slot in LABELS if slot in payload]
            kwargs = dict(data={**FORM, 'image_label': json.dumps([LABELS[s] for s, _ in views])},
                          files=[('images', (slot+'.jpg', raw, 'image/jpeg')) for slot, raw in views])
        response = session.post(BASE+action,
            headers={'Authorization':'Bearer '+os.environ['RODIN_API_KEY'].strip()},
            timeout=(15, 120 if action == 'rodin' else 45), allow_redirects=False, **kwargs)
        value = response.json()
        if not isinstance(value, dict): raise ValueError('Invalid Rodin response')
        return response.status_code, value


def credit(value):
    return value if type(value) in (float, int) and math.isfinite(value) and value >= 0 else None


def accepted(code, value):
    """Both identifiers are required; a partial receipt is uncertain, not retryable."""
    jobs = value.get('jobs')
    return (code in (200, 201) and not value.get('error')
            and isinstance(value.get('uuid'), str) and bool(value['uuid'])
            and isinstance(jobs, dict) and isinstance(jobs.get('subscription_key'), str)
            and bool(jobs['subscription_key']))


def download(url):
    # The authenticated download endpoint may return different storage providers.
    # Only public HTTPS endpoints; reject credentials, redirects and local networks.
    parts = urlsplit(url)
    if (parts.scheme != 'https' or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.port not in (None, 443)):
        raise ValueError('Unexpected Rodin download URL')
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Non-public Rodin download host')
    with requests.Session() as session:
        session.trust_env = False
        # API Authorization is intentionally not sent to the storage server.
        with session.get(url, stream=True, timeout=(15, 120), allow_redirects=False) as response:
            if response.status_code != 200: raise ValueError('Rodin download failed')
            chunks = []; count = 0
            for chunk in response.iter_content(1024*1024):
                count += len(chunk)
                if count > 80*1024*1024: raise ValueError('GLB too large')
                chunks.append(chunk)
    return b''.join(chunks)
