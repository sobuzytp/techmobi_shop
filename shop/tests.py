from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Customer, Order, OrderItem, Product


def make_product(name='Phone', price='1000', quantity=5, **kwargs):
    return Product.objects.create(name=name, price=Decimal(price), quantity=quantity, **kwargs)


class CartTests(TestCase):
    def setUp(self):
        self.product = make_product(quantity=2)

    def add(self, product=None, **extra):
        product = product or self.product
        return self.client.post(reverse('shop:add_to_cart', args=[product.pk]), extra)

    def cart(self):
        return self.client.session.get('cart', {})

    def test_add_requires_post(self):
        resp = self.client.get(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(self.cart(), {})

    def test_cannot_exceed_stock(self):
        self.add()
        self.add()
        self.add()
        self.assertEqual(self.cart()[str(self.product.pk)], 2)

    def test_out_of_stock_not_added(self):
        sold_out = make_product(name='Sold out', quantity=0)
        self.add(sold_out)
        self.assertEqual(self.cart(), {})

    def test_increase_respects_stock(self):
        self.add()
        url = reverse('shop:update_cart', args=[self.product.pk])
        self.client.post(url, {'action': 'increase'})
        self.client.post(url, {'action': 'increase'})
        self.assertEqual(self.cart()[str(self.product.pk)], 2)

    def test_decrease_and_remove(self):
        self.add()
        url = reverse('shop:update_cart', args=[self.product.pk])
        self.client.post(url, {'action': 'decrease'})
        self.assertEqual(self.cart(), {})

    def test_update_requires_post(self):
        resp = self.client.get(reverse('shop:update_cart', args=[self.product.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_external_next_is_ignored(self):
        resp = self.add(next='https://evil.example.com/')
        self.assertRedirects(resp, reverse('shop:cart'), fetch_redirect_response=False)

    def test_local_next_is_followed(self):
        resp = self.add(next='/products/')
        self.assertRedirects(resp, '/products/', fetch_redirect_response=False)

    def test_cart_count_in_every_page(self):
        self.add()
        for name in ('shop:home', 'shop:product_list', 'shop:cart'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.context['cart_count'], 1)


@override_settings(DELIVERY_CHARGES={'inside': 60, 'outside': 120})
class CheckoutTests(TestCase):
    def setUp(self):
        self.p1 = make_product('A', '1000', 5)
        self.p2 = make_product('B', '500', 3, discount_percent=10)
        self.url = reverse('shop:checkout')

    def fill_cart(self):
        self.client.post(reverse('shop:add_to_cart', args=[self.p1.pk]))
        self.client.post(reverse('shop:add_to_cart', args=[self.p1.pk]))
        self.client.post(reverse('shop:add_to_cart', args=[self.p2.pk]))

    def data(self, **extra):
        data = {'name': 'Rahim', 'phone': '01712345678', 'address': 'Khulna',
                'delivery_area': 'inside', 'payment_method': 'cod', 'note': ''}
        data.update(extra)
        return data

    def test_empty_cart_redirects(self):
        self.assertRedirects(self.client.get(self.url), reverse('shop:product_list'))

    def test_multi_item_order_is_one_order(self):
        self.fill_cart()
        resp = self.client.post(self.url, self.data())
        self.assertRedirects(resp, reverse('shop:order_success'))
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.get()
        self.assertEqual(order.items.count(), 2)
        # 2 x 1000 + 1 x 450 (10% off) = 2450, + 60 delivery
        self.assertEqual(order.subtotal, Decimal('2450.00'))
        self.assertEqual(order.delivery_charge, Decimal('60'))
        self.assertEqual(order.total_price, Decimal('2510.00'))
        self.assertTrue(order.order_number.startswith('TM'))

    def test_outside_delivery_charge(self):
        self.fill_cart()
        self.client.post(self.url, self.data(delivery_area='outside'))
        self.assertEqual(Order.objects.get().delivery_charge, Decimal('120'))

    def test_stock_reduced_and_cart_cleared(self):
        self.fill_cart()
        self.client.post(self.url, self.data())
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual((self.p1.quantity, self.p2.quantity), (3, 2))
        self.assertEqual(self.client.session.get('cart'), {})

    def test_stock_changed_after_adding_blocks_order(self):
        self.fill_cart()
        Product.objects.filter(pk=self.p1.pk).update(quantity=1)
        resp = self.client.post(self.url, self.data())
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(resp.status_code, 302)

    def test_invalid_phone_rejected(self):
        self.fill_cart()
        resp = self.client.post(self.url, self.data(phone='12345'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_phone_normalised_and_customer_reused(self):
        for phone in ('+8801712345678', '017-1234-5678'):
            self.fill_cart()
            self.client.post(self.url, self.data(phone=phone))
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.get().phone, '01712345678')

    def test_price_snapshot_survives_product_change(self):
        self.fill_cart()
        self.client.post(self.url, self.data())
        Product.objects.filter(pk=self.p1.pk).update(price=Decimal('9999'), name='Renamed')
        item = OrderItem.objects.get(product=self.p1)
        self.assertEqual(item.product_name, 'A')
        self.assertEqual(item.unit_price, Decimal('1000.00'))


class TrackOrderTests(TestCase):
    def setUp(self):
        customer = Customer.objects.create(name='Rahim', phone='01712345678', address='Khulna')
        self.order = Order.objects.create(customer=customer, total_price=Decimal('100'))
        self.url = reverse('shop:track_order')

    def test_found(self):
        resp = self.client.post(self.url, {'order_number': self.order.order_number.lower(),
                                           'phone': '01712345678'})
        self.assertEqual(resp.context['order'], self.order)

    def test_wrong_phone_not_found(self):
        resp = self.client.post(self.url, {'order_number': self.order.order_number,
                                           'phone': '01812345678'})
        self.assertIsNone(resp.context['order'])


@override_settings(PRODUCTS_PER_PAGE=2)
class ProductListTests(TestCase):
    def setUp(self):
        phones = Category.objects.create(name='Phones')
        make_product('Cheap', '100', brand='Acme', category=phones)
        make_product('Mid', '200', brand='Acme', category=phones)
        make_product('Pricey', '300', brand='Zeta', category=phones)
        make_product('Sale', '400', brand='Zeta', discount_percent=50)  # effective 200
        self.url = reverse('shop:product_list')

    def names(self, **params):
        resp = self.client.get(self.url, params)
        return [p.name for p in resp.context['products']]

    def test_pagination(self):
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context['products']), 2)
        self.assertEqual(resp.context['page_obj'].paginator.num_pages, 2)

    def test_sort_price_uses_discounted_price(self):
        self.assertEqual(self.names(sort='price_desc')[0], 'Pricey')
        self.assertEqual(self.names(sort='price_asc')[0], 'Cheap')

    def test_price_filter_uses_discounted_price(self):
        self.assertEqual(sorted(self.names(min_price='150', max_price='250', page=1)), ['Mid', 'Sale'])

    def test_brand_filter(self):
        self.assertEqual(sorted(self.names(brand='acme')), ['Cheap', 'Mid'])

    def test_garbage_params_do_not_crash(self):
        for params in ({'min_price': 'abc'}, {'category': 'x'}, {'sort': 'nope'}, {'page': 'zzz'},
                       {'min_price': 'NaN'}, {'max_price': 'Infinity'}):
            self.assertEqual(self.client.get(self.url, params).status_code, 200)

    def test_detail_related_and_404(self):
        cheap = Product.objects.get(name='Cheap')
        resp = self.client.get(reverse('shop:product_detail', args=[cheap.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(cheap, resp.context['related_products'])
        self.assertEqual(self.client.get(reverse('shop:product_detail', args=[9999])).status_code, 404)
