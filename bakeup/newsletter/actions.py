from django.utils import timezone
from wagtail.admin import messages
from wagtail.log_actions import log

from bakeup.newsletter import get_backend
from bakeup.newsletter.forms import SendTestEmailForm
from bakeup.newsletter.models import CampaignStatus, NewsletterPageMixin


def send_test_email(request, page: NewsletterPageMixin) -> None:
    form = SendTestEmailForm(request.POST, prefix="newsletter-test")
    if not form.is_valid():
        for field, errors in form.errors.items():
            for message in errors:
                messages.error(request, f"{field!r}: {message}")
        return

    email = form.cleaned_data["email"]
    backend = get_backend()
    backend.send_test_email(
        tenant=request.tenant,
        page=page,
        user=request.user,
        email=email,
    )

    log(page, "newsletter.send_test_email", data={"email": email})

    messages.success(request, f"Test message sent to {email!r}")


def send_campaign(request, page: NewsletterPageMixin) -> None:
    if (
        not page.newsletter_schedule_date
        or page.newsletter_schedule_date < timezone.now()
    ):
        backend = get_backend()
        page.status = CampaignStatus.SENDING
        # lock page
        page.locked = True
        page.locked_by = request.user
        page.locked_at = timezone.now()
        page.save_revision().publish()
        backend.send_campaign(
            tenant=request.tenant,
            page=page,
        )
    else:
        page.status = CampaignStatus.SCHEDULED
        # lock page
        page.locked = True
        page.locked_by = request.user
        page.locked_at = timezone.now()
        page.save_revision().publish()

    log(page, "newsletter.send_campaign")

    messages.success(request, "Newsletter campaign is now sending")
