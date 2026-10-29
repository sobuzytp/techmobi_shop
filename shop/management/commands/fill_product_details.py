from django.core.management.base import BaseCommand

from shop.models import Product
from shop.product_seed import fill_all


class Command(BaseCommand):
    help = "Fill EMPTY detail fields (highlights, specs, box contents, FAQ, AI notes) on existing products."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Show what would change without saving.")

    def handle(self, *args, **opts):
        for name, fields in fill_all(dry_run=opts['dry_run']):
            self.stdout.write(f"{name}: {', '.join(fields)}")
        self.stdout.write("")
        self.stdout.write("Details filled (of 13) per product:")
        for p in Product.objects.all():
            filled, total = p.completeness
            self.stdout.write(f"  {filled:>2}/{total}  {p.name}")
        self.stdout.write("Open the admin to add anything still missing (photos, exact colour/storage in stock).")
