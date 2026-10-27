import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import shop.models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0001_initial'),
    ]

    operations = [
        # --- Product: brand + specifications ---
        migrations.AddField(model_name='product', name='brand',
                            field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='product', name='ram',
                            field=models.CharField(blank=True, max_length=50, verbose_name='RAM')),
        migrations.AddField(model_name='product', name='storage',
                            field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='product', name='display',
                            field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='product', name='battery',
                            field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='product', name='camera',
                            field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='product', name='color',
                            field=models.CharField(blank=True, help_text='e.g. Black, Blue', max_length=100)),
        migrations.AlterField(
            model_name='product', name='discount_percent',
            field=models.PositiveIntegerField(
                default=0, help_text='Discount percentage, e.g. 10 for 10%',
                validators=[django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='products/gallery/')),
                ('alt_text', models.CharField(blank=True, max_length=200)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='gallery', to='shop.product')),
            ],
        ),

        # --- Customer: phone validation ---
        migrations.AlterField(
            model_name='customer', name='phone',
            field=models.CharField(max_length=20, validators=[shop.models.phone_validator]),
        ),

        # --- Order: new fields (order_number is nullable until backfilled in 0003) ---
        migrations.AddField(model_name='order', name='order_number',
                            field=models.CharField(editable=False, max_length=12, null=True)),
        migrations.AddField(model_name='order', name='delivery_address',
                            field=models.TextField(blank=True)),
        migrations.AddField(model_name='order', name='delivery_area',
                            field=models.CharField(choices=[('inside', 'Inside Khulna'), ('outside', 'Outside Khulna')],
                                                   default='inside', max_length=10)),
        migrations.AddField(model_name='order', name='payment_method',
                            field=models.CharField(choices=[('cod', 'Cash on Delivery')], default='cod', max_length=10)),
        migrations.AddField(model_name='order', name='note',
                            field=models.TextField(blank=True)),
        migrations.AddField(model_name='order', name='subtotal',
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.AddField(model_name='order', name='delivery_charge',
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=8)),
        migrations.AlterField(
            model_name='order', name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('shipped', 'Shipped'),
                         ('delivered', 'Delivered'), ('cancelled', 'Cancelled')],
                default='pending', max_length=20),
        ),

        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(max_length=200)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('line_total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='items', to='shop.order')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                              related_name='order_items', to='shop.product')),
            ],
        ),
    ]
