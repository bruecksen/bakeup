from django.urls import path

from bakeup.workshop.views import ProductAddView


app_name = "workshop"
urlpatterns = [
    path("product/add/", view=ProductAddView.as_view(), name="product-add"),
]
