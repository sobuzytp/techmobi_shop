import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from . import services
from .models import (
    Banner, BlockedPhone, Category, Coupon, Customer, Order, OrderItem, Page, Product, ProductImage,
    Review, ShopSettings, Wishlist,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class LowStockFilter(admin.SimpleListFilter):
    title = 'stock'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return [('out', 'Out of stock'), ('low', 'Low stock (5 or less)')]

    def queryset(self, request, queryset):
        if self.value() == 'out':
            return queryset.filter(quantity=0)
        if self.value() == 'low':
            return queryset.filter(quantity__gt=0, quantity__lte=5)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'discount_percent', 'quantity',
                    'is_featured', 'details_status', 'created_at')
    list_filter = ('category', 'condition', 'is_featured', LowStockFilter)
    search_fields = ('name', 'brand', 'description', 'sku')
    list_editable = ('price', 'quantity', 'is_featured', 'discount_percent')
    inlines = [ProductImageInline]
    fieldsets = (
        ('Basics', {'fields': ('name', 'brand', 'sku', 'category', 'condition', 'warranty_months', 'price',
                               'discount_percent', 'quantity', 'is_featured', 'image')}),
        ('Description (customers and the AI both read this)', {'fields': (
            'short_description', 'description', 'highlights')}),
        ('Specifications', {'fields': (
            'processor', 'ram', 'storage', 'display', 'battery', 'charging', 'camera', 'os', 'network',
            'sim', 'color', 'extra_specs')}),
        ('Box and questions', {'fields': ('in_the_box', 'faq')}),
        ('For the AI assistant (not on the product page - no secrets or cost prices)', {'fields': ('ai_notes',)}),
    )

    @admin.display(description='Details')
    def details_status(self, obj):
        filled, total = obj.completeness
        color = '#198754' if filled >= total - 2 else '#fd7e14' if filled >= total // 2 else '#dc3545'
        return format_html('<b style="color:{}">{}/{}</b>', color, filled, total)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')
    search_fields = ('name', 'phone')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product_name', 'quantity', 'unit_price', 'line_total', 'warranty_months', 'imei')
    readonly_fields = ('product_name', 'unit_price', 'quantity', 'line_total', 'warranty_months')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


