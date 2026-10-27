from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Product


class StaticViewSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8
    protocol = 'http' if settings.DEBUG else 'https'

    def items(self):
        return ['shop:home', 'shop:product_list']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7
    protocol = 'http' if settings.DEBUG else 'https'

    def items(self):
        return Product.objects.all()

    def lastmod(self, obj):
        return obj.created_at
