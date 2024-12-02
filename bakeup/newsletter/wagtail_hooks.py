from typing import cast

from django.contrib.auth.models import Permission
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog
from wagtail import hooks
from wagtail.log_actions import LogContext
from wagtail.models import Page

from . import actions, views, viewsets
from .models import CampaignStatus, NewsletterPageMixin


@hooks.register("after_copy_page")  # type: ignore
def clear_campaign_after_copy(request, page, new_page):
    if isinstance(new_page, NewsletterPageMixin):
        new_page = new_page.specific
        new_page.status = CampaignStatus.UNSENT
        new_page.sent_date = None
        new_page.save(update_fields=["status", "sent_date"])
        if new_page.locked:
            new_page.locked = False
            new_page.locked_at = None
            new_page.locked_by = None
            new_page.save(update_fields=["locked", "locked_at", "locked_by"])


@hooks.register("register_admin_urls")  # type: ignore
def register_admin_urls():
    urls = [
        path(
            "jsi18n/",
            JavaScriptCatalog.as_view(packages=["wagtail_newsletter"]),
            name="javascript_catalog",
        ),
        path("recipients/", views.recipients, name="recipients"),
    ]

    return [
        path(
            "newsletter/",
            include(
                (urls, "wagtail_newsletter"),
                namespace="wagtail_newsletter",
            ),
        )
    ]


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


@hooks.register("register_admin_viewset")  # type: ignore
def register_admin_viewset():
    register_viewsets = [
        viewsets.newsletter_viewset_group,
        viewsets.audience_chooser_viewset,
        viewsets.audience_segment_chooser_viewset,
        viewsets.recipients_chooser_viewset,
    ]
    return register_viewsets


@hooks.register("after_create_page")  # type: ignore
@hooks.register("after_edit_page")  # type: ignore
def redirect_to_campaign_page(request, page: Page):
    action = request.POST.get("newsletter-action")

    if action is None:  # pragma: no cover
        return

    page = cast(NewsletterPageMixin, page)

    # if not page.has_newsletter_permission(request.user, action):
    #     messages.error(
    #         request,
    #         f"You do not have permission to perform the newsletter action {action!r}.",
    #     )
    #     return

    with LogContext(user=request.user):
        if action == "save_campaign":
            actions.save_campaign(request, page)

        if action == "send_test_email":
            actions.send_test_email(request, page)

        if action == "send_campaign":
            actions.send_campaign(request, page)


@hooks.register("register_log_actions")  # type: ignore
def register_log_actions(actions):
    actions.register_action(
        "newsletter.save_campaign",
        "Newsletter: Save campaign",
        "Newsletter: Campaign saved",
    )
    actions.register_action(
        "newsletter.send_test_email",
        "Newsletter: Send test email",
        "Newsletter: Test email sent",
    )
    actions.register_action(
        "newsletter.send_campaign",
        "Newsletter: Send campaign",
        "Newsletter: Campaign sent",
    )
