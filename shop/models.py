import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models


class Category(models.Model):
    """Simple product category (e.g. Smartphones, Accessories, Tablets)."""
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Product Name")
    brand = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0, help_text="Available stock quantity")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    is_featured = models.BooleanField(default=False, help_text="Show on homepage as a Featured Product")
    discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)],
        help_text="Discount percentage, e.g. 10 for 10%",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Specifications (all optional, shown on the detail page)
    ram = models.CharField("RAM", max_length=50, blank=True)
    storage = models.CharField(max_length=50, blank=True)
    display = models.CharField(max_length=100, blank=True)
    battery = models.CharField(max_length=50, blank=True)
    camera = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=100, blank=True, help_text="e.g. Black, Blue")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def discounted_price(self):
        if self.discount_percent:
            return (self.price * (100 - self.discount_percent) / 100).quantize(Decimal('0.01'))
        return self.price

    @property
    def in_stock(self):
        return self.quantity > 0

    @property
    def specs(self):
        """List of (label, value) pairs for the non-empty specifications."""
        pairs = [
            ('Brand', self.brand),
            ('RAM', self.ram),
            ('Storage', self.storage),
            ('Display', self.display),
            ('Battery', self.battery),
            ('Camera', self.camera),
            ('Color', self.color),
        ]
        return [(label, value) for label, value in pairs if value]


class ProductImage(models.Model):
    """Extra gallery images for a product."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Image for {self.product.name}"


phone_validator = RegexValidator(
    regex=r'^01[3-9]\d{8}$',
    message="Enter a valid Bangladeshi mobile number, e.g. 01712345678.",
)


class Customer(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    address = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.phone})"


def generate_order_number():
    return 'TM' + secrets.token_hex(4).upper()


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
    ]
    AREA_CHOICES = [
        ('inside', 'Inside Khulna'),
        ('outside', 'Outside Khulna'),
    ]

    order_number = models.CharField(
        max_length=12, unique=True, default=generate_order_number, editable=False
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    delivery_address = models.TextField(blank=True)
    delivery_area = models.CharField(max_length=10, choices=AREA_CHOICES, default='inside')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cod')
    note = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"Order {self.order_number} for {self.customer.name}"

    @staticmethod
    def delivery_charge_for(area):
        return Decimal(str(settings.DELIVERY_CHARGES.get(area, settings.DELIVERY_CHARGES['outside'])))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items'
    )
    # Snapshot of the product at purchase time, so history survives edits/deletes.
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"
