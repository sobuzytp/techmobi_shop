"""Push the whole product catalogue to the aijobab assistant.

    python manage.py sync_catalog --dry-run     # print what would be sent
    python manage.py sync_catalog               # send it

Configured with AIJOBAB_SYNC_URL / AIJOBAB_API_KEY (and optionally AIJOBAB_AUTH_HEADER)
in the environment. The payload is {"source", "shop", "products": [...]} - the same
product objects the public API returns.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from shop.api import filtered_products, serialize_product
from shop.models import ShopSettings, SyncState

SYNC_NAME = 'aijobab'


class _BaseUrl:
    """Stands in for a request so links are built from the public site address."""
    def __init__(self, base):
        self.base = base

    def build_absolute_uri(self, path):
        return self.base + path


def build_payload(base_url):
    request = _BaseUrl(base_url)
    s = ShopSettings.load()
    return {
        'source': 'techmobi',
        'shop': {'phone': s.shop_phone, 'whatsapp': s.whatsapp_number,
                 'address': s.shop_address, 'opening_hours': s.opening_hours,
                 'payment_methods': ['Cash on Delivery']},
        'products': [serialize_product(p, request) for p in filtered_products({})],
    }


class Command(BaseCommand):
    help = "Send the product catalogue to the aijobab assistant."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Print the payload instead of sending it.")
        parser.add_argument('--site-url', default='https://tech-mobi.notte.top',
                            help="Public address used to build product and image links.")

    def handle(self, *args, **opts):
        payload = build_payload(opts['site_url'].rstrip('/'))
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        if opts['dry_run']:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            self.stderr.write(f"[dry run] {len(payload['products'])} products, {len(body)} bytes - nothing sent.")
            return
        url, key = settings.AIJOBAB_SYNC_URL, settings.AIJOBAB_API_KEY
        if not url or not key:
            raise CommandError("Set AIJOBAB_SYNC_URL and AIJOBAB_API_KEY in the environment first.")
        if not url.startswith('https://'):
            raise CommandError("AIJOBAB_SYNC_URL must start with https://")
        header = settings.AIJOBAB_AUTH_HEADER
        value = f"Bearer {key}" if header.lower() == 'authorization' else key
        req = urllib.request.Request(url, data=body, method='POST', headers={
            'Content-Type': 'application/json; charset=utf-8', header: value})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = f"OK {resp.status}, {len(payload['products'])} products"
        except urllib.error.HTTPError as exc:
            result = f"FAILED HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError) as exc:
            result = f"FAILED {exc}"
        SyncState.objects.update_or_create(
            name=SYNC_NAME, defaults={'last_synced_at': timezone.now(), 'last_result': result[:300]})
        if result.startswith('FAILED'):
            raise CommandError(result)
        self.stdout.write(self.style.SUCCESS(result))
