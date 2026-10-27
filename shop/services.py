"""Business rules that are shared by the admin, staff pages and customer views."""
from django.db import transaction
from django.db.models import F

from .models import Order, Product


def restore_stock(order):
    """Give the stock of a cancelled order back to the products. Safe to call twice."""
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.stock_restored:
            return False
        for item in locked.items.all():
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(quantity=F('quantity') + item.quantity)
        Order.objects.filter(pk=order.pk).update(stock_restored=True)
    order.stock_restored = True
    return True


def apply_status(order, new_status):
    """Move an order to `new_status`. Returns (changed, error_message).

    - Cancelling gives the stock back.
    - A cancelled order cannot be re-opened (the stock was already given back); place a new order instead.
    """
    if new_status == order.status:
        return False, ''
    if order.status == 'cancelled':
        return False, f"Order {order.order_number} is cancelled and cannot be re-opened."
    with transaction.atomic():
        order.status = new_status
        order.save(update_fields=['status'])
        if new_status == 'cancelled':
            restore_stock(order)
    return True, ''
