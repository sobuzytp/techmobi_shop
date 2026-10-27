from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import ratelimit, services
from .forms import CheckoutForm, PhoneLoginForm, ReviewForm, SignupForm, TrackOrderForm, normalize_phone
from .models import (
    Banner, BlockedPhone, Category, Coupon, Customer, Order, OrderItem, Page, Product, Review,
    ShopSettings, Wishlist,
)

CART_SESSION_KEY = 'cart'

# Rate limits: (attempts, window in seconds)
LOGIN_PHONE_LIMIT = (5, 15 * 60)    # failed logins for one phone number
LOGIN_IP_LIMIT = (30, 15 * 60)      # failed logins from one address (generous: shops share IPs)
SIGNUP_IP_LIMIT = (8, 60 * 60)
TRACK_IP_LIMIT = (20, 15 * 60)
COUPON_IP_LIMIT = (15, 15 * 60)     # wrong coupon codes


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


def _session_coupon(request, subtotal):
    """The coupon saved in the session, if it is still valid for this cart (else it is dropped)."""
    code = request.session.get('coupon')
    if not code:
        return None
    coupon = Coupon.objects.filter(code=code).first()
    ok, message = (False, "Coupon not found.") if coupon is None else coupon.validate_for(subtotal, request.user)
    if not ok:
        request.session.pop('coupon', None)
        messages.warning(request, f'Coupon {code} was removed: {message}')
        return None
    return coupon


def _quote(request, subtotal, area='inside'):
    """Price breakdown for the current cart: discount, delivery and total."""
    shop = ShopSettings.load()
    coupon = _session_coupon(request, subtotal)
    discount = coupon.discount_for(subtotal) if coupon else Decimal('0.00')
    after_discount = subtotal - discount
    delivery = shop.delivery_charge_for(area, after_discount)
    return {
        'shop': shop,
        'coupon': coupon,
        'discount': discount,
        'delivery_charge': delivery,
        'total': after_discount + delivery,
        'below_minimum': bool(shop.min_order_amount) and after_discount < shop.min_order_amount,
    }


# ---------- pages ----------

