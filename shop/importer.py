"""Bulk add or update products from a CSV file (save your Excel sheet as 'CSV UTF-8')."""
import csv
import io
import os
import zipfile
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image

from .models import Category, Product

MAX_ROWS = 2000
MAX_BYTES = 2 * 1024 * 1024
MAX_ZIP_BYTES = 40 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 400
IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp')

COLUMNS = [
    'name', 'category', 'brand', 'price', 'discount_percent', 'quantity', 'condition', 'warranty_months',
    'sku', 'short_description', 'description', 'highlights', 'ram', 'storage', 'display', 'processor',
    'battery', 'charging', 'camera', 'os', 'network', 'sim', 'color', 'extra_specs', 'in_the_box', 'faq',
    'ai_notes', 'image',
]
MULTILINE = {'highlights', 'extra_specs', 'in_the_box', 'faq'}
TEXT = ['brand', 'sku', 'short_description', 'description', 'ram', 'storage', 'display', 'processor', 'battery',
        'charging', 'camera', 'os', 'network', 'sim', 'color', 'ai_notes']

SAMPLE = [
    ['Samsung Galaxy A55 5G', 'Mobile Phones', 'Samsung', '54990', '5', '12', 'new', '12', 'SKU-A55',
     'Premium mid-range phone', 'Longer description here.', '120Hz AMOLED|50MP OIS camera|IP67', '8GB', '256GB',
     '6.6-inch Super AMOLED', 'Exynos 1480', '5000 mAh', '25W', '50MP + 12MP + 5MP', 'Android 14', '5G',
     'Dual SIM', 'Navy', 'Weight: 213 g|IP67 water resistant', 'Phone|USB cable|SIM tool',
     'Q: Is it original?|A: Yes, with warranty.', 'Good for Samsung fans on a mid-range budget.', 'samsung-a55.png'],
]


def _lines(value):
    value = value.replace('\r', '')
    if '|' in value:
        parts = [p.strip() for p in value.split('|') if p.strip()]
        return '\n'.join(parts)
    return value.strip()


def _faq(value):
    text = _lines(value)
    out = []
    for line in text.splitlines():
        if line.lower().startswith('q:') and out:
            out.append('')
        out.append(line)
    return '\n'.join(out)


def _decimal(value, field):
    try:
        number = Decimal(value.replace(',', '').replace('Tk', '').replace('৳', '').strip())
    except InvalidOperation:
        raise ValueError(f"{field} must be a number")
    if number < 0:
        raise ValueError(f"{field} cannot be negative")
    return number


def _int(value, field):
    try:
        number = int(Decimal(value.replace(',', '').strip()))
    except InvalidOperation:
        raise ValueError(f"{field} must be a whole number")
    if number < 0:
        raise ValueError(f"{field} cannot be negative")
    return number


def sample_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    writer.writerows(SAMPLE)
    return '﻿' + out.getvalue()


def read_images_zip(uploaded):
    """Read a ZIP of pictures into {lowercase file name: bytes}. Returns (images, errors)."""
    images, errors = {}, []
    raw = uploaded.read(MAX_ZIP_BYTES + 1)
    if len(raw) > MAX_ZIP_BYTES:
        return {}, ["The pictures ZIP is bigger than 40 MB."]
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return {}, ["The pictures file is not a valid ZIP."]
    for info in archive.infolist():
        name = os.path.basename(info.filename)
        if info.is_dir() or not name or name.startswith('.') or not name.lower().endswith(IMAGE_EXT):
            continue
        if len(images) >= MAX_IMAGES:
            errors.append(f"Only the first {MAX_IMAGES} pictures were read.")
            break
        if info.file_size > MAX_IMAGE_BYTES:
            errors.append(f"Picture {name} is bigger than 5 MB and was skipped.")
            continue
        data = archive.read(info)
        try:
            Image.open(io.BytesIO(data)).verify()
        except Exception:
            errors.append(f"Picture {name} is not a valid image and was skipped.")
            continue
        images[name.lower()] = data
    return images, errors


def import_products(uploaded, images=None):
    """Returns (created, updated, errors). Rows with a problem are skipped and reported.

    `images` is the {file name: bytes} dict from read_images_zip; a row's 'image' column names the file.
    """
    images = images or {}
    raw = uploaded.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return 0, 0, ["The file is bigger than 2 MB."]
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return 0, 0, ["Please save the file as 'CSV UTF-8' and try again."]
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return 0, 0, ["The file is empty."]
    reader.fieldnames = [(h or '').strip().lower() for h in reader.fieldnames]
    if 'name' not in reader.fieldnames:
        return 0, 0, ["The first row must contain column names, including 'name'."]

    created = updated = 0
    errors = []
    for number, row in enumerate(reader, start=2):
        if number - 1 > MAX_ROWS:
            errors.append(f"Stopped after {MAX_ROWS} rows.")
            break
        row = {k: (v or '').strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue
        name = row.get('name', '')
        if not name:
            errors.append(f"Row {number}: name is missing.")
            continue
        try:
            with transaction.atomic():
                product = None
                if row.get('sku'):
                    product = Product.objects.filter(sku=row['sku']).first()
                if product is None:
                    product = Product.objects.filter(name__iexact=name).first()
                is_new = product is None
                if is_new:
                    if not row.get('price'):
                        raise ValueError("price is required for a new product")
                    product = Product(name=name, price=Decimal('0'))
                product.name = name
                if row.get('price'):
                    product.price = _decimal(row['price'], 'price')
                if row.get('discount_percent'):
                    value = _int(row['discount_percent'], 'discount_percent')
                    if value > 100:
                        raise ValueError("discount_percent cannot be more than 100")
                    product.discount_percent = value
                if row.get('quantity'):
                    product.quantity = _int(row['quantity'], 'quantity')
                if row.get('warranty_months'):
                    product.warranty_months = _int(row['warranty_months'], 'warranty_months')
                if row.get('condition'):
                    cond = row['condition'].lower()
                    if cond not in dict(Product.CONDITION_CHOICES):
                        raise ValueError("condition must be new, used or refurbished")
                    product.condition = cond
                if row.get('category'):
                    product.category = (Category.objects.filter(name__iexact=row['category']).first()
                                        or Category.objects.create(name=row['category'][:100]))
                for field in TEXT:
                    if row.get(field):
                        setattr(product, field, row[field])
                for field in MULTILINE:
                    if row.get(field):
                        setattr(product, field, _faq(row[field]) if field == 'faq' else _lines(row[field]))
                product.full_clean(exclude=['image'])
                product.save()
                wanted = os.path.basename(row.get('image', '')).lower()
                if wanted:
                    if wanted in images:
                        product.image.save(wanted, ContentFile(images[wanted]), save=True)
                    else:
                        errors.append(f"Row {number} ({name}): picture '{wanted}' was not found in the pictures ZIP (product saved without it).")
            created += is_new
            updated += not is_new
        except Exception as exc:   # one bad row must not stop the rest
            message = '; '.join(getattr(exc, 'messages', [str(exc)]))
            errors.append(f"Row {number} ({name}): {message}")
    return created, updated, errors
