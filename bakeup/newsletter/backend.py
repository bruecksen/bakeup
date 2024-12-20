import logging
from smtplib import SMTPException
from threading import Thread
from typing import NoReturn, Optional, cast

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import close_old_connections, connection, transaction
from django.template import Context, Template
from django.utils import timezone
from django_tenants.utils import schema_context
from wagtail.models import Page

from bakeup.newsletter.models import (
    Audience,
    CampaignStatus,
    Contact,
    NewsletterPage,
    Segment,
)
from bakeup.pages.models import BrandSettings, EmailSettings

logger = logging.getLogger(__name__)


def send_mass_html_mail(
    email_data, fail_silently=False, auth_user=None, auth_password=None, connection=None
):
    """
    Modified version of send_mass_mail to allow html email
    """
    connection = connection or get_connection(
        username=auth_user,
        password=auth_password,
        fail_silently=fail_silently,
    )

    def _email_from_dict(data):
        if "html_body" not in data:
            html_body = data.pop("body")
        else:
            html_body = data.pop("html_body")
        msg = EmailMultiAlternatives(connection=connection, **data)
        msg.attach_alternative(html_body, "text/html")
        return msg

    messages = [_email_from_dict(d) for d in email_data]
    return connection.send_messages(messages)


class SendCampaignThread(Thread):
    def __init__(self, campaign_pk, contact_pks, messages, schema=None):
        super().__init__()
        self.campaign_pk = campaign_pk
        self.contact_pks = contact_pks
        self.messages = messages
        self.schema = schema

    def run(self):
        with schema_context(self.schema):
            campaign = NewsletterPage.objects.get(pk=self.campaign_pk)
            try:
                logger.info(f"Sending {len(self.messages)} emails")
                send_mass_html_mail(self.messages)
                logger.info("Emails finished sending")
                with transaction.atomic():
                    campaign.status = CampaignStatus.SENT
                    campaign.sent_date = timezone.now()
                    campaign.locked = True
                    campaign.locked_by = campaign.owner
                    campaign.locked_at = timezone.now()
                    campaign.save_revision().publish()
                    campaign.save()
                    fresh_contacts = Contact.objects.filter(pk__in=self.contact_pks)
                    campaign.receipts.add(*fresh_contacts)
            except SMTPException:
                logger.exception(f"Problem sending campaign: {self.campaign_pk}")
                campaign.status = CampaignStatus.FAILED
                campaign.save()
            finally:
                close_old_connections()


class SMTPEmailBackend:
    name = "Simple SMTP"

    def get_audiences(self) -> "list[Audience]":
        return Audience.objects.all()

    def get_audience_segments(self, audience_id) -> "list[Segment]":
        return Segment.objects.filter(id=audience_id)

    def get_campaign(self, campaign_id: str) -> Optional[NewsletterPage]:
        return NewsletterPage.objects.get(pk=campaign_id)

    def replace_message_tags(self, subject, client, contact):
        t = Template(subject)
        subject = t.render(
            Context(
                {
                    "site_name": client.name,
                    "user": contact.get_full_name(),
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "email": contact.email,
                }
            )
        )
        return subject

    def send_test_email(self, tenant, page: Page, user: AbstractUser, email) -> None:
        try:
            messages = []
            revision = cast(NewsletterPage, page.latest_revision.as_object())
            site = tenant.default_site

            from_string = tenant.clientsetting.default_from_email
            from_name = tenant.clientsetting.email_name
            if from_name:
                from_string = f"{from_name} <{from_string}>"
            reply_to = tenant.clientsetting.default_from_email
            email_settings = EmailSettings.load(site)
            subject = revision.newsletter_subject or revision.title
            if email_settings.email_subject_prefix:
                subject = (
                    f"{email_settings.email_subject_prefix} {revision.newsletter_subject or revision.title}"
                )
            subject = self.replace_message_tags(subject, tenant, user.contact)
            html = self.replace_message_tags(
                revision.get_newsletter_html(
                    user.contact,
                    BrandSettings.load(site),
                    email_settings,
                    tenant.default_full_url,
                ),
                tenant,
                user.contact,
            )
            message_data = {
                "subject": subject,
                "from_email": from_string,
                "to": [email],
                "reply_to": [reply_to],
            }
            message_data["html_body"] = html
            messages.append(message_data)
            send_mass_html_mail(messages)

        except Exception as error:
            _log_and_raise(error, "Error while sending campaign", campaign_id=page.pk)

    def send_campaign(self, tenant, page: Page) -> None:
        try:
            messages = []
            revision = cast(NewsletterPage, page.latest_revision.as_object())
            site = tenant.default_site

            from_string = tenant.clientsetting.default_from_email
            from_name = tenant.clientsetting.email_name
            if from_name:
                from_string = f"{from_name} <{from_string}>"
            reply_to = tenant.clientsetting.default_from_email
            recipients = revision.newsletter_recipients
            email_settings = EmailSettings.load(site)
            for contact in recipients.members.all():
                subject = revision.newsletter_subject or revision.title
                if email_settings.email_subject_prefix:
                    subject = (
                        f"{email_settings.email_subject_prefix} {revision.newsletter_subject or revision.title}"
                    )
                subject = self.replace_message_tags(subject, tenant, contact)
                html = self.replace_message_tags(
                    revision.get_newsletter_html(
                        contact,
                        BrandSettings.load(site),
                        email_settings,
                        tenant.default_full_url,
                    ),
                    tenant,
                    contact,
                )
                message_data = {
                    "subject": subject,
                    "from_email": from_string,
                    "to": [contact.email],
                    "reply_to": [reply_to],
                }
                message_data["html_body"] = html
                messages.append(message_data)
            campaign_thread = SendCampaignThread(
                page.pk,
                [c for c in recipients.members.values_list("pk", flat=True)],
                messages,
                connection.schema_name,
            )
            campaign_thread.start()

        except Exception as error:
            _log_and_raise(error, "Error while sending campaign", campaign_id=page.pk)


def _log_and_raise(error: Exception, message: str, **kwargs) -> NoReturn:
    logger.exception(
        f"{message}: {', '.join(f'{key}=%r' for key in kwargs.keys())}",
        *kwargs.values(),
    )
    raise Exception(message) from error


def _require_setting(name):
    value = getattr(settings, name, None)
    if value is None:
        raise ImproperlyConfigured(f"{name} is not set")
    return value
