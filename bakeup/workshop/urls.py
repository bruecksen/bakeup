from django.urls import path

from bakeup.workshop.views import CategoryListView, ProductAddView, ProductDeleteView, ProductDetailView, ProductListView, ProductUpdateView


app_name = "workshop"
urlpatterns = [
    path("products/add/", view=ProductAddView.as_view(), name="product-add"),
    path("products/<int:pk>/delete/", view=ProductDeleteView.as_view(), name="product-delete"),
    path("products/<int:pk>/update/", view=ProductUpdateView.as_view(), name="product-update"),
    path("products/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
    path("products/", view=ProductListView.as_view(), name="product-list"),
    path("categories/", view=CategoryListView.as_view(), name="category-list"),
]
