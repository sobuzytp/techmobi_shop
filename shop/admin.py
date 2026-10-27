from django.contrib import admin

from .models import Category, Product, ProductImage, Customer, Order, OrderItem


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
    list_display = ('name', 'brand', 'category', 'price', 'discount_percent', 'quantity', 'is_featured', 'created_at')
    list_filter = ('category', 'is_featured', LowStockFilter)
    search_fields = ('name', 'brand', 'description')
    list_editable = ('price', 'quantity', 'is_featured', 'discount_percent')
    inlines = [ProductImageInline]
    fieldsets = (
        (None, {'fields': ('name', 'brand', 'category', 'price', 'discount_percent', 'quantity',
                           'is_featured', 'image', 'description')}),
        ('Specifications', {'fields': ('ram', 'storage', 'display', 'battery', 'camera', 'color')}),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')
    search_fields = ('name', 'phone')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'unit_price', 'quantity', 'line_total')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'delivery_area', 'payment_method',
                    'total_price', 'status', 'order_date')
    list_filter = ('status', 'delivery_area', 'payment_method', 'order_date')
    list_editable = ('status',)
    search_fields = ('order_number', 'customer__name', 'customer__phone')
    readonly_fields = ('order_number', 'subtotal', 'delivery_charge', 'total_price', 'order_date')
    inlines = [OrderItemInline]
