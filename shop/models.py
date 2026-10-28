import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


def warranty_text(months):
    """12 -> '1 year', 18 -> '18 months', 0 -> ''."""
    if not months:
        return ''
    if months % 12 == 0:
        years = months // 12
        return f"{years} year{'s' if years > 1 else ''}"
    return f"{months} month{'s' if months > 1 else ''}"


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

    CONDITION_CHOICES = [('new', 'New'), ('used', 'Used'), ('refurbished', 'Refurbished')]
    condition = models.CharField(max_length=12, choices=CONDITION_CHOICES, default='new')
    warranty_months = models.PositiveIntegerField(
        default=0, help_text="Warranty in months. 0 = no warranty.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.pk])

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
            ('Condition', self.get_condition_display()),
            ('Warranty', self.warranty_label),
        ]
        return [(label, value) for label, value in pairs if value]

    @property
    def warranty_label(self):
        return warranty_text(self.warranty_months)


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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', help_text="Set when the customer was logged in at checkout.",
    )
    delivery_address = models.TextField(blank=True)
    delivery_area = models.CharField(max_length=10, choices=AREA_CHOICES, default='inside')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cod')
    note = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    coupon_code = models.CharField(max_length=30, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    call_confirmed = models.BooleanField(
        default=False, help_text="Tick after you have confirmed this order with the customer by phone.")
    stock_restored = models.BooleanField(default=False, editable=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"Order {self.order_number} for {self.customer.name}"

    @property
    def can_customer_cancel(self):
        return self.status == 'pending' and not self.call_confirmed

    @property
    def status_step(self):
        """Position in the pending -> delivered timeline (0-3), or -1 if cancelled."""
        order = ['pending', 'confirmed', 'shipped', 'delivered']
        return order.index(self.status) if self.status in order else -1


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
    warranty_months = models.PositiveIntegerField(default=0)
    imei = models.CharField(
        "IMEI / serial", max_length=120, blank=True,
        help_text="Fill in before shipping. Separate several numbers with commas. Shown on the invoice.")

    @property
    def warranty_label(self):
        return warranty_text(self.warranty_months)

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class ShopSettings(models.Model):
    """Single row of shop-wide settings, editable from the admin."""
    delivery_charge_inside = models.DecimalField(max_digits=8, decimal_places=2, default=60,
                                                 verbose_name="Delivery charge: Inside Khulna (Tk)")
    delivery_charge_outside = models.DecimalField(max_digits=8, decimal_places=2, default=120,
                                                  verbose_name="Delivery charge: Outside Khulna (Tk)")
    free_delivery_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Delivery is free when the order (after discount) reaches this amount. 0 = off.")
    min_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Smallest order total accepted. 0 = no minimum.")
    low_stock_threshold = models.PositiveIntegerField(
        default=5, help_text="Products at or below this quantity show up as low stock.")
    whatsapp_number = models.CharField(
        max_length=20, blank=True,
        help_text="With country code, digits only, e.g. 8801712345678. Shows an 'Order on WhatsApp' button.")
    shop_phone = models.CharField(max_length=40, default='+880 1601642548')
    shop_email = models.EmailField(default='support@techmobi.abrakadabra.sobuj')
    shop_address = models.CharField(max_length=200, default='Khulna, Bangladesh')
    opening_hours = models.CharField(max_length=120, blank=True, help_text="e.g. Sat-Thu, 10am - 9pm")
    facebook_url = models.URLField(blank=True)

    class Meta:
        verbose_name = "Shop settings"
        verbose_name_plural = "Shop settings"

    def __str__(self):
        return "Shop settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        defaults = {
            'delivery_charge_inside': settings.DELIVERY_CHARGES['inside'],
            'delivery_charge_outside': settings.DELIVERY_CHARGES['outside'],
        }
        obj, _ = cls.objects.get_or_create(pk=1, defaults=defaults)
        return obj

    def delivery_charge_for(self, area, amount):
        """Delivery charge for an order of `amount` (after discount) going to `area`."""
        if self.free_delivery_threshold and amount >= self.free_delivery_threshold:
            return Decimal('0.00')
        charge = self.delivery_charge_inside if area == 'inside' else self.delivery_charge_outside
        return Decimal(charge)


class Coupon(models.Model):
    PERCENT = 'percent'
    FIXED = 'fixed'
    TYPE_CHOICES = [(PERCENT, 'Percent (%)'), (FIXED, 'Fixed amount (Tk)')]

    code = models.CharField(max_length=30, unique=True, help_text="Letters/numbers, stored in capitals.")
    discount_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    max_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cap for percent coupons (Tk). 0 = no cap.")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(default=0, help_text="Total uses allowed. 0 = unlimited.")
    per_user_limit = models.PositiveIntegerField(default=1, help_text="Uses per customer. 0 = unlimited.")
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def times_used(self, user=None):
        qs = self.orders.exclude(status='cancelled')
        if user is not None:
            qs = qs.filter(user=user)
        return qs.count()

    def validate_for(self, subtotal, user):
        """Return (ok, message). `subtotal` is the cart total before discount."""
        now = timezone.now()
        if not self.is_active:
            return False, "This coupon is not active."
        if self.valid_from and now < self.valid_from:
            return False, "This coupon is not valid yet."
        if self.valid_to and now > self.valid_to:
            return False, "This coupon has expired."
        if subtotal < self.min_order_amount:
            return False, f"This coupon needs an order of at least Tk {self.min_order_amount:.0f}."
        if self.max_uses and self.times_used() >= self.max_uses:
            return False, "This coupon has been fully used."
        if self.per_user_limit and user is not None and user.is_authenticated \
                and self.times_used(user) >= self.per_user_limit:
            return False, "You have already used this coupon."
        return True, ""

    def discount_for(self, subtotal):
        if self.discount_type == self.PERCENT:
            amount = (subtotal * self.value / 100).quantize(Decimal('0.01'))
            if self.max_discount:
                amount = min(amount, self.max_discount)
        else:
            amount = self.value
        return min(amount, subtotal)


class BlockedPhone(models.Model):
    """Phone numbers that cannot sign up or place orders (fake / abusive orders)."""
    phone = models.CharField(max_length=20, unique=True, validators=[phone_validator])
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.phone


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='unique_wishlist_item')]

    def __str__(self):
        return f"{self.user} likes {self.product}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, max_length=1000)
    is_visible = models.BooleanField(default=True, help_text="Untick to hide this review from the site.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='one_review_per_user_product')]

    def __str__(self):
        return f"{self.rating}/5 for {self.product}"


class Banner(models.Model):
    """Offer banner shown at the top of the home page."""
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=200, blank=True)
    image = models.ImageField(
        upload_to='banners/', blank=True, null=True,
        help_text="Wide image, about 1600 x 500 pixels. If you add an image it is shown as it is, so put "
                  "your text inside the image. Without an image, the title and subtitle are shown on a coloured banner.")
    link = models.CharField(max_length=300, blank=True, help_text="Where the banner goes, e.g. /products/?category=1")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', '-id']

    def __str__(self):
        return self.title


class Page(models.Model):
    """Simple text pages (About, Contact, policies) the shop owner can edit in the admin."""
    slug = models.SlugField(unique=True, help_text="Part of the web address, e.g. return-policy")
    title = models.CharField(max_length=120)
    content = models.TextField(help_text="Plain text. Blank lines start a new paragraph.")
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('shop:page', args=[self.slug])


class ThrottleEntry(models.Model):
    """Counts attempts per key inside a time window (used for rate limiting)."""
    key = models.CharField(max_length=120, unique=True)
    count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.key}: {self.count}"
