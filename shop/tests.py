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
