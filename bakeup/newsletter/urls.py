from django.urls import path

from .views import (
    activate,
    process_contact_import,
    start_contact_import,
    subscribe_api,
    unsubscribe_user,
)

app_name = "birdsong"

urlpatterns = [
    path("unsubscribe/<uuid:uuid>/", unsubscribe_user, name="unsubscribe"),
    path(
        "unsubscribe/<uuid:uuid>/<int:list_id>/", unsubscribe_user, name="unsubscribe"
    ),
    path("subscribe_api/", subscribe_api, name="subscribe_api"),
    path("activate/<uuid:uuid>/<token>/", activate, name="activate"),
    path("import/", start_contact_import, name="start_import"),
    path("import/process/", process_contact_import, name="process_import"),
]
