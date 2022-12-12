from django.urls import path, include

from bakeup.workshop.views import CategoryListView, CustomerOrderDeleteView, CustomerOrderListView, CustomerOrderUpdateView, ProductionDayDetailView, RecipeListView, RecipeDetailView, ProductAddView, ProductDeleteView, ProductDetailView, ProductHierarchyDeleteView, ProductHierarchyUpdateView, ProductListView, ProductUpdateView, ProductionDayAddView, ProductionDayDeleteView, ProductionDayListView, ProductionDayUpdateView, ProductionPlanAddView, ProductionPlanDeleteView, ProductionPlanDetailView, ProductionPlanListView, ProductionPlanUpdateView, WorkshopView, product_add_inline_view, product_normalize_view, production_plan_cancel_view, production_plan_next_state_view, production_plan_update, CustomerOrderAddView, CreateUpdateInstructionsView


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
    path("production-plans/", view=ProductionPlanListView.as_view(), name="production-plan-list"),
    path("production-plans/<int:pk>/", view=ProductionPlanDetailView.as_view(), name="production-plan-detail"),
    path("production-plans/<int:pk>/next-state/", view=production_plan_next_state_view, name="production-plan-next-state"),
    path("production-plans/<int:pk>/cancel/", view=production_plan_cancel_view, name="production-plan-cancel"),
    path("production-plans/<int:pk>/delete/", view=ProductionPlanDeleteView.as_view(), name="production-plan-delete"),
    path("production-plans/<int:production_day>/<int:product>/update/", view=production_plan_update, name="production-plan-update"),
    path("production-plans/add/", view=ProductionPlanAddView.as_view(), name="production-plan-add"),
    path("production-days/", view=ProductionDayListView.as_view(), name="production-day-list"),
    path("production-days/add/", view=ProductionDayAddView.as_view(), name="production-day-add"),
    path("production-days/<int:pk>/", view=ProductionDayDetailView.as_view(), name="production-day-detail"),
    path("production-days/<int:pk>/update/", view=ProductionDayUpdateView.as_view(), name="production-day-update"),
    path("production-days/<int:pk>/delete/", view=ProductionDayDeleteView.as_view(), name="production-day-delete"),
    path("orders/", view=CustomerOrderListView.as_view(), name="order-list"),
    path("orders/add/", view=CustomerOrderAddView.as_view(), name="order-add"),
    path("orders/add/<int:pk>/", view=CustomerOrderAddView.as_view(), name="order-add"),
    path("orders/<int:pk>/delete/", view=CustomerOrderDeleteView.as_view(), name="order-delete"),
    path("orders/<int:pk>/update/", view=CustomerOrderUpdateView.as_view(), name="order-update"),
]
