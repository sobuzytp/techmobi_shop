from django.urls import path

from . import api

app_name = 'api'

urlpatterns = [
    path('', api.api_root, name='root'),
    path('products/', api.api_products, name='products'),
    path('products/<int:pk>/', api.api_product, name='product'),
    path('categories/', api.api_categories, name='categories'),
    path('shop/', api.api_shop, name='shop'),
    path('pages/', api.api_pages, name='pages'),
    path('feed.csv', api.product_feed, name='feed'),
]
