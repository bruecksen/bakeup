from django.urls import path

from bakeup.workshop.views import (
    BatchCustomerTemplateView,
    CategoryAddView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    CreateUpdateInstructionsView,
    CustomerDeleteView,
    CustomerDetailView,
    CustomerListView,
    CustomerOrderAddView,
    CustomerOrderDeleteView,
    CustomerOrderListView,
    CustomerOrderUpdateView,
    CustomerReady2OrderExportView,
    CustomerSevdeskExportView,
    CustomerUpdateView,
    GroupCreateView,
    GroupDeleteView,
    GroupListView,
    GroupUpdateView,
    PointOfSaleCreateView,
    PointOfSaleDeleteView,
    PointOfSaleListView,
    PointOfSaleUpdateView,
    ProductAddView,
    ProductDeleteView,
    ProductDetailView,
    ProductHierarchyDeleteView,
    ProductHierarchyUpdateView,
    ProductionDayAddView,
    ProductionDayDeleteView,
    ProductionDayDetailView,
    ProductionDayExportView,
    ProductionDayListView,
    ProductionDayMetaProductView,
    ProductionDayReminderDeleteView,
    ProductionDayReminderView,
    ProductionDayUpdateView,
    ProductionPlanAddView,
    ProductionPlanDeleteView,
    ProductionPlanDetailView,
    ProductionPlanListView,
    ProductionPlanOfProductionDay,
    ProductListView,
    ProductUpdateView,
    RecipeDetailView,
    RecipeListView,
    WorkshopView,
    customer_order_all_picked_up_view,
    customer_order_toggle_picked_up_view,
    order_max_quantities_view,
    pos_order_all_picked_up_view,
    product_add_inline_view,
    product_normalize_view,
    production_day_redirect_view,
    production_plan_cancel_view,
    production_plan_finish_view,
    production_plan_redirect_view,
    production_plan_start_view,
    production_plan_update,
    production_plans_finish_view,
    production_plans_start_view,
    reminder_message_redirect_view,
)

