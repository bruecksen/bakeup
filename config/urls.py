from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import RedirectView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from bakeup.core.views import HomeView
from bakeup.users.views import LoginView, SignupView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    # path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    # path("impressum/", TemplateView.as_view(template_name="pages/impressum.html"), name="impressum"),
    # path("datenschutz/", TemplateView.as_view(template_name="pages/datenschutz.html"), name="datenschutz"),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("accounts/login/", view=LoginView.as_view(), name="login"),
    path("accounts/signup/", view=SignupView.as_view(), name="signup"),
    path("accounts/", include("allauth.urls")),
    path("users/", include("bakeup.users.urls", namespace="users")),
    path("workshop/", include("bakeup.workshop.urls", namespace="workshop")),
    path("shop/", include("bakeup.shop.urls", namespace="shop")),
    path("shop/", include(wagtail_urls)),
    # path("login/", LoginView.as_view(), name='login'),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "favicon.ico/", RedirectView.as_view(url="/static/images/favicons/favicon.ico")
    ),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
