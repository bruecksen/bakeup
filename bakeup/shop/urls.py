from django.urls import path, re_path, include
from django.utils.translation import gettext_lazy as _

from wagtail import urls as wagtail_urls

from bakeup.shop.views import CustomerOrderTemplatePositionDeleteView, customer_order_template_update, CustomerOrderTemplateDeleteView, CustomerOrderTemplateListView, customer_order_add_or_update, CustomerOrderListView, ProductionDayListView, redirect_to_production_day_view, CustomerOrderUpdateView, CustomerOrderAddView, ProductListView, ShopView, ProductionDayWeeklyView, CustomerOrderPositionDeleteView, CustomerOrderPositionUpdateView
from bakeup.users.views import LoginView, TokenLoginView, SignupView
from bakeup.users.views import (
    shop_user_profile_view,
    shop_user_update_view,
)

#from bakeup.workshop.views import ProductAddView, ProductDetailView, ProductListView


app_name = "shop"
urlpatterns = [
   path("<int:production_day>/", view=ShopView.as_view(), name="shop-production-day"),
#    path("", view=ShopView.as_view(), name="shop"),
   path("redirect/", view=redirect_to_production_day_view, name='redirect-production-day'),
#    path("weekly/", view=ProductionDayWeeklyView.as_view(), name="weekly"),
#    path("weekly/<int:year>/<int:calendar_week>/", view=ProductionDayWeeklyView.as_view(), name="weekly"),
#    path(_("products/"), view=ProductListView.as_view(), name="product-list"),
#    path(_("production-days/"), view=ProductionDayListView.as_view(), name="production-day-list"),
   path("orders/add/<int:production_day>/", view=customer_order_add_or_update, name="customer-order-add"),
#    path("orders/add/<int:production_day_product>/", view=CustomerOrderAddView.as_view(), name="order-add"),
   path("orders/<int:pk>/update/", view=CustomerOrderUpdateView.as_view(), name="customer-order-update"),
   path("orders/positions/<int:pk>/delete/", view=CustomerOrderPositionDeleteView.as_view(), name="customer-order-position-delete"),
   path("orders/positions/<int:pk>/update/", view=CustomerOrderPositionUpdateView.as_view(), name="customer-order-position-update"),
   path(_("orders/"), view=CustomerOrderListView.as_view(), name="order-list"),
   path(_("order-templates/positions/<int:pk>/delete/"), view=CustomerOrderTemplatePositionDeleteView.as_view(), name="customer-order-template-position-delete"),
   path(_("order-templates/<int:pk>/delete/"), view=CustomerOrderTemplateDeleteView.as_view(), name="customer-order-template-delete"),
   path(_("order-templates/positions/<int:pk>/update/"), view=customer_order_template_update, name="customer-order-template-update"),
   path(_("order-templates/"), view=CustomerOrderTemplateListView.as_view(), name="order-template-list"),
   path("profile/", view=shop_user_update_view, name="user-profile"),
    path(_("login/"), view=LoginView.as_view(), name="login"),
    path(_("signup/"), view=SignupView.as_view(), name="signup"),
#    path("product/add/", view=ProductAddView.as_view(), name="product-add"),
#    path("product/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
#    path("product/", view=ProductListView.as_view(), name="product-list"),
]
