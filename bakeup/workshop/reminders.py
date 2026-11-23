"""The pickup emails of a production day: its texts, what was sent and what
is left to send.

A ReminderMessage is one of two things:

- A text, in the state PLANNED: the text of the day has no point of sale, a
  point of sale's own text has one. A day has at most one of each, the
  newest counts if older ones are left over from before.
- A mail, queued (PLANNED_SENDING), being sent (SENDING) or sent (SENT). A
  mail without a point of sale goes to all orders of the day, one with a
  point of sale to the orders of that point (ReminderMessage.get_orders).

Sending never changes a text, the text is copied into a new mail, so the
text of the day stays for the next mail. The management command
send_reminder_emails sends the queued mails.

The status is worked out from the orders and the mails in two queries, so a
later "only the orders since the last mail" can compare the orders with the
send_log of the mails of their point.
"""

from django.template import TemplateSyntaxError
from django.utils.translation import gettext_lazy as _

from bakeup.pages.models import EmailSettings
from bakeup.workshop.models import ReminderMessage

MAIL_STATES = (
    ReminderMessage.State.PLANNED_SENDING,
    ReminderMessage.State.SENDING,
    ReminderMessage.State.SENT,
)


def get_day_texts(production_day):
    """The texts of the day by point of sale id, None is the text of the day."""
    texts = {}
    for text in ReminderMessage.objects.filter(
        production_day=production_day, state=ReminderMessage.State.PLANNED
    ).order_by("pk"):
        texts[text.point_of_sale_id] = text
    return texts


def get_default_text(request, production_day):
    """The text of the day before it was changed, from the email settings."""
    email_settings = EmailSettings.load(request_or_site=request)
    return ReminderMessage(
        production_day=production_day,
        subject=email_settings.get_subject_with_prefix(
            email_settings.production_day_reminder_subject
        ),
        body=email_settings.production_day_reminder_body,
    )


def get_mail_counts(mails, emails=None):
    """Delivered and failed recipients of mails, within emails if given. A
    recipient that failed once and was reached by a later mail counts as
    delivered."""
    delivered = set()
    failed = set()
    for mail in mails:
        if not mail.is_sent:
            continue
        delivered.update(mail.send_log or [])
        failed.update((mail.error_log or {}).keys())
    if emails is not None:
        delivered &= emails
        failed &= emails
    return {"delivered": len(delivered), "failed": len(failed - delivered)}


def get_mail_state(mails):
    """What the newest of the mails is: queued, being sent or sent."""
    if not mails:
        return "none"
    latest = mails[-1]
    if latest.is_planned_sending:
        return "queued"
    if latest.is_sending:
        return "sending"
    return "sent"


def get_reminder_overview(production_day, texts):
    """The pickup emails of the day: its state, one row per point of sale
    with orders and the history of its mails."""
    orders = list(
        production_day.customer_orders.select_related(
            "customer__user", "point_of_sale"
        ).order_by("point_of_sale__name", "pk")
    )
    mails = list(
        ReminderMessage.objects.filter(
            production_day=production_day, state__in=MAIL_STATES
        )
        .select_related("point_of_sale")
        .order_by("created", "pk")
    )
    rows = {}
    for order in orders:
        row = rows.setdefault(
            order.point_of_sale_id,
            {
                "point_of_sale": order.point_of_sale,
                "orders": 0,
                "emails": set(),
                "own_text": texts.get(order.point_of_sale_id)
                if order.point_of_sale_id
                else None,
            },
        )
        row["orders"] += 1
        if order.customer:
            row["emails"].add(order.customer.user.email)
    for key, row in rows.items():
        # A mail to all reaches every point, one to a point only that one.
        row["mails"] = [
            mail
            for mail in mails
            if mail.point_of_sale_id is None or mail.point_of_sale_id == key
        ]
        row["state"] = get_mail_state(row["mails"])
        row["is_notified"] = bool(row["mails"])
        row.update(get_mail_counts(row["mails"], row["emails"]))
        if row["mails"]:
            row["last_mail"] = row["mails"][-1]
    points = sorted(
        (row for key, row in rows.items() if key is not None),
        key=lambda row: row["point_of_sale"].name.lower(),
    )
    without = rows.get(None)
    pending = [mail for mail in mails if not mail.is_sent]
    notified = [row for row in points if row["is_notified"]]
    remaining = [row for row in points if not row["is_notified"]]
    to_all = [mail for mail in mails if mail.point_of_sale_id is None]
    if pending:
        state = "sending" if pending[-1].is_sending else "queued"
    elif to_all or (mails and not remaining):
        state = "sent"
    elif notified:
        state = "partly"
    else:
        state = "none"
    sent = [mail for mail in mails if mail.is_sent]
    return {
        "state": state,
        "orders": len(orders),
        "points": points,
        "without_point": without,
        # The per point section is for days with more than one place to
        # pick up.
        "has_points": len(points) + bool(without) > 1,
        "notified": len(notified),
        "remaining": remaining,
        "remaining_orders": sum(row["orders"] for row in remaining),
        # Mails go to all orders while no point has its own mail or text,
        # otherwise to the points one by one, see queue_reminders.
        "by_point": bool(notified) or any(row["own_text"] for row in points),
        "mails": mails,
        "pending": pending,
        "last_sent": sent[-1] if sent else None,
        **get_mail_counts(mails),
    }


