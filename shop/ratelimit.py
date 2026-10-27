"""Tiny database-backed rate limiter, so it works across all server processes."""
from datetime import timedelta
from random import random

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ThrottleEntry


def client_ip(request):
    """The visitor's address. Behind a proxy/CDN set DJANGO_CLIENT_IP_HEADER (e.g. HTTP_X_FORWARDED_FOR or
    HTTP_CF_CONNECTING_IP); otherwise REMOTE_ADDR is used. For X-Forwarded-For we take the LAST entry,
    which is the one added by your own proxy and cannot be faked by the visitor."""
    header = getattr(settings, 'CLIENT_IP_HEADER', '') or 'REMOTE_ADDR'
    value = request.META.get(header, '')
    if header == 'HTTP_X_FORWARDED_FOR':
        value = value.split(',')[-1]
    return value.strip() or request.META.get('REMOTE_ADDR') or 'unknown'


def make_key(prefix, value):
    return f"{prefix}:{str(value)[:80]}"


def is_limited(key, limit, window_seconds):
    """True if `key` has already been recorded `limit` times within the window."""
    entry = ThrottleEntry.objects.filter(key=key).first()
    if entry is None or timezone.now() - entry.window_start > timedelta(seconds=window_seconds):
        return False
    return entry.count >= limit


def record(key, window_seconds):
    """Count one attempt for `key`, starting a new window when the old one has passed."""
    now = timezone.now()
    with transaction.atomic():
        entry, created = ThrottleEntry.objects.select_for_update().get_or_create(
            key=key, defaults={'count': 1, 'window_start': now})
        if not created:
            if now - entry.window_start > timedelta(seconds=window_seconds):
                entry.count, entry.window_start = 1, now
            else:
                entry.count += 1
            entry.save(update_fields=['count', 'window_start'])
    if random() < 0.02:  # occasional clean-up of old rows
        ThrottleEntry.objects.filter(window_start__lt=now - timedelta(days=1)).delete()


def reset(key):
    ThrottleEntry.objects.filter(key=key).delete()
