from django.db import migrations


def backfill(apps, schema_editor):
    """Move the old one-product-per-order data into OrderItem and fill new Order fields."""
    import secrets

    Order = apps.get_model('shop', 'Order')
    OrderItem = apps.get_model('shop', 'OrderItem')

    used = set()
    for order in Order.objects.select_related('customer', 'product').all():
        number = 'TM' + secrets.token_hex(4).upper()
        while number in used:
            number = 'TM' + secrets.token_hex(4).upper()
        used.add(number)

        order.order_number = number
        order.delivery_address = order.customer.address
        order.subtotal = order.total_price
        order.save(update_fields=['order_number', 'delivery_address', 'subtotal'])

        qty = order.quantity or 1
        OrderItem.objects.create(
            order=order,
            product=order.product,
            product_name=order.product.name if order.product_id else 'Deleted product',
            unit_price=order.total_price / qty,
            quantity=qty,
            line_total=order.total_price,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_order_items_and_specs'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