def home(request):
    categories = Category.objects.all()
    featured_products = list(Product.objects.filter(is_featured=True)[:8])
    if not featured_products:
        featured_products = list(Product.objects.all()[:8])
    return render(request, 'shop/home.html', {
        'categories': categories,
        'featured_products': featured_products,
        'banners': Banner.objects.filter(is_active=True),
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

    reviews = product.reviews.filter(is_visible=True).select_related('user')
    rating = reviews.aggregate(average=Avg('rating'), count=Count('id'))

    user = request.user
    can_review = my_review = wishlisted = False
    if user.is_authenticated:
        can_review = OrderItem.objects.filter(
            order__user=user, order__status='delivered', product=product).exists()
        my_review = Review.objects.filter(user=user, product=product).first()
        wishlisted = Wishlist.objects.filter(user=user, product=product).exists()

    # Recently viewed (kept in the session, newest first, current product excluded from the list)
    recent_ids = [i for i in request.session.get('recent', []) if i != product.pk]
    recent_products = Product.objects.in_bulk(recent_ids[:4])
    request.session['recent'] = ([product.pk] + recent_ids)[:6]

    shop = ShopSettings.load()
    whatsapp_url = ''
    if shop.whatsapp_number:
        text = (f"Hello, I want to order {product.name} (Tk {product.discounted_price}). "
                f"{request.build_absolute_uri(product.get_absolute_url())}")
        whatsapp_url = f"https://wa.me/{shop.whatsapp_number}?text={quote(text)}"

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'gallery': product.gallery.all(),
        'related_products': related[:4],
        'recent_products': [recent_products[i] for i in recent_ids[:4] if i in recent_products],
        'cart_qty': _get_cart(request).get(str(product.pk), 0),
        'reviews': reviews[:20],
        'rating': rating,
        'review_form': ReviewForm(initial={'rating': my_review.rating if my_review else 5,
                                           'comment': my_review.comment if my_review else ''}),
        'can_review': can_review,
        'my_review': my_review,
        'wishlisted': wishlisted,
        'whatsapp_url': whatsapp_url,
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

    if request.POST.get('buy_now') and key in cart:
        return redirect('shop:checkout')
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
    quote_ = _quote(request, subtotal)
    return render(request, 'shop/cart.html', {
        'items': items,
        'subtotal': subtotal,
        'quote': quote_,
        'has_stock_problem': any(i['over_stock'] for i in items),
    })


@require_POST
def apply_coupon(request):
    code = request.POST.get('code', '').strip().upper()
    _, subtotal = _cart_items(request)
    ip_key = ratelimit.make_key('coupon-ip', ratelimit.client_ip(request))
    if ratelimit.is_limited(ip_key, *COUPON_IP_LIMIT):
        messages.error(request, "Too many wrong coupon codes. Please try again later.")
        return redirect('shop:cart')
    coupon = Coupon.objects.filter(code=code).first() if code else None
    if coupon is None:
        ratelimit.record(ip_key, COUPON_IP_LIMIT[1])
        messages.error(request, "That coupon code is not valid.")
    else:
        ok, message = coupon.validate_for(subtotal, request.user)
        if ok:
            request.session['coupon'] = coupon.code
            messages.success(request, f'Coupon {coupon.code} applied.')
        else:
            messages.error(request, message)
    return redirect('shop:cart')


@require_POST
def remove_coupon(request):
    request.session.pop('coupon', None)
    messages.info(request, "Coupon removed.")
    return redirect('shop:cart')


@login_required
def checkout(request):
    items, subtotal = _cart_items(request)

    if not items:
        messages.info(request, "Your cart is empty. Add some products before checking out.")
        return redirect('shop:product_list')

    if any(i['over_stock'] for i in items):
        messages.warning(request, "Some items in your cart exceed available stock. Please adjust the quantities.")
        return redirect('shop:cart')

    had_coupon = bool(request.session.get('coupon'))
    early_quote = _quote(request, subtotal)
    if request.method == 'POST' and had_coupon and early_quote['coupon'] is None:
        # The coupon stopped being valid, so the price the customer saw has changed.
        # Show the new total instead of silently placing the order.
        return redirect('shop:checkout')

    if early_quote['below_minimum']:
        shop = early_quote['shop']
        messages.warning(request, f"The minimum order is Tk {shop.min_order_amount:.0f}. Please add more items.")
        return redirect('shop:cart')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            phones = {form.cleaned_data['phone'], request.user.username}
            if BlockedPhone.objects.filter(phone__in=phones).exists():
                form.add_error(None, "We are unable to accept orders from this account. Please contact us.")
            else:
                order = _place_order(request, form)
                if order is not None:
                    return redirect('shop:order_success')
                return redirect('shop:cart')
    else:
        form = CheckoutForm(initial=_checkout_initial(request.user))

    area = form['delivery_area'].value() or 'inside'
    quote_ = _quote(request, subtotal, area)
    shop = quote_['shop']
    return render(request, 'shop/checkout.html', {
        'form': form,
        'items': items,
        'subtotal': subtotal,
        'discount': quote_['discount'],
        'coupon': quote_['coupon'],
        'delivery_charge': quote_['delivery_charge'],
        'grand_total': quote_['total'],
        'delivery_charges': {'inside': shop.delivery_charge_inside, 'outside': shop.delivery_charge_outside},
        'free_threshold': shop.free_delivery_threshold,
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
    """Create the order atomically, re-checking stock, coupon and minimum under a lock.

    Returns the Order, or None if something changed and the order could not be placed.
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

        shop = ShopSettings.load()

        coupon = None
        discount = Decimal('0.00')
        code = request.session.get('coupon')
        if code:
            coupon = Coupon.objects.select_for_update().filter(code=code).first()
            ok, message = (False, "Coupon not found.") if coupon is None else coupon.validate_for(subtotal, request.user)
            if not ok:
                request.session.pop('coupon', None)
                messages.error(request, f'Coupon {code} could not be used: {message} Please review your order.')
                return None
            discount = coupon.discount_for(subtotal)

        after_discount = subtotal - discount
        if shop.min_order_amount and after_discount < shop.min_order_amount:
            messages.error(request, f"The minimum order is Tk {shop.min_order_amount:.0f}.")
            return None

        # One customer record per phone number (older data may contain duplicates).
        customer = Customer.objects.filter(phone=data['phone']).order_by('-id').first()
        if customer is None:
            customer = Customer.objects.create(
                phone=data['phone'], name=data['name'], address=data['address'])
        else:
            customer.name = data['name']
            customer.address = data['address']
            customer.save(update_fields=['name', 'address'])

        delivery_charge = shop.delivery_charge_for(data['delivery_area'], after_discount)
        order = Order.objects.create(
            customer=customer,
            user=request.user if request.user.is_authenticated else None,
            delivery_address=data['address'],
            delivery_area=data['delivery_area'],
            payment_method=data['payment_method'],
            note=data['note'],
            subtotal=subtotal,
            coupon=coupon,
            coupon_code=coupon.code if coupon else '',
            discount_amount=discount,
            delivery_charge=delivery_charge,
            total_price=after_discount + delivery_charge,
        )
        for product, qty, line_total in lines:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.discounted_price,
                quantity=qty,
                line_total=line_total,
                warranty_months=product.warranty_months,
            )
            product.quantity -= qty
            product.save(update_fields=['quantity'])

    _save_cart(request, {})
    request.session.pop('coupon', None)
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
        ip_key = ratelimit.make_key('track-ip', ratelimit.client_ip(request))
        if ratelimit.is_limited(ip_key, *TRACK_IP_LIMIT):
            form.add_error(None, "Too many attempts. Please wait a few minutes and try again.")
            response = render(request, 'shop/track_order.html', {'form': form, 'order': None})
            response.status_code = 429
            return response
        ratelimit.record(ip_key, TRACK_IP_LIMIT[1])
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
    if request.method == 'POST':
        ip_key = ratelimit.make_key('signup-ip', ratelimit.client_ip(request))
        if ratelimit.is_limited(ip_key, *SIGNUP_IP_LIMIT):
            messages.error(request, "Too many sign-up attempts. Please try again later.")
            response = render(request, 'shop/signup.html', {'form': SignupForm(), 'next': request.GET.get('next', '')})
            response.status_code = 429
            return response
        ratelimit.record(ip_key, SIGNUP_IP_LIMIT[1])
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


@login_required
@require_POST
def cancel_my_order(request, order_number):
    order = get_object_or_404(request.user.orders, order_number=order_number)
    if not order.can_customer_cancel:
        messages.error(request, "This order can no longer be cancelled online. Please contact us.")
    else:
        services.apply_status(order, 'cancelled')
        messages.success(request, f"Order {order.order_number} has been cancelled.")
    return redirect('shop:my_order_detail', order_number=order.order_number)


# ---------- wishlist & reviews ----------

@login_required
def wishlist_view(request):
    items = request.user.wishlist.select_related('product')
    return render(request, 'shop/wishlist.html', {'items': items})


@require_POST
def wishlist_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    fallback = reverse('shop:product_detail', args=[product.pk])
    if not request.user.is_authenticated:
        messages.info(request, "Please log in to save products to your wishlist.")
        return redirect(f"{reverse('shop:login')}?next={_safe_next(request, fallback)}")
    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
        messages.info(request, f'"{product.name}" removed from your wishlist.')
    else:
        messages.success(request, f'"{product.name}" saved to your wishlist.')
    return redirect(_safe_next(request, fallback))


@require_POST
def submit_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    url = reverse('shop:product_detail', args=[product.pk]) + '#reviews'
    if not request.user.is_authenticated:
        messages.info(request, "Please log in to write a review.")
        return redirect(f"{reverse('shop:login')}?next={reverse('shop:product_detail', args=[product.pk])}")
    bought = OrderItem.objects.filter(
        order__user=request.user, order__status='delivered', product=product).exists()
    if not bought:
        messages.error(request, "You can review a product after your order of it has been delivered.")
        return redirect(url)
    form = ReviewForm(request.POST)
    if form.is_valid():
        Review.objects.update_or_create(
            user=request.user, product=product,
            defaults={'rating': int(form.cleaned_data['rating']), 'comment': form.cleaned_data['comment']})
        messages.success(request, "Thanks for your review!")
    else:
        messages.error(request, "Please choose a rating from 1 to 5.")
    return redirect(url)


# ---------- staff pages ----------

@staff_member_required
def dashboard(request):
    shop = ShopSettings.load()
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = today.replace(day=1)
    live = Order.objects.exclude(status='cancelled')

    def totals(qs):
        data = qs.aggregate(count=Count('id'), sales=Sum('total_price'))
        return {'count': data['count'], 'sales': data['sales'] or Decimal('0')}

    week_start = today - timedelta(days=6)
    by_day = {row['day']: row for row in live.filter(order_date__gte=week_start)
              .annotate(day=TruncDate('order_date')).values('day')
              .annotate(count=Count('id'), sales=Sum('total_price'))}
    week = []
    for i in range(7):
        day = (week_start + timedelta(days=i)).date()
        row = by_day.get(day, {})
        week.append({'day': day, 'count': row.get('count', 0), 'sales': row.get('sales') or Decimal('0')})
    peak = max((d['sales'] for d in week), default=0) or 1
    for d in week:
        d['percent'] = int(d['sales'] * 100 / peak)

    status_counts = {row['status']: row['n'] for row in Order.objects.values('status').annotate(n=Count('id'))}
    pending = Order.objects.filter(status='pending')

    return render(request, 'shop/dashboard.html', {
        'today': totals(live.filter(order_date__gte=today)),
        'month': totals(live.filter(order_date__gte=month)),
        'all_time': totals(live),
        'week': week,
        'status_counts': [(label, status_counts.get(key, 0)) for key, label in Order.STATUS_CHOICES],
        'pending_count': pending.count(),
        'unconfirmed_count': pending.filter(call_confirmed=False).count(),
        'low_stock': Product.objects.filter(quantity__lte=shop.low_stock_threshold).order_by('quantity', 'name')[:15],
        'low_stock_threshold': shop.low_stock_threshold,
        'top_products': (OrderItem.objects.filter(order__in=live.filter(order_date__gte=now - timedelta(days=30)))
                         .values('product_name').annotate(qty=Sum('quantity'), revenue=Sum('line_total'))
                         .order_by('-qty')[:5]),
        'recent_orders': Order.objects.select_related('customer')[:10],
        'customer_count': Customer.objects.count(),
        'visitor_ip': ratelimit.client_ip(request),
    })


@staff_member_required
def invoice(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related('customer').prefetch_related('items'), order_number=order_number)
    return render(request, 'shop/invoice.html', {'order': order})


def server_error(request):
    return render(request, 'shop/500.html', status=500)


class ThrottledLoginView(LoginView):
    """Login with phone + password; locks a phone number after too many wrong passwords."""
    template_name = 'shop/login.html'
    authentication_form = PhoneLoginForm
    redirect_authenticated_user = True

    def _keys(self):
        phone = normalize_phone(self.request.POST.get('username', ''))
        return (ratelimit.make_key('login-phone', phone),
                ratelimit.make_key('login-ip', ratelimit.client_ip(self.request)))

    def post(self, request, *args, **kwargs):
        phone_key, ip_key = self._keys()
        if ratelimit.is_limited(phone_key, *LOGIN_PHONE_LIMIT) or ratelimit.is_limited(ip_key, *LOGIN_IP_LIMIT):
            messages.error(request, "Too many failed attempts. Please wait 15 minutes and try again.")
            response = self.render_to_response(self.get_context_data(form=PhoneLoginForm(request=request)))
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        phone_key, ip_key = self._keys()
        ratelimit.record(phone_key, LOGIN_PHONE_LIMIT[1])
        ratelimit.record(ip_key, LOGIN_IP_LIMIT[1])
        return super().form_invalid(form)

    def form_valid(self, form):
        ratelimit.reset(self._keys()[0])
        return super().form_valid(form)


# ---------- text pages ----------

def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, 'shop/page.html', {'page': page})
