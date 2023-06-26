from django.urls import path, include

from bakeup.workshop.views import ProductionDayReminderDeleteView, reminder_message_redirect_view, CustomerDetailView, pos_order_all_picked_up_view, customer_order_all_picked_up_view, customer_order_toggle_picked_up_view, production_plans_finish_view, production_plans_start_view, production_plan_redirect_view, production_day_redirect_view, ProductionDayReminderView, ProductionPlanOfProductionDay, ProductionDayMetaProductView, BatchCustomerTemplateView, CustomerUpdateView, CustomerDeleteView, CategoryListView, CustomerOrderDeleteView, CustomerListView, CustomerOrderListView, CustomerOrderUpdateView, ProductionDayDetailView, RecipeListView, RecipeDetailView, ProductAddView, ProductDeleteView, ProductDetailView, ProductHierarchyDeleteView, ProductHierarchyUpdateView, ProductListView, ProductUpdateView, ProductionDayAddView, ProductionDayDeleteView, ProductionDayListView, ProductionDayUpdateView, ProductionPlanAddView, ProductionPlanDeleteView, ProductionPlanDetailView, ProductionPlanListView, WorkshopView, product_add_inline_view, product_normalize_view, production_plan_cancel_view, production_plan_next_state_view, production_plan_update, CustomerOrderAddView, CreateUpdateInstructionsView


app_name = "workshop"
urlpatterns = [
    path("", view=WorkshopView.as_view(), name="workshop"),
    path("products/add/<int:pk>/", view=ProductAddView.as_view(), name="product-add"),
    path("products/add/", view=ProductAddView.as_view(), name="product-add"),
    path("products/<int:pk>/delete/", view=ProductDeleteView.as_view(), name="product-delete"),
    path("products/<int:pk>/update/", view=ProductUpdateView.as_view(), name="product-update"),
    path("products/<int:pk>/normalize/", view=product_normalize_view, name="product-normalize"),
    path("products/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
    path("products/<int:pk>/add/", view=product_add_inline_view, name="product-add-inline"),
    path("products/<int:pk>/instructions/", view=CreateUpdateInstructionsView.as_view(), name='product-instructions-update'),
    path("products/", view=ProductListView.as_view(), name="product-list"),
    path("recipes/<int:pk>/", view=RecipeDetailView.as_view(), name="recipe-detail"),
    path("recipes/", view=RecipeListView.as_view(), name="recipe-list"),
    path("products/hierarchy/<int:pk>/delete/", view=ProductHierarchyDeleteView.as_view(), name="product-hierarchy-delete"),
    path("products/hierarchy/<int:pk>/update/", view=ProductHierarchyUpdateView.as_view(), name="product-hierarchy-update"),
    path("categories/", view=CategoryListView.as_view(), name="category-list"),
    path("production-plans/", view=production_plan_redirect_view, name="production-plan-next"),
    path("production-plans/production-day/<int:pk>/", view=ProductionPlanOfProductionDay.as_view(), name="production-plan-production-day"),
    path("production-plans/list/", view=ProductionPlanListView.as_view(), name="production-plan-list"),
    path("production-plans/<int:pk>/", view=ProductionPlanDetailView.as_view(), name="production-plan-detail"),
    path("production-plans/<int:production_day>/start/", view=production_plans_start_view, name="production-plans-start"),
    path("production-plans/<int:production_day>/finish/", view=production_plans_finish_view, name="production-plans-finish"),
    path("production-plans/<int:pk>/next-state/", view=production_plan_next_state_view, name="production-plan-next-state"),
    path("production-plans/<int:pk>/cancel/", view=production_plan_cancel_view, name="production-plan-cancel"),
    path("production-plans/<int:pk>/delete/", view=ProductionPlanDeleteView.as_view(), name="production-plan-delete"),
    path("production-plans/<int:production_day>/<int:product>/update/", view=production_plan_update, name="production-plan-update"),
    path("production-plans/add/", view=ProductionPlanAddView.as_view(), name="production-plan-add"),
    path("production-days/", view=production_day_redirect_view, name="production-day-next"),
    path("production-days/list/", view=ProductionDayListView.as_view(), name="production-day-list"),
    path("production-days/add/", view=ProductionDayAddView.as_view(), name="production-day-add"),
    path("production-days/<int:pk>/", view=ProductionDayDetailView.as_view(), name="production-day-detail"),
    path("production-days/<int:pk>/update/", view=ProductionDayUpdateView.as_view(), name="production-day-update"),
    path("production-days/<int:pk>/delete/", view=ProductionDayDeleteView.as_view(), name="production-day-delete"),
    path("production-days/<int:pk>/abo/", view=ProductionDayMetaProductView.as_view(), name="production-day-meta-product"),
    path("production-days/<int:production_day>/reminder/<int:pk>/", view=ProductionDayReminderView.as_view(), name="production-day-reminder"),
    path("production-days/<int:production_day>/reminder/<int:pk>/delete/", view=ProductionDayReminderDeleteView.as_view(), name="production-day-reminder-delete"),
    path("production-days/<int:production_day>/reminder/", view=ProductionDayReminderView.as_view(), name="production-day-reminder"),
    path("production-days/<int:pk>/select-reminder/", view=reminder_message_redirect_view, name="reminder-message-redirect"),
    path("production-days/<int:pk>/all-picked-up/", view=customer_order_all_picked_up_view, name="production-day-all-picked-up"),
    path("production-days/<int:production_day>/<int:pos>/all-picked-up/", view=pos_order_all_picked_up_view, name="pos-all-picked-up"),
    path("orders/", view=CustomerOrderListView.as_view(), name="order-list"),
    path("orders/add/", view=CustomerOrderAddView.as_view(), name="order-add"),
    path("orders/add/<int:pk>/", view=CustomerOrderAddView.as_view(), name="order-add"),
    path("orders/<int:pk>/delete/", view=CustomerOrderDeleteView.as_view(), name="order-delete"),
    path("orders/<int:pk>/update/", view=CustomerOrderUpdateView.as_view(), name="order-update"),
    path("orders/<int:pk>/is-picked-up/", view=customer_order_toggle_picked_up_view, name="order-is-picked-up"),
    path("customers/", view=CustomerListView.as_view(), name="customer-list"),
    path("customers/<int:pk>/", view=CustomerDetailView.as_view(), name="customer-detail"),
    path("customers/abo/", view=BatchCustomerTemplateView.as_view(), name="customer-abo"),
    path("customers/<int:pk>/delete/", view=CustomerDeleteView.as_view(), name="customer-delete"),
    path("customers/<int:pk>/update/", view=CustomerUpdateView.as_view(), name="customer-update"),
]
