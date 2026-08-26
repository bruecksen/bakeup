from django.utils import timezone

from bakeup.core.management.base import PerTenantCommand
from bakeup.core.tenant_settings import TenantSettings
from bakeup.newsletter import get_backend
from bakeup.newsletter.models import CampaignStatus, NewsletterPage


class Command(PerTenantCommand):
    help = "Sends scheduled newsletter"

    def handle_tenant(self, tenant, *args, **options):
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
            self.stdout.write(self.style.SUCCESS("Successfully send all newsletters"))
