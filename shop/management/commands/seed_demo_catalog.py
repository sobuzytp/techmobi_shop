"""Add ~38 sample products (all categories incl. Laptops and MacBook) in one go.

    python manage.py seed_demo_catalog              # add them (safe to run again - nothing is duplicated)
    python manage.py seed_demo_catalog --no-images  # without placeholder pictures
    python manage.py seed_demo_catalog --remove     # delete the sample products again

Sample products have an SKU starting with DEMO-. Products that already have orders are never deleted.
"""
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from shop.demo_catalog import BOX, ROWS
from shop.models import Category, Product
from shop.placeholders import make_placeholder
from shop.product_seed import COMMON_FAQ


def get_category(name):
    return Category.objects.filter(name__iexact=name).first() or Category.objects.create(name=name)


class Command(BaseCommand):
    help = "Add sample products across all categories (with placeholder pictures)."

    def add_arguments(self, parser):
        parser.add_argument('--no-images', action='store_true', help="Do not create placeholder pictures.")
        parser.add_argument('--remove', action='store_true', help="Delete the DEMO- sample products.")

    def handle(self, *args, **opts):
        if opts['remove']:
            return self.remove()
        created = skipped = 0
        for index, row in enumerate(ROWS, start=1):
            (cat, box, name, brand, price, disc, qty, warranty, cond, ram, storage, display, processor,
             battery, camera, charging, os_, short, highlights, note) = row
            sku = f"DEMO-{index:03d}"
            if Product.objects.filter(sku=sku).exists():
                skipped += 1
                continue
            with transaction.atomic():
                product = Product.objects.create(
                    sku=sku, name=name, brand=brand, category=get_category(cat), price=Decimal(price),
                    discount_percent=disc, quantity=qty, warranty_months=warranty, condition=cond,
                    ram=ram, storage=storage, display=display, processor=processor, battery=battery,
                    camera=camera, charging=charging, os=os_, short_description=short,
                    description=short, highlights=highlights.replace('|', '\n'),
                    in_the_box=BOX[box], faq=COMMON_FAQ, ai_notes=note, is_featured=(index % 7 == 1),
                )
                if not opts['no_images']:
                    png = make_placeholder(name, brand, cat)
                    product.image.save(f"demo-{slugify(name)[:60]}.png", ContentFile(png), save=True)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Added {created} sample products ({skipped} already there)."))
        self.stdout.write("Replace the placeholder pictures and check prices/stock in the admin. "
                          "Remove them later with: python manage.py seed_demo_catalog --remove")

    def remove(self):
        removed = kept = 0
        for product in Product.objects.filter(sku__startswith='DEMO-'):
            if product.order_items.exists():
                kept += 1
                continue
            if product.image:
                product.image.delete(save=False)
            product.delete()
            removed += 1
        self.stdout.write(f"Removed {removed} sample products ({kept} kept because they have orders).")
