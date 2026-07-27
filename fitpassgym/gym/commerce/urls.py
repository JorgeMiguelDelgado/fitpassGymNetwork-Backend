from django.urls import path

from . import api

urlpatterns = [
    path("products/", api.product_list, name="products"),
    path("products/<int:product_id>/purchases/", api.buy_product, name="purchase"),
]