app_name = "workshop"
urlpatterns = [
    path("", view=WorkshopView.as_view(), name="workshop"),
    path("products/add/<int:pk>/", view=ProductAddView.as_view(), name="product-add"),
    path("products/add/", view=ProductAddView.as_view(), name="product-add"),
    path(
        "products/<int:pk>/delete/",
        view=ProductDeleteView.as_view(),
        name="product-delete",
    ),
    path(
        "products/<int:pk>/update/",
        view=ProductUpdateView.as_view(),
        name="product-update",
    ),
    path(
        "products/<int:pk>/normalize/",
        view=product_normalize_view,
        name="product-normalize",
    ),
    path("products/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<int:pk>/add/",
        view=product_add_inline_view,
        name="product-add-inline",
    ),
    path(
        "products/<int:pk>/instructions/",
        view=CreateUpdateInstructionsView.as_view(),
        name="product-instructions-update",
    ),
    path("products/", view=ProductListView.as_view(), name="product-list"),
    path("recipes/<int:pk>/", view=RecipeDetailView.as_view(), name="recipe-detail"),
    path("recipes/", view=RecipeListView.as_view(), name="recipe-list"),
    path(
        "products/hierarchy/<int:pk>/delete/",
        view=ProductHierarchyDeleteView.as_view(),
        name="product-hierarchy-delete",
    ),
    path(
        "products/hierarchy/<int:pk>/update/",
        view=ProductHierarchyUpdateView.as_view(),
        name="product-hierarchy-update",
    ),
    path("categories/", view=CategoryListView.as_view(), name="category-list"),
    path("categories/add/", view=CategoryAddView.as_view(), name="category-add"),
    path(
        "categories/<int:pk>/update/",
        view=CategoryUpdateView.as_view(),
        name="category-update",
    ),
    path(
        "categories/<int:pk>/delete/",
        view=CategoryDeleteView.as_view(),
        name="category-delete",
    ),
    path(
        "production-plans/",
        view=production_plan_redirect_view,
        name="production-plan-next",
    ),
    path(
        "production-plans/production-day/<int:pk>/",
        view=ProductionPlanOfProductionDay.as_view(),
        name="production-plan-production-day",
    ),
    path(
        "production-plans/list/",
        view=ProductionPlanListView.as_view(),
        name="production-plan-list",
    ),
    path(
        "production-plans/<int:pk>/",
        view=ProductionPlanDetailView.as_view(),
        name="production-plan-detail",
    ),
    path(
        "production-plans/<int:production_day>/start-all/",
        view=production_plans_start_view,
        name="production-plans-start",
    ),
    path(
        "production-plans/<int:production_day>/finish-all/",
        view=production_plans_finish_view,
        name="production-plans-finish",
    ),
    path(
        "production-plans/<int:pk>/finish/",
        view=production_plan_finish_view,
        name="production-plan-finish",
    ),
    path(
        "production-plans/<int:pk>/start/",
        view=production_plan_start_view,
        name="production-plan-start",
    ),
    path(
        "production-plans/<int:pk>/cancel/",
        view=production_plan_cancel_view,
        name="production-plan-cancel",
    ),
    path(
        "production-plans/<int:pk>/delete/",
        view=ProductionPlanDeleteView.as_view(),
        name="production-plan-delete",
    ),
    path(
        "production-plans/<int:pk>/update/",
        view=production_plan_update,
        name="production-plan-update",
    ),
    path(
        "production-plans/add/",
        view=ProductionPlanAddView.as_view(),
        name="production-plan-add",
    ),
    path(
        "production-days/",
        view=production_day_redirect_view,
        name="production-day-next",
    ),
    path(
        "production-days/list/",
        view=ProductionDayListView.as_view(),
        name="production-day-list",
    ),
    path(
        "production-days/add/",
        view=ProductionDayAddView.as_view(),
        name="production-day-add",
    ),
    path(
        "production-days/<int:pk>/",
        view=ProductionDayDetailView.as_view(),
        name="production-day-detail",
    ),
    path(
        "production-days/<int:pk>/export/",
        view=ProductionDayExportView.as_view(),
        name="production-day-export",
    ),
    path(
        "production-days/<int:pk>/update/",
        view=ProductionDayUpdateView.as_view(),
        name="production-day-update",
    ),
    path(
        "production-days/<int:pk>/delete/",
        view=ProductionDayDeleteView.as_view(),
        name="production-day-delete",
    ),
    path(
        "production-days/<int:pk>/abo/",
        view=ProductionDayMetaProductView.as_view(),
        name="production-day-meta-product",
    ),
    path(
        "production-days/<int:production_day>/reminder/<int:pk>/",
        view=ProductionDayReminderView.as_view(),
        name="production-day-reminder",
    ),
    path(
        "production-days/<int:production_day>/reminder/<int:pk>/delete/",
        view=ProductionDayReminderDeleteView.as_view(),
        name="production-day-reminder-delete",
    ),
    path(
        "production-days/<int:production_day>/reminder/",
        view=ProductionDayReminderView.as_view(),
        name="production-day-reminder",
    ),
    path(
        "production-days/<int:pk>/select-reminder/",
        view=reminder_message_redirect_view,
        name="reminder-message-redirect",
    ),
    path(
        "production-days/<int:pk>/all-picked-up/",
        view=customer_order_all_picked_up_view,
        name="production-day-all-picked-up",
    ),
    path(
        "production-days/<int:pk>/order-max-quantities/",
        view=order_max_quantities_view,
        name="production-day-order-max-quantities",
    ),
    path(
        "production-days/<int:production_day>/<int:pos>/all-picked-up/",
        view=pos_order_all_picked_up_view,
        name="pos-all-picked-up",
    ),
    path("orders/", view=CustomerOrderListView.as_view(), name="order-list"),
    path("orders/add/", view=CustomerOrderAddView.as_view(), name="order-add"),
    path("orders/add/<int:pk>/", view=CustomerOrderAddView.as_view(), name="order-add"),
    path(
        "orders/<int:pk>/delete/",
        view=CustomerOrderDeleteView.as_view(),
        name="order-delete",
    ),
    path(
        "orders/<int:pk>/update/",
        view=CustomerOrderUpdateView.as_view(),
        name="order-update",
    ),
    path(
        "orders/<int:pk>/is-picked-up/",
        view=customer_order_toggle_picked_up_view,
        name="order-is-picked-up",
    ),
    path("groups/", view=GroupListView.as_view(), name="group-list"),
    path("groups/add/", view=GroupCreateView.as_view(), name="group-add"),
    path(
        "groups/<int:pk>/delete/", view=GroupDeleteView.as_view(), name="group-delete"
    ),
    path(
        "groups/<int:pk>/update/", view=GroupUpdateView.as_view(), name="group-update"
    ),
    path("customers/", view=CustomerListView.as_view(), name="customer-list"),
    path(
        "customers/export/ready2order/",
        view=CustomerReady2OrderExportView.as_view(),
        name="customer-export-ready-2-order",
    ),
    path(
        "customers/export/sevdesk/",
        view=CustomerSevdeskExportView.as_view(),
        name="customer-export-sevdesk",
    ),
    path(
        "customers/<int:pk>/", view=CustomerDetailView.as_view(), name="customer-detail"
    ),
    path(
        "customers/abo/", view=BatchCustomerTemplateView.as_view(), name="customer-abo"
    ),
    path(
        "customers/<int:pk>/delete/",
        view=CustomerDeleteView.as_view(),
        name="customer-delete",
    ),
    path(
        "customers/<int:pk>/update/",
        view=CustomerUpdateView.as_view(),
        name="customer-update",
    ),
    path(
        "points-of-sale/", view=PointOfSaleListView.as_view(), name="point-of-sale-list"
    ),
    path(
        "points-of-sale/add/",
        view=PointOfSaleCreateView.as_view(),
        name="point-of-sale-add",
    ),
    path(
        "points-of-sale/<int:pk>/update/",
        view=PointOfSaleUpdateView.as_view(),
        name="point-of-sale-update",
    ),
    path(
        "points-of-sale/<int:pk>/delete/",
        view=PointOfSaleDeleteView.as_view(),
        name="point-of-sale-delete",
    ),
]
