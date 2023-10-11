from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import get_tenant_model

from bakeup.core.tenant_settings import TenantSettings
from bakeup.workshop.models import ReminderMessage


class Command(BaseCommand):
    help = "Sends reminder emails to customers who have placed an order"

    def handle(self, *args, **options):
        current_schema_obj = get_tenant_model().objects.get(
            schema_name=connection.schema_name
        )
        TenantSettings.overload_settings(current_schema_obj)
        for reminder_message in ReminderMessage.objects.filter(
            state=ReminderMessage.State.PLANNED_SENDING
        ):
            self.stdout.write(
                "Sending all reminder messages: {}".format(reminder_message)
            )
            reminder_message.set_state_to_sending()
            reminder_message.send_messages()
            self.stdout.write(
                self.style.SUCCESS("Successfully send all reminder messages")
            )
