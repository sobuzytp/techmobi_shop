import json
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
        from django.contrib.auth import get_user_model
        self.p1 = make_product('A', '1000', 5)
        self.p2 = make_product('B', '500', 3, discount_percent=10)
        self.url = reverse('shop:checkout')
        self.user = get_user_model().objects.create_user('01600000000', password='S3cure-pass-91')
        self.client.force_login(self.user)

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


class AccountTests(TestCase):
    def signup_data(self, **extra):
        data = {'name': 'Rahim', 'phone': '01712345678',
                'password1': 'S3cure-pass-91', 'password2': 'S3cure-pass-91'}
        data.update(extra)
        return data

    def test_signup_creates_user_and_logs_in(self):
        resp = self.client.post(reverse('shop:signup'), self.signup_data())
        self.assertRedirects(resp, reverse('shop:home'))
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.get(username='01712345678')
        self.assertEqual(user.first_name, 'Rahim')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_signup_normalises_phone(self):
        self.client.post(reverse('shop:signup'), self.signup_data(phone='+8801712345678'))
        from django.contrib.auth import get_user_model
        self.assertTrue(get_user_model().objects.filter(username='01712345678').exists())

    def test_signup_rejects_duplicate_phone_bad_phone_and_weak_password(self):
        self.client.post(reverse('shop:signup'), self.signup_data())
        self.client.logout()
        for bad in (self.signup_data(), self.signup_data(phone='123'),
                    self.signup_data(phone='01812345678', password1='12345678', password2='12345678'),
                    self.signup_data(phone='01912345678', password2='different-pass-1')):
            resp = self.client.post(reverse('shop:signup'), bad)
            self.assertEqual(resp.status_code, 200)
        from django.contrib.auth import get_user_model
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_login_with_phone_variants_and_wrong_password(self):
        self.client.post(reverse('shop:signup'), self.signup_data())
        self.client.logout()
        resp = self.client.post(reverse('shop:login'), {'username': '+880 1712-345678', 'password': 'S3cure-pass-91'})
        self.assertEqual(resp.status_code, 302)
        self.client.logout()
        resp = self.client.post(reverse('shop:login'), {'username': '01712345678', 'password': 'nope'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_external_next_is_ignored(self):
        self.client.post(reverse('shop:signup'), self.signup_data())
        self.client.logout()
        resp = self.client.post(reverse('shop:login'), {
            'username': '01712345678', 'password': 'S3cure-pass-91', 'next': 'https://evil.example.com/'})
        self.assertRedirects(resp, reverse('shop:home'), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.post(reverse('shop:signup'), self.signup_data())
        self.assertEqual(self.client.get(reverse('shop:logout')).status_code, 405)
        self.client.post(reverse('shop:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_my_orders_requires_login(self):
        resp = self.client.get(reverse('shop:my_orders'))
        self.assertRedirects(resp, reverse('shop:login') + '?next=/my-orders/')

    def test_order_attached_to_user_prefill_and_privacy(self):
        product = make_product(quantity=5)
        self.client.post(reverse('shop:signup'), self.signup_data())
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        self.client.post(reverse('shop:checkout'), {
            'name': 'Rahim', 'phone': '01712345678', 'address': 'Sonadanga, Khulna',
            'delivery_area': 'inside', 'payment_method': 'cod', 'note': ''})
        order = Order.objects.get()
        self.assertIsNotNone(order.user)

        resp = self.client.get(reverse('shop:my_orders'))
        self.assertEqual(list(resp.context['orders']), [order])
        self.assertEqual(self.client.get(reverse('shop:my_order_detail', args=[order.order_number])).status_code, 200)

        # checkout is prefilled from the account and last order
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        resp = self.client.get(reverse('shop:checkout'))
        self.assertEqual(resp.context['form'].initial['address'], 'Sonadanga, Khulna')
        self.assertEqual(resp.context['form'].initial['phone'], '01712345678')

        # another user cannot open this order
        self.client.post(reverse('shop:logout'))
        self.client.post(reverse('shop:signup'), self.signup_data(phone='01812345678', name='Karim'))
        self.assertEqual(self.client.get(reverse('shop:my_order_detail', args=[order.order_number])).status_code, 404)
        self.assertEqual(list(self.client.get(reverse('shop:my_orders')).context['orders']), [])

    def test_checkout_requires_login(self):
        product = make_product(quantity=5)
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        resp = self.client.get(reverse('shop:checkout'))
        self.assertRedirects(resp, reverse('shop:login') + '?next=/checkout/')
        resp = self.client.post(reverse('shop:checkout'), {
            'name': 'Guest', 'phone': '01512345678', 'address': 'Dhaka',
            'delivery_area': 'outside', 'payment_method': 'cod', 'note': ''})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_guest_can_still_use_cart_and_is_sent_back_to_checkout_after_login(self):
        product = make_product(quantity=5)
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        self.assertEqual(self.client.get(reverse('shop:cart')).status_code, 200)
        self.client.post(reverse('shop:signup'), self.signup_data(next='/checkout/'))
        self.assertEqual(self.client.get(reverse('shop:checkout')).status_code, 200)
        self.assertEqual(self.client.session['cart'], {str(product.pk): 1})


# ---------------------------------------------------------------------------
# Growth features: coupons, delivery settings, cancel/stock, wishlist, reviews,
# staff pages, admin actions, SEO
# ---------------------------------------------------------------------------
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from . import services
from .models import BlockedPhone, Coupon, Review, ShopSettings, Wishlist


def make_user(phone='01700000001', staff=False, password='S3cure-pass-91'):
    user = get_user_model().objects.create_user(phone, password=password, first_name='Test', is_staff=staff,
                                                is_superuser=staff)
    return user


def checkout_data(**extra):
    data = {'name': 'Rahim', 'phone': '01700000001', 'address': 'Khulna',
            'delivery_area': 'inside', 'payment_method': 'cod', 'note': ''}
    data.update(extra)
    return data


class CouponAndPricingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.product = make_product('Phone', '1000', 10)
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))  # subtotal 2000

    def apply(self, code):
        return self.client.post(reverse('shop:apply_coupon'), {'code': code})

    def test_percent_coupon_with_cap(self):
        Coupon.objects.create(code='save10', discount_type='percent', value=10, max_discount=150)
        self.apply('SAVE10')
        quote = self.client.get(reverse('shop:cart')).context['quote']
        self.assertEqual(quote['discount'], Decimal('150'))  # 10% = 200, capped at 150

    def test_fixed_coupon_and_order_snapshot(self):
        coupon = Coupon.objects.create(code='FLAT100', discount_type='fixed', value=100)
        self.apply('flat100')  # case-insensitive
        self.client.post(reverse('shop:checkout'), checkout_data())
        order = Order.objects.get()
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.coupon_code, 'FLAT100')
        self.assertEqual(order.discount_amount, Decimal('100'))
        self.assertEqual(order.total_price, Decimal('2000') - Decimal('100') + Decimal('60'))
        self.assertNotIn('coupon', self.client.session)

    def test_invalid_coupons_rejected(self):
        past = timezone.now() - timedelta(days=1)
        Coupon.objects.create(code='OLD', value=10, valid_to=past)
        Coupon.objects.create(code='OFF', value=10, is_active=False)
        Coupon.objects.create(code='BIG', value=10, min_order_amount=99999)
        for code in ('OLD', 'OFF', 'BIG', 'NOPE', ''):
            self.apply(code)
            self.assertNotIn('coupon', self.client.session, code)

    def test_one_use_per_customer_and_max_uses(self):
        Coupon.objects.create(code='ONCE', value=10, per_user_limit=1)
        self.apply('ONCE')
        self.client.post(reverse('shop:checkout'), checkout_data())
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.apply('ONCE')
        self.assertNotIn('coupon', self.client.session)

        Coupon.objects.create(code='LIMITED', value=5, max_uses=1, per_user_limit=0)
        other = make_user('01700000002')
        self.client.force_login(other)
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.apply('LIMITED')
        self.client.post(reverse('shop:checkout'), checkout_data(phone='01700000002'))
        third = make_user('01700000003')
        self.client.force_login(third)
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.apply('LIMITED')
        self.assertNotIn('coupon', self.client.session)

    def test_coupon_that_becomes_invalid_blocks_order(self):
        coupon = Coupon.objects.create(code='SAVE', value=10)
        self.apply('SAVE')
        Coupon.objects.filter(pk=coupon.pk).update(is_active=False)
        resp = self.client.post(reverse('shop:checkout'), checkout_data())
        self.assertRedirects(resp, reverse('shop:checkout'))  # shows the new price instead of ordering
        self.assertEqual(Order.objects.count(), 0)
        self.assertNotIn('coupon', self.client.session)

    def test_free_delivery_threshold_and_settings_charges(self):
        shop = ShopSettings.load()
        shop.delivery_charge_inside = 80
        shop.free_delivery_threshold = 1500
        shop.save()
        resp = self.client.get(reverse('shop:checkout'))
        self.assertEqual(resp.context['delivery_charge'], Decimal('0.00'))
        shop.free_delivery_threshold = 5000
        shop.save()
        self.client.post(reverse('shop:checkout'), checkout_data())
        self.assertEqual(Order.objects.get().delivery_charge, Decimal('80'))

    def test_minimum_order(self):
        shop = ShopSettings.load()
        shop.min_order_amount = 5000
        shop.save()
        self.assertRedirects(self.client.get(reverse('shop:checkout')), reverse('shop:cart'))
        self.client.post(reverse('shop:checkout'), checkout_data())
        self.assertEqual(Order.objects.count(), 0)


class CancelAndStockTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.product = make_product('Phone', '1000', 5)
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.client.post(reverse('shop:add_to_cart', args=[self.product.pk]))
        self.client.post(reverse('shop:checkout'), checkout_data())
        self.order = Order.objects.get()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)

    def stock(self):
        self.product.refresh_from_db()
        return self.product.quantity

    def test_customer_cancel_restores_stock_once(self):
        url = reverse('shop:cancel_my_order', args=[self.order.order_number])
        self.client.post(url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.stock(), 5)
        self.client.post(url)  # second time does nothing
        self.assertEqual(self.stock(), 5)

    def test_cancel_requires_post_and_ownership(self):
        url = reverse('shop:cancel_my_order', args=[self.order.order_number])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(make_user('01700000009'))
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.stock(), 3)

    def test_call_confirmed_order_cannot_be_cancelled_online(self):
        Order.objects.filter(pk=self.order.pk).update(call_confirmed=True)
        self.client.post(reverse('shop:cancel_my_order', args=[self.order.order_number]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
        self.assertEqual(self.stock(), 3)

    def test_services_apply_status_cannot_reopen(self):
        services.apply_status(self.order, 'cancelled')
        ok, error = services.apply_status(self.order, 'shipped')
        self.assertFalse(ok)
        self.assertIn('cannot be re-opened', error)
        self.assertEqual(self.stock(), 5)

    def test_admin_bulk_cancel_and_list_editable(self):
        admin_user = make_user('01700000100', staff=True)
        self.client.force_login(admin_user)
        resp = self.client.post(reverse('admin:shop_order_changelist'), {
            'action': 'mark_cancelled', '_selected_action': [self.order.pk]}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.stock(), 5)

    def test_admin_change_form_cancel_restores_stock(self):
        admin_user = make_user('01700000100', staff=True)
        self.client.force_login(admin_user)
        url = reverse('admin:shop_order_change', args=[self.order.pk])
        data = {'status': 'cancelled', 'delivery_address': 'Khulna', 'delivery_area': 'inside',
                'payment_method': 'cod', 'note': '', 'call_confirmed': '',
                'items-TOTAL_FORMS': '0', 'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000', 'customer': self.order.customer_id}
        self.client.post(url, data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.stock(), 5)
        # trying to re-open is refused
        self.client.post(url, dict(data, status='shipped'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.stock(), 5)


class BlockedAndBuyNowTests(TestCase):
    def test_blocked_phone_cannot_signup_or_order(self):
        BlockedPhone.objects.create(phone='01700000050')
        resp = self.client.post(reverse('shop:signup'), {
            'name': 'X', 'phone': '01700000050', 'password1': 'S3cure-pass-91', 'password2': 'S3cure-pass-91'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='01700000050').exists())

        user = make_user('01700000051')
        product = make_product(quantity=3)
        self.client.force_login(user)
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        self.client.post(reverse('shop:checkout'), checkout_data(phone='01700000050'))
        self.assertEqual(Order.objects.count(), 0)
        BlockedPhone.objects.create(phone='01700000051')  # the account's own number
        self.client.post(reverse('shop:checkout'), checkout_data(phone='01700000052'))
        self.assertEqual(Order.objects.count(), 0)

    def test_admin_block_action(self):
        user = make_user('01700000060')
        customer = Customer.objects.create(name='A', phone='01700000060', address='x')
        order = Order.objects.create(customer=customer, user=user, total_price=Decimal('10'))
        self.client.force_login(make_user('01700000100', staff=True))
        self.client.post(reverse('admin:shop_order_changelist'),
                         {'action': 'block_customer_phone', '_selected_action': [order.pk]})
        self.assertTrue(BlockedPhone.objects.filter(phone='01700000060').exists())

    def test_buy_now_goes_to_checkout(self):
        product = make_product(quantity=3)
        self.client.force_login(make_user())
        resp = self.client.post(reverse('shop:add_to_cart', args=[product.pk]), {'buy_now': '1'})
        self.assertRedirects(resp, reverse('shop:checkout'))

    def test_buy_now_out_of_stock_does_not_redirect_to_checkout(self):
        product = make_product(quantity=0)
        resp = self.client.post(reverse('shop:add_to_cart', args=[product.pk]), {'buy_now': '1'})
        self.assertRedirects(resp, reverse('shop:cart'), fetch_redirect_response=False)


class WishlistReviewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product(quantity=3)

    def test_wishlist_toggle_and_guest_redirect(self):
        url = reverse('shop:wishlist_toggle', args=[self.product.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertEqual(Wishlist.objects.count(), 1)
        self.assertEqual(self.client.get(reverse('shop:wishlist')).status_code, 200)
        self.client.post(url)
        self.assertEqual(Wishlist.objects.count(), 0)

    def deliver_order(self, status='delivered'):
        customer = Customer.objects.create(name='A', phone=self.user.username, address='x')
        order = Order.objects.create(customer=customer, user=self.user, total_price=Decimal('10'), status=status)
        OrderItem.objects.create(order=order, product=self.product, product_name='P', unit_price=1,
                                 quantity=1, line_total=1)
        return order

    def test_review_needs_delivered_order(self):
        url = reverse('shop:submit_review', args=[self.product.pk])
        self.client.force_login(self.user)
        self.deliver_order(status='shipped')
        self.client.post(url, {'rating': '5', 'comment': 'great'})
        self.assertEqual(Review.objects.count(), 0)

    def test_review_create_update_and_display(self):
        self.client.force_login(self.user)
        self.deliver_order()
        url = reverse('shop:submit_review', args=[self.product.pk])
        self.client.post(url, {'rating': '4', 'comment': 'good <b>phone</b>'})
        self.client.post(url, {'rating': '5', 'comment': 'even better'})
        self.assertEqual(Review.objects.count(), 1)
        resp = self.client.get(reverse('shop:product_detail', args=[self.product.pk]))
        self.assertEqual(resp.context['rating']['count'], 1)
        self.assertEqual(resp.context['rating']['average'], 5)
        self.assertTrue(resp.context['can_review'])
        self.assertContains(resp, 'even better')

    def test_review_html_is_escaped_and_bad_rating_rejected(self):
        self.client.force_login(self.user)
        self.deliver_order()
        url = reverse('shop:submit_review', args=[self.product.pk])
        self.client.post(url, {'rating': '9', 'comment': 'x'})
        self.assertEqual(Review.objects.count(), 0)
        self.client.post(url, {'rating': '3', 'comment': '<script>alert(1)</script>'})
        resp = self.client.get(reverse('shop:product_detail', args=[self.product.pk]))
        self.assertNotContains(resp, '<script>alert(1)</script>')

    def test_hidden_review_not_shown(self):
        Review.objects.create(product=self.product, user=self.user, rating=1, comment='secret', is_visible=False)
        resp = self.client.get(reverse('shop:product_detail', args=[self.product.pk]))
        self.assertNotContains(resp, 'secret')
        self.assertEqual(resp.context['rating']['count'], 0)

    def test_recently_viewed(self):
        other = make_product('Other', '10', 1)
        self.client.get(reverse('shop:product_detail', args=[other.pk]))
        resp = self.client.get(reverse('shop:product_detail', args=[self.product.pk]))
        self.assertEqual(resp.context['recent_products'], [other])


class StaffAndSeoTests(TestCase):
    def setUp(self):
        self.product = make_product(quantity=1)
        customer = Customer.objects.create(name='=cmd|evil', phone='01700000070', address='+1+1')
        self.order = Order.objects.create(customer=customer, total_price=Decimal('500'), subtotal=Decimal('500'),
                                          delivery_address='+1+1')
        OrderItem.objects.create(order=self.order, product=self.product, product_name='Phone',
                                 unit_price=500, quantity=1, line_total=500)

    def test_dashboard_and_invoice_are_staff_only(self):
        for url in (reverse('shop:dashboard'), reverse('shop:invoice', args=[self.order.order_number])):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
        self.client.force_login(make_user('01700000071'))  # normal customer
        self.assertEqual(self.client.get(reverse('shop:dashboard')).status_code, 302)

    def test_dashboard_renders_for_staff(self):
        self.client.force_login(make_user('01700000072', staff=True))
        resp = self.client.get(reverse('shop:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['today']['count'], 1)
        self.assertEqual(resp.context['today']['sales'], Decimal('500'))
        self.assertIn(self.product, resp.context['low_stock'])

    def test_invoice_renders_for_staff(self):
        self.client.force_login(make_user('01700000072', staff=True))
        resp = self.client.get(reverse('shop:invoice', args=[self.order.order_number]))
        self.assertContains(resp, self.order.order_number)

    def test_admin_pages_load(self):
        self.client.force_login(make_user('01700000072', staff=True))
        for name in ('shop_order', 'shop_product', 'shop_coupon', 'shop_blockedphone', 'shop_review',
                     'shop_wishlist', 'shop_banner'):
            self.assertEqual(self.client.get(reverse(f'admin:{name}_changelist')).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        resp = self.client.get(reverse('admin:shop_shopsettings_changelist'))
        self.assertEqual(resp.status_code, 302)

    def test_csv_export_neutralises_formulas(self):
        self.client.force_login(make_user('01700000072', staff=True))
        resp = self.client.post(reverse('admin:shop_order_changelist'),
                                {'action': 'export_csv', '_selected_action': [self.order.pk]})
        body = resp.content.decode('utf-8-sig')
        self.assertIn("'=cmd|evil", body)
        self.assertIn("'+1+1", body)
        self.assertIn(self.order.order_number, body)

    def test_sitemap_robots_and_meta(self):
        sitemap = self.client.get('/sitemap.xml')
        self.assertContains(sitemap, f'/products/{self.product.pk}/')
        robots = self.client.get('/robots.txt')
        self.assertContains(robots, 'Disallow: /admin/')
        self.assertContains(robots, 'Sitemap:')
        detail = self.client.get(reverse('shop:product_detail', args=[self.product.pk]))
        self.assertContains(detail, 'og:title')

    def test_home_banners_and_whatsapp(self):
        from .models import Banner
        Banner.objects.create(title='Eid Sale', subtitle='Up to 20% off')
        Banner.objects.create(title='Hidden', is_active=False)
        home = self.client.get(reverse('shop:home'))
        self.assertContains(home, 'Eid Sale')
        self.assertNotContains(home, 'Hidden')
        shop = ShopSettings.load()
        shop.whatsapp_number = '8801712345678'
        shop.save()
        detail = self.client.get(reverse('shop:product_detail', args=[self.product.pk]))
        self.assertContains(detail, 'https://wa.me/8801712345678?text=')

    def test_timezone_is_dhaka(self):
        from django.conf import settings
        self.assertEqual(settings.TIME_ZONE, 'Asia/Dhaka')


# ---------------------------------------------------------------------------
# Trust & safety: backups, warranty/IMEI, text pages, rate limiting
# ---------------------------------------------------------------------------
import shutil
import sqlite3
import tempfile
import zipfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError

from . import ratelimit
from .models import Page, ThrottleEntry


class BackupCommandTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # a real SQLite file with some data, and a media folder with one file
        self.db_path = self.tmp / 'live.sqlite3'
        con = sqlite3.connect(self.db_path)
        con.execute('CREATE TABLE t (x INTEGER)')
        con.execute('INSERT INTO t VALUES (42)')
        con.commit()
        con.close()
        self.media = self.tmp / 'media'
        (self.media / 'products').mkdir(parents=True)
        (self.media / 'products' / 'a.jpg').write_bytes(b'jpgdata')

    def run_backup(self, *args):
        out = StringIO()
        databases = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.db_path)}}
        with self.settings(DATABASES=databases, MEDIA_ROOT=str(self.media)):
            call_command('backup_data', f'--dir={self.tmp / "bk"}', *args, stdout=out)
        return out.getvalue()

    def test_backup_contains_working_db_and_media(self):
        self.run_backup()
        zips = list((self.tmp / 'bk').glob('techmobi-backup-*.zip'))
        self.assertEqual(len(zips), 1)
        with zipfile.ZipFile(zips[0]) as z:
            self.assertEqual(sorted(z.namelist()), ['db.sqlite3', 'media/products/a.jpg'])
            z.extract('db.sqlite3', self.tmp / 'restored')
        con = sqlite3.connect(self.tmp / 'restored' / 'db.sqlite3')
        self.assertEqual(con.execute('SELECT x FROM t').fetchone(), (42,))
        con.close()

    def test_no_media_and_rotation(self):
        bk = self.tmp / 'bk'
        bk.mkdir()
        for day in ('2026-01-01', '2026-01-02', '2026-01-03'):
            (bk / f'techmobi-backup-{day}_000000.zip').write_bytes(b'old')
        self.run_backup('--keep=2', '--no-media')
        names = sorted(p.name for p in bk.glob('*.zip'))
        self.assertEqual(len(names), 2)
        self.assertNotIn('techmobi-backup-2026-01-01_000000.zip', names)
        newest = [bk / n for n in names if '2026-01' not in n][0]
        with zipfile.ZipFile(newest) as z:
            self.assertEqual(z.namelist(), ['db.sqlite3'])

    def test_missing_database_is_an_error_and_creates_nothing(self):
        databases = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.tmp / 'nope.sqlite3')}}
        with self.settings(DATABASES=databases):
            with self.assertRaises(CommandError):
                call_command('backup_data', f'--dir={self.tmp / "bk"}')
        self.assertFalse((self.tmp / 'nope.sqlite3').exists())


class WarrantyAndImeiTests(TestCase):
    def test_labels(self):
        from .models import warranty_text
        self.assertEqual(warranty_text(0), '')
        self.assertEqual(warranty_text(12), '1 year')
        self.assertEqual(warranty_text(24), '2 years')
        self.assertEqual(warranty_text(6), '6 months')
        self.assertEqual(warranty_text(1), '1 month')
        self.assertEqual(warranty_text(18), '18 months')

    def test_snapshot_invoice_and_customer_view(self):
        user = make_user()
        self.client.force_login(user)
        product = make_product('Phone', '1000', 5, warranty_months=12, condition='refurbished')
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        self.client.post(reverse('shop:checkout'), checkout_data())
        item = OrderItem.objects.get()
        self.assertEqual(item.warranty_months, 12)
        Product.objects.filter(pk=product.pk).update(warranty_months=0)  # later change must not matter
        item.imei = '356938035643809'
        item.save()
        order = item.order

        detail = self.client.get(reverse('shop:my_order_detail', args=[order.order_number]))
        self.assertContains(detail, '356938035643809')
        self.assertContains(detail, '1 year')

        self.client.force_login(make_user('01700000099', staff=True))
        invoice = self.client.get(reverse('shop:invoice', args=[order.order_number]))
        self.assertContains(invoice, 'IMEI/Serial: 356938035643809')
        self.assertContains(invoice, '1 year')

    def test_product_page_shows_condition_and_warranty(self):
        product = make_product('Used phone', '500', 1, warranty_months=6, condition='used')
        page = self.client.get(reverse('shop:product_detail', args=[product.pk]))
        self.assertContains(page, '6 months warranty')
        self.assertContains(page, 'Used')
        self.assertIn(('Warranty', '6 months'), page.context['product'].specs)
        listing = self.client.get(reverse('shop:product_list'))
        self.assertContains(listing, 'Used')

    def test_admin_can_save_imei_on_order(self):
        user = make_user()
        customer = Customer.objects.create(name='A', phone=user.username, address='x')
        order = Order.objects.create(customer=customer, user=user, total_price=Decimal('10'), delivery_address='x')
        item = OrderItem.objects.create(order=order, product_name='P', unit_price=1, quantity=1, line_total=1)
        self.client.force_login(make_user('01700000098', staff=True))
        data = {'status': 'pending', 'delivery_address': 'x', 'delivery_area': 'inside', 'payment_method': 'cod',
                'note': '', 'customer': customer.pk,
                'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '1', 'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000', 'items-0-id': item.pk, 'items-0-order': order.pk,
                'items-0-imei': '111, 222'}
        self.client.post(reverse('admin:shop_order_change', args=[order.pk]), data)
        item.refresh_from_db()
        self.assertEqual(item.imei, '111, 222')


class PagesTests(TestCase):
    def test_default_pages_exist_and_render(self):
        slugs = {'about', 'contact', 'return-policy', 'warranty-policy', 'privacy-policy', 'terms'}
        self.assertEqual(set(Page.objects.values_list('slug', flat=True)), slugs)
        for slug in slugs:
            resp = self.client.get(reverse('shop:page', args=[slug]))
            self.assertEqual(resp.status_code, 200, slug)

    def test_footer_links_and_contact_details_come_from_settings(self):
        shop = ShopSettings.load()
        shop.shop_phone = '+880 1999-000000'
        shop.shop_address = 'Boyra, Khulna'
        shop.facebook_url = 'https://facebook.com/techmobi'
        shop.save()
        home = self.client.get(reverse('shop:home'))
        self.assertContains(home, 'Return &amp; Refund Policy')
        self.assertContains(home, '+880 1999-000000')
        self.assertContains(home, 'Boyra, Khulna')
        self.assertContains(home, 'https://facebook.com/techmobi')
        contact = self.client.get(reverse('shop:page', args=['contact']))
        self.assertContains(contact, 'tel:+8801999-000000')

    def test_unpublished_page_is_hidden_everywhere(self):
        Page.objects.filter(slug='terms').update(is_published=False)
        self.assertEqual(self.client.get(reverse('shop:page', args=['terms'])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('shop:home')), 'Terms &amp; Conditions')
        self.assertNotContains(self.client.get('/sitemap.xml'), '/pages/terms/')
        self.assertContains(self.client.get('/sitemap.xml'), '/pages/about/')

    def test_page_content_is_escaped(self):
        Page.objects.create(slug='x', title='X', content='Hello <script>alert(1)</script>\n\nSecond')
        resp = self.client.get(reverse('shop:page', args=['x']))
        self.assertNotContains(resp, '<script>alert(1)</script>')
        self.assertContains(resp, '&lt;script&gt;')

    def test_edited_page_is_not_overwritten_by_seed(self):
        Page.objects.filter(slug='about').update(content='My own text')
        from importlib import import_module
        from django.apps import apps
        import_module('shop.migrations.0008_seed_pages').seed(apps, None)
        self.assertEqual(Page.objects.get(slug='about').content, 'My own text')

    def test_checkout_links_to_policies(self):
        self.client.force_login(make_user())
        product = make_product(quantity=2)
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        resp = self.client.get(reverse('shop:checkout'))
        self.assertContains(resp, '/pages/terms/')
        self.assertContains(resp, '/pages/return-policy/')


class RateLimitTests(TestCase):
    def setUp(self):
        self.user = make_user('01700000200', password='S3cure-pass-91')

    def login(self, phone='01700000200', password='wrong-password'):
        return self.client.post(reverse('shop:login'), {'username': phone, 'password': password})

    def test_unit_limiter_window(self):
        key = 'k:1'
        for _ in range(3):
            ratelimit.record(key, 60)
        self.assertTrue(ratelimit.is_limited(key, 3, 60))
        self.assertFalse(ratelimit.is_limited(key, 4, 60))
        ThrottleEntry.objects.filter(key=key).update(window_start=timezone.now() - timedelta(seconds=61))
        self.assertFalse(ratelimit.is_limited(key, 3, 60))      # old window ignored
        ratelimit.record(key, 60)
        self.assertEqual(ThrottleEntry.objects.get(key=key).count, 1)  # fresh window started
        ratelimit.reset(key)
        self.assertFalse(ThrottleEntry.objects.filter(key=key).exists())

    def test_phone_locked_after_five_wrong_passwords_even_with_right_one(self):
        for _ in range(5):
            self.assertEqual(self.login().status_code, 200)
        resp = self.login(password='S3cure-pass-91')
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_other_phone_not_affected_and_phone_variants_share_a_lock(self):
        make_user('01700000201')
        for phone in ('01700000200', '+8801700000200', '880 1700-000200', '01700000200', '01700000200'):
            self.login(phone)
        self.assertEqual(self.login('01700000200', 'S3cure-pass-91').status_code, 429)
        self.assertEqual(self.login('01700000201', 'S3cure-pass-91').status_code, 302)

    def test_lock_expires(self):
        for _ in range(5):
            self.login()
        ThrottleEntry.objects.all().update(window_start=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.login(password='S3cure-pass-91').status_code, 302)

    def test_success_resets_counter(self):
        for _ in range(4):
            self.login()
        self.assertEqual(self.login(password='S3cure-pass-91').status_code, 302)
        self.client.logout()
        for _ in range(4):
            self.assertEqual(self.login().status_code, 200)   # fresh count, not locked yet

    def test_track_order_throttled(self):
        url = reverse('shop:track_order')
        for _ in range(20):
            self.assertEqual(self.client.post(url, {'order_number': 'TMXXXXXXXX', 'phone': '01700000300'}).status_code, 200)
        resp = self.client.post(url, {'order_number': 'TMXXXXXXXX', 'phone': '01700000300'})
        self.assertEqual(resp.status_code, 429)
        self.assertIsNone(resp.context['order'])

    def test_signup_throttled(self):
        url = reverse('shop:signup')
        for i in range(8):
            self.client.post(url, {'name': 'A', 'phone': f'0170000040{i}', 'password1': 'x', 'password2': 'y'})
        resp = self.client.post(url, {'name': 'A', 'phone': '01700000499',
                                      'password1': 'S3cure-pass-91', 'password2': 'S3cure-pass-91'})
        self.assertEqual(resp.status_code, 429)
        self.assertFalse(get_user_model().objects.filter(username='01700000499').exists())

    def test_coupon_guessing_throttled(self):
        Coupon.objects.create(code='REAL', value=10)
        url = reverse('shop:apply_coupon')
        for i in range(15):
            self.client.post(url, {'code': f'GUESS{i}'})
        self.client.post(url, {'code': 'REAL'})
        self.assertNotIn('coupon', self.client.session)


class ClientIpTests(TestCase):
    def test_default_and_headers(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get('/', REMOTE_ADDR='10.0.0.5', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8', HTTP_CF_CONNECTING_IP='9.9.9.9')
        self.assertEqual(ratelimit.client_ip(request), '10.0.0.5')
        with self.settings(CLIENT_IP_HEADER='HTTP_X_FORWARDED_FOR'):
            self.assertEqual(ratelimit.client_ip(request), '5.6.7.8')   # last entry: added by our proxy
        with self.settings(CLIENT_IP_HEADER='HTTP_CF_CONNECTING_IP'):
            self.assertEqual(ratelimit.client_ip(request), '9.9.9.9')
        with self.settings(CLIENT_IP_HEADER='HTTP_MISSING'):
            self.assertEqual(ratelimit.client_ip(request), '10.0.0.5')  # falls back safely

    def test_dashboard_shows_visitor_ip(self):
        self.client.force_login(make_user('01700000555', staff=True))
        self.assertContains(self.client.get(reverse('shop:dashboard')), '127.0.0.1')


# ---------------------------------------------------------------------------
# UI polish: money format, banners, footer, home sections, free-delivery hint
# ---------------------------------------------------------------------------
class UiTests(TestCase):
    def test_taka_filter(self):
        from .templatetags.shop_extras import taka, category_icon
        self.assertEqual(taka(Decimal('5499.00')), '5,499')
        self.assertEqual(taka(Decimal('3399.15')), '3,399.15')
        self.assertEqual(taka(1234567), '12,34,567')
        self.assertEqual(taka(0), '0')
        self.assertEqual(taka(-1500), '-1,500')
        self.assertEqual(taka('abc'), 'abc')
        self.assertEqual(category_icon('Smartphones'), 'bi-phone')
        self.assertEqual(category_icon('Chargers'), 'bi-lightning-charge')
        self.assertEqual(category_icon('Something else'), 'bi-grid')

    def test_banner_with_image_is_shown_whole_without_overlay_text(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Banner
        import tempfile
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                   b'\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82')
            Banner.objects.create(title='Image banner', image=SimpleUploadedFile('b.png', png, 'image/png'))
            Banner.objects.create(title='Text banner', subtitle='Sub line')
            html = self.client.get(reverse('shop:home')).content.decode()
        self.assertIn('class="banner-img"', html)
        self.assertIn('Text banner', html)
        self.assertIn('Sub line', html)
        self.assertEqual(html.count('class="banner-img"'), 1)

    def test_footer_is_compact_with_three_link_groups(self):
        html = self.client.get(reverse('shop:home')).content.decode()
        footer = html[html.index('<footer'):]
        self.assertNotIn('Quick Links', footer)
        for heading in ('Shop', 'Information', 'Contact Us'):
            self.assertIn(heading, footer)
        self.assertIn('Cash on Delivery', footer)

    def test_home_sections_skip_out_of_stock_and_do_not_repeat_products(self):
        in_stock = [make_product(f'P{i}', '1000', 5, is_featured=(i < 2), discount_percent=10 if i in (2, 3) else 0)
                    for i in range(6)]
        make_product('Gone', '1000', 0, is_featured=True)
        resp = self.client.get(reverse('shop:home'))
        shown = [p.pk for key in ('featured_products', 'deal_products', 'new_products') for p in resp.context[key]]
        self.assertEqual(len(shown), len(set(shown)))
        self.assertNotIn('Gone', [p.name for key in ('featured_products', 'deal_products', 'new_products')
                                  for p in resp.context[key]])
        self.assertTrue(set(shown) <= {p.pk for p in in_stock})

    def test_cart_shows_free_delivery_progress(self):
        shop = ShopSettings.load()
        shop.free_delivery_threshold = 5000
        shop.save()
        product = make_product('Phone', '1000', 5)
        self.client.post(reverse('shop:add_to_cart', args=[product.pk]))
        cart = self.client.get(reverse('shop:cart'))
        self.assertContains(cart, 'more for free delivery')
        self.assertEqual(cart.context['quote']['free_delivery_percent'], 20)
        self.assertEqual(cart.context['quote']['free_delivery_remaining'], Decimal('4000'))

    def test_wishlist_hearts_on_cards(self):
        user = make_user()
        product = make_product('Phone', '1000', 5)
        self.client.force_login(user)
        Wishlist.objects.create(user=user, product=product)
        resp = self.client.get(reverse('shop:product_list'))
        self.assertIn(product.pk, resp.context['wishlist_ids'])
        self.assertContains(resp, 'bi-heart-fill')


class ApiTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(name='Phones')
        self.p = Product.objects.create(name='Galaxy A15', brand='Samsung', price=Decimal('20000'),
                                        discount_percent=10, quantity=3, category=cat, ram='6GB')
        Product.objects.create(name='Old Nokia', brand='Nokia', price=Decimal('2000'), quantity=0, category=cat)

    def test_list_and_filters(self):
        data = self.client.get('/api/v1/products/').json()
        self.assertEqual(data['count'], 2)
        first = data['results'][0]
        self.assertEqual(first['final_price'], '18000.00')
        self.assertEqual(first['specs']['ram'], '6GB')
        self.assertTrue(first['url'].startswith('http'))
        self.assertEqual(self.client.get('/api/v1/products/?in_stock=1').json()['count'], 1)
        self.assertEqual(self.client.get('/api/v1/products/?q=nokia').json()['count'], 1)
        self.assertEqual(self.client.get('/api/v1/products/?page=abc').status_code, 400)

    def test_detail_404_and_other_endpoints(self):
        self.assertEqual(self.client.get(f'/api/v1/products/{self.p.pk}/').json()['name'], 'Galaxy A15')
        self.assertEqual(self.client.get('/api/v1/products/9999/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/categories/').json()['results'][0]['name'], 'Phones')
        self.assertEqual(self.client.get('/api/v1/shop/').json()['payment_methods'], ['Cash on Delivery'])
        self.assertIn('results', self.client.get('/api/v1/pages/').json())

    def test_read_only(self):
        self.assertEqual(self.client.post('/api/v1/products/').status_code, 405)

    def test_csv_feed_neutralises_formulas(self):
        Product.objects.create(name='=HYPERLINK("x")', price=Decimal('1'), quantity=1)
        text = self.client.get('/api/v1/feed.csv').content.decode()
        self.assertIn('Galaxy A15', text)
        self.assertIn("'=HYPERLINK", text)

    def test_sync_dry_run_and_missing_config(self):
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        out, err = StringIO(), StringIO()
        call_command('sync_catalog', '--dry-run', stdout=out, stderr=err)
        self.assertEqual(len(json.loads(out.getvalue())['products']), 2)
        with self.assertRaises(CommandError):
            call_command('sync_catalog', stdout=StringIO())
