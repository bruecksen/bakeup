from django.urls import path

from bakeup.users.views import (
    TokenLoginView,
    user_profile_view,
    user_update_view,
)

app_name = "users"
urlpatterns = [
    path("update/", view=user_update_view, name="update"),
    path("token/<slug:token>/", TokenLoginView.as_view(), name='login-token'),
    path("token/", TokenLoginView.as_view(), name='login-token'),
]
