from .models import Category, Page, ShopSettings, Wishlist


def cart(request):
    """Cart count for the navbar, plus shop contact details and policy links for the footer."""
    cart_data = request.session.get('cart', {})
    try:
        count = sum(int(q) for q in cart_data.values())
    except (TypeError, ValueError):
        count = 0
    return {
        'cart_count': count,
        'shop_settings': ShopSettings.load(),
        'footer_pages': Page.objects.filter(is_published=True).only('slug', 'title'),
        'nav_categories': Category.objects.only('id', 'name'),
        # ids of products the logged-in customer has saved, to fill the heart on product cards
        'wishlist_ids': set(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
        if request.user.is_authenticated else set(),
    }
