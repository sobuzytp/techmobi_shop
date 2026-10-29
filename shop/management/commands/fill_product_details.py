from django.core.management.base import BaseCommand

from shop.models import Product
from shop.product_seed import fill_all


class Command(BaseCommand):
    help = "Fill EMPTY detail fields (highlights, specs, box contents, FAQ, AI notes) on existing products."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Show what would change without saving.")
        parser.add_argument('--images', action='store_true',
                            help="Also create a placeholder picture for products that have no image.")

    def handle(self, *args, **opts):
        for name, fields in fill_all(dry_run=opts['dry_run']):
            self.stdout.write(f"{name}: {', '.join(fields)}")
        if opts['images'] and not opts['dry_run']:
            from django.core.files.base import ContentFile
            from django.utils.text import slugify
            from shop.placeholders import make_placeholder
            for p in Product.objects.filter(image='').select_related('category'):
                png = make_placeholder(p.name, p.brand, p.category.name if p.category else '')
                p.image.save(f"placeholder-{slugify(p.name)[:60]}.png", ContentFile(png), save=True)
                self.stdout.write(f"picture added: {p.name}")
        self.stdout.write("")
        self.stdout.write("Details filled (of 13) per product:")
        for p in Product.objects.all():
            filled, total = p.completeness
            self.stdout.write(f"  {filled:>2}/{total}  {p.name}")
        self.stdout.write("Open the admin to add anything still missing (photos, exact colour/storage in stock).")
