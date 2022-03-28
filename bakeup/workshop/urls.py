from django.urls import path

from bakeup.workshop.views import ProductAddView, ProductDeleteView, ProductDetailView, ProductListView


app_name = "workshop"
urlpatterns = [
    path("product/add/", view=ProductAddView.as_view(), name="product-add"),
    path("product/<int:pk>/delete/", view=ProductDeleteView.as_view(), name="product-delete"),
    path("product/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
    path("product/", view=ProductListView.as_view(), name="product-list"),
]
