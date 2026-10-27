from django.core.management.base import BaseCommand
from shop.models import Category, Product


class Command(BaseCommand):
    help = "Seed the database with sample TechMobi categories and products."

    def handle(self, *args, **options):
        categories = ['Smartphones', 'Tablets', 'Accessories', 'Smartwatches']
        cat_objs = {}
        for name in categories:
            cat, _ = Category.objects.get_or_create(name=name)
            cat_objs[name] = cat

        products = [
            {
                'name': 'TechMobi Nova X12',
                'brand': 'TechMobi', 'ram': '8GB', 'storage': '256GB', 'display': '6.7" AMOLED', 'battery': '5000mAh', 'camera': '108MP', 'color': 'Black, Blue',
                'price': 45999,
                'description': 'Flagship smartphone with a 6.7" AMOLED display, 5000mAh battery, and a 108MP camera.',
                'quantity': 25,
                'category': cat_objs['Smartphones'],
                'is_featured': True,
                'discount_percent': 10,
            },
            {
                'name': 'TechMobi Lite S5',
                'brand': 'TechMobi', 'ram': '4GB', 'storage': '64GB', 'display': '6.5" LCD', 'battery': '5000mAh', 'camera': '50MP', 'color': 'Black, Green',
                'price': 15999,
                'description': 'Affordable everyday smartphone with a 6.5" display and long-lasting battery life.',
                'quantity': 40,
                'category': cat_objs['Smartphones'],
                'is_featured': True,
            },
            {
                'name': 'TechMobi Pro Max 14',
                'brand': 'TechMobi', 'ram': '12GB', 'storage': '512GB', 'display': '6.8" LTPO 120Hz', 'battery': '5200mAh', 'camera': '200MP triple', 'color': 'Titanium',
                'price': 68999,
                'description': 'Premium flagship with titanium frame, triple camera setup, and 120Hz display.',
                'quantity': 12,
                'category': cat_objs['Smartphones'],
                'is_featured': True,
                'discount_percent': 5,
            },
            {
                'name': 'TechMobi Tab Air',
                'brand': 'TechMobi', 'ram': '6GB', 'storage': '128GB', 'display': '10.5" IPS', 'battery': '8000mAh',
                'price': 27999,
                'description': '10.5" tablet perfect for study, work, and entertainment with stylus support.',
                'quantity': 18,
                'category': cat_objs['Tablets'],
                'is_featured': True,
            },
            {
                'name': 'TechMobi Buds Pro',
                'brand': 'TechMobi', 'battery': '30 hours', 'color': 'White, Black',
                'price': 3999,
                'description': 'True wireless earbuds with active noise cancellation and 30-hour battery life.',
                'quantity': 60,
                'category': cat_objs['Accessories'],
                'is_featured': True,
                'discount_percent': 15,
            },
            {
                'name': 'TechMobi FastCharge 65W',
                'brand': 'TechMobi',
                'price': 1799,
                'description': 'GaN fast charger with USB-C PD, compatible with all major smartphone brands.',
                'quantity': 80,
                'category': cat_objs['Accessories'],
            },
            {
                'name': 'TechMobi Watch Fit',
                'brand': 'TechMobi', 'display': '1.4" AMOLED', 'battery': '7 days',
                'price': 5499,
                'description': 'Smartwatch with heart-rate monitoring, SpO2 tracking, and 7-day battery life.',
                'quantity': 30,
                'category': cat_objs['Smartwatches'],
                'is_featured': True,
            },
            {
                'name': 'TechMobi Armor Case',
                'brand': 'TechMobi',
                'price': 899,
                'description': 'Rugged shockproof case with military-grade drop protection.',
                'quantity': 100,
                'category': cat_objs['Accessories'],
            },
        ]

        created = 0
        for data in products:
            _, was_created = Product.objects.get_or_create(name=data['name'], defaults=data)
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(categories)} categories and {created} new products."
        ))
