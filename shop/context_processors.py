def cart(request):
    """Expose the cart item count to every template (used by the navbar badge)."""
    cart_data = request.session.get('cart', {})
    try:
        count = sum(int(q) for q in cart_data.values())
    except (TypeError, ValueError):
        count = 0
    return {'cart_count': count}
