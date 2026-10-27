from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:pk>/', views.update_cart, name='update_cart'),
    path('cart/coupon/apply/', views.apply_coupon, name='apply_coupon'),
    path('cart/coupon/remove/', views.remove_coupon, name='remove_coupon'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/', views.order_success, name='order_success'),
    path('track-order/', views.track_order, name='track_order'),

    # accounts
    path('signup/', views.signup, name='signup'),
    path('login/', views.ThrottledLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('my-orders/<str:order_number>/', views.my_order_detail, name='my_order_detail'),
    path('my-orders/<str:order_number>/cancel/', views.cancel_my_order, name='cancel_my_order'),

    # wishlist & reviews
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:pk>/', views.wishlist_toggle, name='wishlist_toggle'),
    path('products/<int:pk>/review/', views.submit_review, name='submit_review'),

    path('pages/<slug:slug>/', views.page_detail, name='page'),

    # staff
    path('dashboard/', views.dashboard, name='dashboard'),
    path('staff/invoice/<str:order_number>/', views.invoice, name='invoice'),
]
