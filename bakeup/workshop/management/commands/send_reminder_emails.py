from django.core.management.base import BaseCommand

from bakeup.workshop.models import ReminderMessage


class Command(BaseCommand):
    help = "Sends reminder emails to customers who have placed an order"

    def handle(self, *args, **options):
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
