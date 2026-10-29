from django.db import migrations


def fill(apps, schema_editor):
    # Only empty fields are filled, so nothing typed by the owner is lost.
    from shop.product_seed import fill_all
    fill_all(model=apps.get_model('shop', 'Product'))


class Migration(migrations.Migration):

    dependencies = [('shop', '0011_product_details')]

    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
