from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from django_tenants.management.commands import InteractiveTenantOption

from bakeup.core.tenant_settings import TenantSettings
from bakeup.newsletter import get_backend
from bakeup.newsletter.models import CampaignStatus, NewsletterPage


class Command(InteractiveTenantOption, BaseCommand):
    help = "Sends scheduled newsletter"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "-s", "--schema", dest="schema_name", help="specify tenant schema"
        )

    def handle(self, *args, **options):
        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)
        TenantSettings.overload_settings(tenant)
        scheduled_newsletters = NewsletterPage.objects.filter(
            status=CampaignStatus.SCHEDULED,
            newsletter_schedule_date__lte=timezone.now(),
        )
        for newsletter in scheduled_newsletters:
            self.stdout.write("Sending newsletter: {}".format(newsletter))
            backend = get_backend()
            newsletter.status = CampaignStatus.SENDING
            # lock page
            newsletter.locked = True
            newsletter.locked_by = newsletter.owner
            newsletter.locked_at = timezone.now()
            newsletter.save_revision().publish()
            backend.send_campaign(
                tenant,
                newsletter,
            )
            self.stdout.write(
                self.style.SUCCESS("Successfully send all reminder messages")
            )
