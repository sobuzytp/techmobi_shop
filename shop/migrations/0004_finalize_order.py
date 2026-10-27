from django.db import migrations, models

import shop.models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_backfill_order_items'),
    ]

    operations = [
        migrations.RemoveField(model_name='order', name='product'),
        migrations.RemoveField(model_name='order', name='quantity'),
        migrations.AlterField(
            model_name='order', name='order_number',
            field=models.CharField(default=shop.models.generate_order_number, editable=False,
                                   max_length=12, unique=True),
        ),
    ]
