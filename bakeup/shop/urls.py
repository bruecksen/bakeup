from django.urls import path

from bakeup.shop.views import ProductListView, ShopView, WeeklyProductionDayView

#from bakeup.workshop.views import ProductAddView, ProductDetailView, ProductListView


app_name = "shop"
urlpatterns = [
   path("", view=ShopView.as_view(), name="shop"),
   path("weekly/", view=WeeklyProductionDayView.as_view(), name="weekly"),
   path("weekly/<int:year>/<int:calendar_week>/", view=WeeklyProductionDayView.as_view(), name="weekly"),
   path("products/", view=ProductListView.as_view(), name="product-list"),
#    path("product/add/", view=ProductAddView.as_view(), name="product-add"),
#    path("product/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
#    path("product/", view=ProductListView.as_view(), name="product-list"),
]
