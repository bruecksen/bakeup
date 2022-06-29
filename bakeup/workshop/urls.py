from django.urls import path

from bakeup.workshop.views import CategoryListView, RecipeListView, RecipeDetailView, ProductAddView, ProductDeleteView, ProductDetailView, ProductHierarchyDeleteView, ProductHierarchyUpdateView, ProductListView, ProductUpdateView, ProductionDayAddView, ProductionDayDeleteView, ProductionDayListView, ProductionDayUpdateView, ProductionPlanAddView, ProductionPlanDeleteView, ProductionPlanDetailView, ProductionPlanListView, ProductionPlanUpdateView, WorkshopView, product_normalize_view


app_name = "workshop"
urlpatterns = [
    path("", view=WorkshopView.as_view(), name="workshop"),
    path("products/add/<int:pk>/", view=ProductAddView.as_view(), name="product-add"),
    path("products/add/", view=ProductAddView.as_view(), name="product-add"),
    path("products/<int:pk>/delete/", view=ProductDeleteView.as_view(), name="product-delete"),
    path("products/<int:pk>/update/", view=ProductUpdateView.as_view(), name="product-update"),
    path("products/<int:pk>/normalize/", view=product_normalize_view, name="product-normalize"),
    path("products/<int:pk>/", view=ProductDetailView.as_view(), name="product-detail"),
    path("products/", view=ProductListView.as_view(), name="product-list"),
    path("recipies/<int:pk>/", view=RecipeDetailView.as_view(), name="recipe-detail"),
    path("recipies/", view=RecipeListView.as_view(), name="recipe-list"),
    path("products/hierarchy/<int:pk>/delete/", view=ProductHierarchyDeleteView.as_view(), name="product-hierarchy-delete"),
    path("products/hierarchy/<int:pk>/update/", view=ProductHierarchyUpdateView.as_view(), name="product-hierarchy-update"),
    path("categories/", view=CategoryListView.as_view(), name="category-list"),
    path("production-plans/", view=ProductionPlanListView.as_view(), name="production-plan-list"),
    path("production-plans/<int:pk>/", view=ProductionPlanDetailView.as_view(), name="production-plan-detail"),
    path("production-plans/<int:pk>/delete/", view=ProductionPlanDeleteView.as_view(), name="production-plan-delete"),
    path("production-plans/<int:pk>/update/", view=ProductionPlanUpdateView.as_view(), name="production-plan-update"),
    path("production-plans/add/", view=ProductionPlanAddView.as_view(), name="production-plan-add"),
    path("production-days/", view=ProductionDayListView.as_view(), name="production-day-list"),
    path("production-days/add/", view=ProductionDayAddView.as_view(), name="production-day-add"),
    path("production-days/<int:pk>/update/", view=ProductionDayUpdateView.as_view(), name="production-day-update"),
    path("production-days/<int:pk>/delete/", view=ProductionDayDeleteView.as_view(), name="production-day-delete"),
]
