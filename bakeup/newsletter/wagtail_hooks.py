from django.contrib.auth.models import Permission
from wagtail import hooks

from . import viewsets


@hooks.register("register_admin_viewset")  # type: ignore
def register_admin_viewset():
    register_viewsets = [
        viewsets.segment_viewset,
    ]
    return register_viewsets


@hooks.register("register_permissions")  # type: ignore
def register_permissions():  # pragma: no cover
    return Permission.objects.filter(
        content_type__app_label="newsletter",
        codename__in=[
            "add_contact",
            "change_contact",
            "delete_contact",
            "sendnewsletter_articlepage",
        ],
    )
