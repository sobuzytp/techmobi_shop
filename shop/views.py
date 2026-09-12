from decimal import Decimal

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from .models import Product, Category, Customer, Order
from .forms import CheckoutForm

CART_SESSION_KEY = 'cart'


# ---------- helpers ----------

def _get_cart(request):
    return request.session.get(CART_SESSION_KEY, {})


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def _cart_items(request):
    """Build a list of cart line items with live product data + totals."""
    cart = _get_cart(request)
    items = []
    grand_total = Decimal('0.00')
    for product_id, qty in cart.items():
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            continue
        unit_price = product.discounted_price
        line_total = unit_price * qty
        grand_total += line_total
        items.append({
            'product': product,
            'quantity': qty,
            'unit_price': unit_price,
            'line_total': line_total,
        })
    return items, grand_total


def _cart_count(request):
    return sum(_get_cart(request).values())


# ---------- pages ----------

def home(request):
    categories = Category.objects.all()
    featured_products = Product.objects.filter(is_featured=True)[:8]
    if not featured_products:
        featured_products = Product.objects.all()[:8]
    context = {
        'categories': categories,
        'featured_products': featured_products,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/home.html', context)


def product_list(request):
    products = Product.objects.all()

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(name__icontains=query)

    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    context = {
        'products': products,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category_id,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/product_list.html', context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    context = {
        'product': product,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/product_detail.html', context)


def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = _get_cart(request)
    key = str(pk)
    cart[key] = cart.get(key, 0) + 1
    _save_cart(request, cart)
    messages.success(request, f'"{product.name}" added to your cart.')

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('shop:cart')


def update_cart(request, pk):
    """Increase / decrease / remove a cart line via POST action."""
    if request.method == 'POST':
        cart = _get_cart(request)
        key = str(pk)
        action = request.POST.get('action')

        if key in cart:
            if action == 'increase':
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
    items, grand_total = _cart_items(request)
    context = {
        'items': items,
        'grand_total': grand_total,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/cart.html', context)


def checkout(request):
    items, grand_total = _cart_items(request)

    if not items:
        messages.info(request, "Your cart is empty. Add some products before checking out.")
        return redirect('shop:product_list')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            customer = form.save()

            # Create one Order row per cart line, using the required Order fields.
            for item in items:
                Order.objects.create(
                    customer=customer,
                    product=item['product'],
                    quantity=item['quantity'],
                    total_price=item['line_total'],
                )
                # reduce stock
                product = item['product']
                product.quantity = max(product.quantity - item['quantity'], 0)
                product.save(update_fields=['quantity'])

            _save_cart(request, {})  # empty the cart
            request.session['last_order_total'] = str(grand_total)
            request.session['last_order_customer'] = customer.name
            return redirect('shop:order_success')
    else:
        form = CheckoutForm()

    context = {
        'form': form,
        'items': items,
        'grand_total': grand_total,
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/checkout.html', context)


def order_success(request):
    context = {
        'grand_total': request.session.pop('last_order_total', None),
        'customer_name': request.session.pop('last_order_customer', None),
        'cart_count': _cart_count(request),
    }
    return render(request, 'shop/order_success.html', context)
