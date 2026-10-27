from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Value
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CheckoutForm, SignupForm, TrackOrderForm
from .models import Category, Customer, Order, OrderItem, Product

CART_SESSION_KEY = 'cart'


# ---------- helpers ----------

def _get_cart(request):
    """Return the session cart as {str(product_id): int(quantity)}, dropping bad entries."""
    raw = request.session.get(CART_SESSION_KEY, {})
    cart = {}
    for key, qty in raw.items():
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if str(key).isdigit() and qty > 0:
            cart[str(key)] = qty
    return cart


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def _cart_items(request):
    """Build cart line items with live product data + totals (one query for all products)."""
    cart = _get_cart(request)
    products = Product.objects.in_bulk([int(pk) for pk in cart])
    items = []
    subtotal = Decimal('0.00')
    for key, qty in cart.items():
        product = products.get(int(key))
        if product is None:
            continue
        unit_price = product.discounted_price
        line_total = unit_price * qty
        subtotal += line_total
        items.append({
            'product': product,
            'quantity': qty,
            'unit_price': unit_price,
            'line_total': line_total,
            'over_stock': qty > product.quantity,
        })
    return items, subtotal


def _safe_next(request, fallback):
    """Return the `next` URL only if it points back to this site."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return fallback


# ---------- pages ----------

def home(request):
    categories = Category.objects.all()
    featured_products = list(Product.objects.filter(is_featured=True)[:8])
    if not featured_products:
        featured_products = list(Product.objects.all()[:8])
    return render(request, 'shop/home.html', {
        'categories': categories,
        'featured_products': featured_products,
    })


SORT_OPTIONS = {
    'newest': ('Newest', ['-created_at']),
    'price_asc': ('Price: Low to High', ['effective_price', '-created_at']),
    'price_desc': ('Price: High to Low', ['-effective_price', '-created_at']),
    'discount': ('Biggest Discount', ['-discount_percent', '-created_at']),
}


def _parse_decimal(value):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        return None
    return number if number.is_finite() and number >= 0 else None


def product_list(request):
    products = Product.objects.select_related('category').annotate(
        effective_price=ExpressionWrapper(
            F('price') * (100 - F('discount_percent')) / Value(100),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(brand__icontains=query))

    category_id = request.GET.get('category', '')
    if category_id.isdigit():
        products = products.filter(category_id=category_id)
    else:
        category_id = ''

    brand = request.GET.get('brand', '').strip()
    if brand:
        products = products.filter(brand__iexact=brand)

    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    if _parse_decimal(min_price) is not None:
        products = products.filter(effective_price__gte=_parse_decimal(min_price))
    else:
        min_price = ''
    if _parse_decimal(max_price) is not None:
        products = products.filter(effective_price__lte=_parse_decimal(max_price))
    else:
        max_price = ''

    sort = request.GET.get('sort', 'newest')
    if sort not in SORT_OPTIONS:
        sort = 'newest'
    products = products.order_by(*SORT_OPTIONS[sort][1])

    page_obj = Paginator(products, settings.PRODUCTS_PER_PAGE).get_page(request.GET.get('page'))

    # Keep every active filter in pagination links (everything except `page`).
    params = request.GET.copy()
    params.pop('page', None)

    brands = (Product.objects.exclude(brand='').order_by('brand')
              .values_list('brand', flat=True).distinct())

    return render(request, 'shop/product_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'brands': brands,
        'query': query,
        'selected_category': category_id,
        'selected_brand': brand,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
        'sort_options': [(key, label) for key, (label, _) in SORT_OPTIONS.items()],
        'querystring': params.urlencode(),
    })


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    related = Product.objects.exclude(pk=product.pk)
    if product.category_id:
        related = related.filter(category_id=product.category_id)
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'gallery': product.gallery.all(),
        'related_products': related[:4],
        'cart_qty': _get_cart(request).get(str(product.pk), 0),
    })


@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = _get_cart(request)
    key = str(pk)
    current = cart.get(key, 0)

    if not product.in_stock:
        messages.error(request, f'"{product.name}" is out of stock.')
    elif current + 1 > product.quantity:
        messages.warning(
            request, f'Only {product.quantity} of "{product.name}" available; you already have {current} in your cart.'
        )
    else:
        cart[key] = current + 1
        _save_cart(request, cart)
        messages.success(request, f'"{product.name}" added to your cart.')

    return redirect(_safe_next(request, reverse('shop:cart')))


@require_POST
def update_cart(request, pk):
    """Increase / decrease / remove a cart line via POST action."""
    cart = _get_cart(request)
    key = str(pk)
    action = request.POST.get('action')

    if key in cart:
        if action == 'increase':
            product = Product.objects.filter(pk=pk).first()
            if product is None:
                del cart[key]
            elif cart[key] + 1 > product.quantity:
                messages.warning(request, f'Only {product.quantity} of "{product.name}" in stock.')
            else:
                cart[key] += 1
        elif action == 'decrease':
            cart[key] -= 1
            if cart[key] <= 0:
                del cart[key]
        elif action == 'remove':
            del cart[key]
        _save_cart(request, cart)
    return redirect('shop:cart')


def cart_view(request):
    items, subtotal = _cart_items(request)
    return render(request, 'shop/cart.html', {
        'items': items,
        'grand_total': subtotal,
        'has_stock_problem': any(i['over_stock'] for i in items),
    })


@login_required
def checkout(request):
    items, subtotal = _cart_items(request)

    if not items:
        messages.info(request, "Your cart is empty. Add some products before checking out.")
        return redirect('shop:product_list')

    if any(i['over_stock'] for i in items):
        messages.warning(request, "Some items in your cart exceed available stock. Please adjust the quantities.")
        return redirect('shop:cart')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = _place_order(request, form)
            if order is not None:
                return redirect('shop:order_success')
            return redirect('shop:cart')
    else:
        form = CheckoutForm(initial=_checkout_initial(request.user))

    delivery_charges = {k: v for k, v in settings.DELIVERY_CHARGES.items()}
    selected_area = form['delivery_area'].value() or 'inside'
    delivery_charge = Order.delivery_charge_for(selected_area)
    return render(request, 'shop/checkout.html', {
        'form': form,
        'items': items,
        'subtotal': subtotal,
        'delivery_charge': delivery_charge,
        'grand_total': subtotal + delivery_charge,
        'delivery_charges': delivery_charges,
    })


def _checkout_initial(user):
    """Prefill the checkout form for logged-in customers from their account and last order."""
    if not user.is_authenticated:
        return {}
    initial = {'name': user.get_full_name() or user.first_name, 'phone': user.username}
    last = user.orders.order_by('-order_date').first()
    if last:
        initial.update(address=last.delivery_address, delivery_area=last.delivery_area)
    return initial


def _place_order(request, form):
    """Create the order atomically, re-checking stock under a row lock.

    Returns the Order, or None if stock changed and the order could not be placed.
    """
    cart = _get_cart(request)
    data = form.cleaned_data

    with transaction.atomic():
        products = Product.objects.select_for_update().in_bulk([int(pk) for pk in cart])

        lines = []
        subtotal = Decimal('0.00')
        for key, qty in cart.items():
            product = products.get(int(key))
            if product is None or qty > product.quantity:
                name = product.name if product else 'An item'
                messages.error(request, f'Sorry, "{name}" no longer has enough stock. Please review your cart.')
                return None
            line_total = product.discounted_price * qty
            subtotal += line_total
            lines.append((product, qty, line_total))

        # One customer record per phone number (older data may contain duplicates).
        customer = Customer.objects.filter(phone=data['phone']).order_by('-id').first()
        if customer is None:
            customer = Customer.objects.create(
                phone=data['phone'], name=data['name'], address=data['address'])
        else:
            customer.name = data['name']
            customer.address = data['address']
            customer.save(update_fields=['name', 'address'])

        delivery_charge = Order.delivery_charge_for(data['delivery_area'])
        order = Order.objects.create(
            customer=customer,
            user=request.user if request.user.is_authenticated else None,
            delivery_address=data['address'],
            delivery_area=data['delivery_area'],
            payment_method=data['payment_method'],
            note=data['note'],
            subtotal=subtotal,
            delivery_charge=delivery_charge,
            total_price=subtotal + delivery_charge,
        )
        for product, qty, line_total in lines:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.discounted_price,
                quantity=qty,
                line_total=line_total,
            )
            product.quantity -= qty
            product.save(update_fields=['quantity'])

    _save_cart(request, {})
    request.session['last_order_number'] = order.order_number
    return order


def order_success(request):
    number = request.session.pop('last_order_number', None)
    order = Order.objects.filter(order_number=number).select_related('customer').first() if number else None
    return render(request, 'shop/order_success.html', {'order': order})


def track_order(request):
    order = None
    if request.method == 'POST':
        form = TrackOrderForm(request.POST)
        if form.is_valid():
            order = (Order.objects
                     .filter(order_number=form.cleaned_data['order_number'],
                             customer__phone=form.cleaned_data['phone'])
                     .prefetch_related('items').select_related('customer').first())
            if order is None:
                form.add_error(None, "No order found with that order number and phone number.")
    else:
        form = TrackOrderForm()
    return render(request, 'shop/track_order.html', {'form': form, 'order': order})


def page_not_found(request, exception):
    return render(request, 'shop/404.html', status=404)


# ---------- accounts ----------

def signup(request):
    if request.user.is_authenticated:
        return redirect('shop:home')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
        return redirect(_safe_next(request, reverse('shop:home')))
    return render(request, 'shop/signup.html', {'form': form, 'next': request.GET.get('next', '')})


@login_required
def my_orders(request):
    orders = request.user.orders.prefetch_related('items')
    return render(request, 'shop/my_orders.html', {'orders': orders})


@login_required
def my_order_detail(request, order_number):
    order = get_object_or_404(
        request.user.orders.prefetch_related('items'), order_number=order_number)
    return render(request, 'shop/my_order_detail.html', {'order': order})