def _csv_safe(value):
    """Stop spreadsheet programs from running customer-typed text as a formula."""
    value = '' if value is None else str(value)
    return "'" + value if value[:1] in ('=', '+', '-', '@', '\t', '\r') else value


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'delivery_area', 'total_price', 'status',
                    'call_confirmed', 'order_date', 'invoice_link')
    list_filter = ('status', 'call_confirmed', 'delivery_area', 'payment_method', 'order_date')
    list_editable = ('status', 'call_confirmed')
    search_fields = ('order_number', 'customer__name', 'customer__phone')
    readonly_fields = ('order_number', 'user', 'subtotal', 'coupon', 'coupon_code', 'discount_amount',
                       'delivery_charge', 'total_price', 'order_date')
    inlines = [OrderItemInline]
    actions = ['mark_confirmed', 'mark_shipped', 'mark_delivered', 'mark_cancelled',
               'mark_call_confirmed', 'block_customer_phone', 'export_csv']

    @admin.display(description='Invoice')
    def invoice_link(self, obj):
        return format_html('<a href="{}" target="_blank">Print</a>', reverse('shop:invoice', args=[obj.order_number]))

    def save_model(self, request, obj, form, change):
        if change:
            old_status = Order.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
            if old_status == 'cancelled' and obj.status != 'cancelled':
                self.message_user(
                    request, f"Order {obj.order_number} is cancelled and cannot be re-opened "
                             f"(its stock was given back). Ask the customer to place a new order.",
                    messages.ERROR)
                return
        super().save_model(request, obj, form, change)
        if obj.status == 'cancelled':
            services.restore_stock(obj)

    def _set_status(self, request, queryset, status):
        changed = 0
        for order in queryset:
            ok, error = services.apply_status(order, status)
            if ok:
                changed += 1
            elif error:
                self.message_user(request, error, messages.WARNING)
        self.message_user(request, f"{changed} order(s) updated to {dict(Order.STATUS_CHOICES)[status]}.")

    @admin.action(description="Mark selected orders as Confirmed")
    def mark_confirmed(self, request, queryset):
        self._set_status(request, queryset, 'confirmed')

    @admin.action(description="Mark selected orders as Shipped")
    def mark_shipped(self, request, queryset):
        self._set_status(request, queryset, 'shipped')

    @admin.action(description="Mark selected orders as Delivered")
    def mark_delivered(self, request, queryset):
        self._set_status(request, queryset, 'delivered')

    @admin.action(description="Cancel selected orders (stock is given back)")
    def mark_cancelled(self, request, queryset):
        self._set_status(request, queryset, 'cancelled')

    @admin.action(description="Mark as confirmed by phone call")
    def mark_call_confirmed(self, request, queryset):
        count = queryset.update(call_confirmed=True)
        self.message_user(request, f"{count} order(s) marked as call-confirmed.")

    @admin.action(description="Block the phone number of the selected orders")
    def block_customer_phone(self, request, queryset):
        blocked = 0
        for order in queryset.select_related('customer', 'user'):
            phones = {order.customer.phone}
            if order.user_id:
                phones.add(order.user.username)
            for phone in phones:
                _, created = BlockedPhone.objects.get_or_create(
                    phone=phone, defaults={'reason': f'Blocked from order {order.order_number}'})
                blocked += created
        self.message_user(request, f"{blocked} phone number(s) blocked.")

    @admin.action(description="Export selected orders to CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="orders-{timezone.localdate()}.csv"'
        response.write('\ufeff')  # so Excel reads Bangla text correctly
        writer = csv.writer(response)
        writer.writerow(['Order', 'Date', 'Customer', 'Phone', 'Address', 'Area', 'Items', 'Subtotal',
                         'Discount', 'Coupon', 'Delivery', 'Total', 'Payment', 'Status', 'Call confirmed'])
        for o in queryset.select_related('customer').prefetch_related('items'):
            items = '; '.join(f'{i.product_name} x{i.quantity}' for i in o.items.all())
            writer.writerow([_csv_safe(v) for v in [
                o.order_number, timezone.localtime(o.order_date).strftime('%Y-%m-%d %H:%M'),
                o.customer.name, o.customer.phone, o.delivery_address, o.get_delivery_area_display(), items,
                o.subtotal, o.discount_amount, o.coupon_code, o.delivery_charge, o.total_price,
                o.get_payment_method_display(), o.get_status_display(), 'yes' if o.call_confirmed else 'no']])
        return response


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'min_order_amount', 'times_used_display',
                    'max_uses', 'valid_to', 'is_active')
    list_filter = ('is_active', 'discount_type')
    list_editable = ('is_active',)
    search_fields = ('code',)

    @admin.display(description='Used')
    def times_used_display(self, obj):
        return obj.times_used()


@admin.register(BlockedPhone)
class BlockedPhoneAdmin(admin.ModelAdmin):
    list_display = ('phone', 'reason', 'created_at')
    search_fields = ('phone', 'reason')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_visible', 'created_at')
    list_filter = ('rating', 'is_visible')
    list_editable = ('is_visible',)
    search_fields = ('product__name', 'user__username', 'comment')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__username', 'product__name')


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'sort_order', 'updated_at')
    list_editable = ('is_published', 'sort_order')
    search_fields = ('title', 'content')


@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    """Only one settings row exists; the list page jumps straight to it."""
    fieldsets = (
        ('Delivery and orders', {'fields': ('delivery_charge_inside', 'delivery_charge_outside',
                                            'free_delivery_threshold', 'min_order_amount',
                                            'low_stock_threshold')}),
        ('Contact details (shown in the footer and Contact page)', {
            'fields': ('shop_phone', 'shop_email', 'shop_address', 'opening_hours', 'facebook_url',
                       'whatsapp_number')}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = ShopSettings.load()
        return redirect(reverse('admin:shop_shopsettings_change', args=[obj.pk]))
