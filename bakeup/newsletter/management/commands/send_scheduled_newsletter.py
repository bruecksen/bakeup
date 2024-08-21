from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from django_tenants.utils import get_tenant_model

from bakeup.core.tenant_settings import TenantSettings
from bakeup.newsletter import get_backend
from bakeup.newsletter.models import CampaignStatus, NewsletterPage


class Command(BaseCommand):
    help = "Sends scheduled newsletter"

    def handle(self, *args, **options):
        tenant = get_tenant_model().objects.get(schema_name=connection.schema_name)
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