def queue_mail(production_day, text, point_of_sale=None):
    """A new mail from a text, queued for the command that sends it."""
    return ReminderMessage.objects.create(
        production_day=production_day,
        point_of_sale=point_of_sale,
        subject=text.subject,
        body=text.body,
        state=ReminderMessage.State.PLANNED_SENDING,
    )


def queue_reminders(overview, day_text, target):
    """Queues the mails for "all", "rest" or one point of sale (its id).

    "all" is one mail to all orders while no point has been notified and no
    point has its own text. Otherwise it is the same as "rest": one mail to
    each point not notified yet, with its own text or the text of the day.
    That way a point that was told already is never told again. Orders
    without a point of sale are only reached by a mail to all.
    """
    production_day = day_text.production_day
    if target == "all" and not overview["by_point"]:
        return [queue_mail(production_day, day_text)]
    if target in ("all", "rest"):
        rows = overview["remaining"]
    else:
        rows = [
            row
            for row in overview["points"]
            if str(row["point_of_sale"].pk) == str(target)
        ]
    return [
        queue_mail(production_day, row["own_text"] or day_text, row["point_of_sale"])
        for row in rows
    ]


def get_preview_order(production_day, point_of_sale=None):
    """An order of the day to fill in the placeholders, of the point of sale
    if given, or None."""
    orders = production_day.customer_orders.filter(
        customer__isnull=False
    ).select_related("customer__user", "point_of_sale")
    if point_of_sale:
        orders = orders.filter(point_of_sale=point_of_sale)
    return orders.order_by("pk").first()


def fill_reminder(text, production_day, client, order=None, dummy=None):
    """Subject and body of a text as a customer gets them: with the order if
    given, otherwise with the example of dummy (order, user)."""
    message = ReminderMessage(production_day=production_day)
    order, user = (order, order.customer.user) if order else dummy

    def fill(value):
        try:
            return message.replace_message_tags(
                value or "", order, user, client, production_day
            )
        except TemplateSyntaxError:
            return value or ""

    return {"subject": fill(text.subject), "body": fill(text.body)}


def get_reminder_badge(production_day, order_points):
    """The badge of the pickup emails tab: nothing while nothing is sent, a
    check when every point is notified, "3 / 11" when some are. One query,
    order_points are the point of sale ids of the orders of the day."""
    mails = list(
        ReminderMessage.objects.filter(
            production_day=production_day, state__in=MAIL_STATES
        ).values_list("point_of_sale_id", flat=True)
    )
    if not mails:
        return None
    points = {point for point in order_points if point is not None}
    if None in mails or not points:
        return "✓"
    notified = points & set(mails)
    if notified == points:
        return "✓"
    return _("%(notified)s / %(points)s") % {
        "notified": len(notified),
        "points": len(points),
    }
