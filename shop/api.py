"""Read-only public JSON API (/api/v1/) and the product feed.

Everything here is safe to expose: no customer data, no orders, no write access.
The same serializer is used by the aijobab sync command, so the assistant always sees
exactly what the website shows.
"""
import csv

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import Category, Page, Product, ShopSettings

MAX_PAGE_SIZE = 100


def _abs(request, path):
    return request.build_absolute_uri(path) if path else ''


def serialize_product(product, request):
    image = product.image.url if product.image else ''
    return {
        'id': product.pk,
        'name': product.name,
        'brand': product.brand,
        'category': product.category.name if product.category else None,
        'description': product.description,
        'price': str(product.price),
        'discount_percent': product.discount_percent,
        'final_price': str(product.discounted_price),
        'currency': 'BDT',
        'in_stock': product.in_stock,
        'quantity': product.quantity,
        'condition': product.condition,
        'warranty_months': product.warranty_months,
        'specs': {
            'ram': product.ram, 'storage': product.storage, 'display': product.display,
            'battery': product.battery, 'camera': product.camera, 'color': product.color,
        },
        'url': _abs(request, product.get_absolute_url()),
        'image': _abs(request, image),
        'updated_at': product.updated_at.isoformat(),
    }


def visible_products(request=None):
    return Product.objects.select_related('category')


def filtered_products(params):
    qs = visible_products()
    q = (params.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q))
    category = params.get('category')
    if category:
        qs = qs.filter(category__name__iexact=category)
    brand = params.get('brand')
    if brand:
        qs = qs.filter(brand__iexact=brand)
    if params.get('in_stock') in ('1', 'true'):
        qs = qs.filter(quantity__gt=0)
    return qs.order_by('pk')


@require_GET
def api_root(request):
    return JsonResponse({
        'name': 'TechMobi API', 'version': 1,
        'endpoints': {
            'products': reverse('api:products'),
            'categories': reverse('api:categories'),
            'shop': reverse('api:shop'),
            'pages': reverse('api:pages'),
            'feed_csv': reverse('api:feed'),
        },
    })


@require_GET
def api_products(request):
    try:
        page_size = min(max(int(request.GET.get('page_size', 20)), 1), MAX_PAGE_SIZE)
        page_no = max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        return JsonResponse({'error': 'page and page_size must be numbers'}, status=400)
    paginator = Paginator(filtered_products(request.GET), page_size)
    page = paginator.get_page(page_no)
    return JsonResponse({
        'count': paginator.count,
        'page': page.number,
        'pages': paginator.num_pages,
        'results': [serialize_product(p, request) for p in page.object_list],
    })


@require_GET
def api_product(request, pk):
    try:
        product = visible_products().get(pk=pk)
    except Product.DoesNotExist:
        raise Http404
    return JsonResponse(serialize_product(product, request))


@require_GET
def api_categories(request):
    return JsonResponse({'results': [{'id': c.pk, 'name': c.name} for c in Category.objects.all()]})


@require_GET
def api_shop(request):
    s = ShopSettings.load()
    return JsonResponse({
        'phone': s.shop_phone, 'email': s.shop_email, 'address': s.shop_address,
        'opening_hours': s.opening_hours, 'whatsapp': s.whatsapp_number,
        'facebook': s.facebook_url,
        'payment_methods': ['Cash on Delivery'],
        'delivery': {
            'inside_dhaka': str(s.delivery_charge_for('inside', 0)),
            'outside_dhaka': str(s.delivery_charge_for('outside', 0)),
            'free_delivery_threshold': str(s.free_delivery_threshold),
        },
        'min_order_amount': str(s.min_order_amount),
        'currency': 'BDT',
    })


@require_GET
def api_pages(request):
    pages = Page.objects.filter(is_published=True)
    return JsonResponse({'results': [
        {'slug': p.slug, 'title': p.title, 'content': p.content,
         'url': _abs(request, reverse('shop:page', args=[p.slug]))}
        for p in pages
    ]})


def _csv_safe(value):
    value = '' if value is None else str(value)
    return "'" + value if value[:1] in ('=', '+', '-', '@') else value


@require_GET
def product_feed(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    writer = csv.writer(response)
    writer.writerow(['id', 'name', 'brand', 'category', 'price', 'final_price', 'in_stock',
                     'quantity', 'condition', 'warranty_months', 'ram', 'storage', 'display',
                     'battery', 'camera', 'color', 'url', 'image', 'description'])
    for p in filtered_products(request.GET):
        d = serialize_product(p, request)
        s = d['specs']
        writer.writerow([_csv_safe(v) for v in [
            d['id'], d['name'], d['brand'], d['category'] or '', d['price'], d['final_price'],
            'yes' if d['in_stock'] else 'no', d['quantity'], d['condition'], d['warranty_months'],
            s['ram'], s['storage'], s['display'], s['battery'], s['camera'], s['color'],
            d['url'], d['image'], d['description'].replace('\n', ' '),
        ]])
    return response
