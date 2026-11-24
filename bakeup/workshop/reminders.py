"""The pickup emails of a production day: its texts, what was sent and what
is left to send.

A ReminderMessage is one of two things:

- A text, in the state PLANNED: the text of the day has no point of sale, a
  point of sale's own text has one. A day has at most one of each, the
  newest counts if older ones are left over from before.
- A mail, queued (PLANNED_SENDING), being sent (SENDING) or sent (SENT). It
  keeps the orders it goes to (ReminderMessage.orders), set when it is
  queued. Its point of sale only says which row sent it, None for a mail to
  all or to the rest.

"Send to all" is one mail with the text of the day to every order of the
day. "Send to the others" is one mail with the text of the day to the orders
no mail went to yet, also the ones that came in after the last mail. A
point's own text is only used when that point is sent on its own.

Sending never changes a text, the text is copied into a new mail, so the
text of the day stays for the next mail. The management command
send_reminder_emails sends the queued mails.

The status is worked out per order, from the orders, the mails and the
orders of the mails, three queries.
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


def get_mail_orders(mails, orders):
    """The ids of the orders each mail goes to, by mail id. A mail from
    before mails kept their orders goes by its point of sale: to the orders
    of that point, or to all without one."""
    kept = {}
    for mail_id, order_id in ReminderMessage.orders.through.objects.filter(
        remindermessage__in=[mail.pk for mail in mails]
    ).values_list("remindermessage_id", "customerorder_id"):
        kept.setdefault(mail_id, set()).add(order_id)
    return {
        mail.pk: kept.get(mail.pk)
        or {
            order.pk
            for order in orders
            if mail.point_of_sale_id in (None, order.point_of_sale_id)
        }
        for mail in mails
    }


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
    mail_orders = get_mail_orders(mails, orders)
    covered = set().union(*mail_orders.values()) if mail_orders else set()
    rows = {}
    for order in orders:
        row = rows.setdefault(
            order.point_of_sale_id,
            {
                "point_of_sale": order.point_of_sale,
                "orders": 0,
                "order_list": [],
                "emails": set(),
                "own_text": texts.get(order.point_of_sale_id)
                if order.point_of_sale_id
                else None,
            },
        )
        row["orders"] += 1
        row["order_list"].append(order)
        if order.customer:
            row["emails"].add(order.customer.user.email)
    for row in rows.values():
        ids = {order.pk for order in row["order_list"]}
        # The mails that reach an order of the point, and the orders no mail
        # reached: all of them before the first mail, the new ones after it.
        row["mails"] = [mail for mail in mails if mail_orders[mail.pk] & ids]
        row["open_orders"] = [
            order for order in row["order_list"] if order.pk not in covered
        ]
        row["open"] = len(row["open_orders"])
        row["state"] = get_mail_state(row["mails"])
        row["is_notified"] = not row["open"]
        row.update(get_mail_counts(row["mails"], row["emails"]))
        if row["mails"]:
            row["last_mail"] = row["mails"][-1]
    points = sorted(
        (row for key, row in rows.items() if key is not None),
        key=lambda row: row["point_of_sale"].name.lower(),
    )
    without = rows.get(None)
    pending = [mail for mail in mails if not mail.is_sent]
    open_orders = [order for order in orders if order.pk not in covered]
    if pending:
        state = "sending" if pending[-1].is_sending else "queued"
    elif not mails:
        state = "none"
    elif open_orders:
        state = "partly"
    else:
        state = "sent"
    sent = [mail for mail in mails if mail.is_sent]
    return {
        "state": state,
        "orders": len(orders),
        "points": points,
        "without_point": without,
        # The per point section is for days with more than one place to
        # pick up.
        "has_points": len(points) + bool(without) > 1,
        "order_list": orders,
        "notified": len(orders) - len(open_orders),
        "open_orders": open_orders,
        "remaining_orders": len(open_orders),
        # Named beside the button for all: their text isn't used by it.
        "own_texts": [
            row["point_of_sale"] for row in points if row["own_text"] and row["open"]
        ],
        "mails": mails,
        "pending": pending,
        "last_sent": sent[-1] if sent else None,
        **get_mail_counts(mails),
    }


def queue_mail(production_day, text, point_of_sale=None, orders=None):
    """A new mail from a text to orders, queued for the command that sends
    it. Without orders it goes to all orders of the point of sale, or of the
    day."""
    mail = ReminderMessage.objects.create(
        production_day=production_day,
        point_of_sale=point_of_sale,
        subject=text.subject,
        body=text.body,
        state=ReminderMessage.State.PLANNED_SENDING,
    )
    if orders is None:
        orders = production_day.customer_orders.all()
        if point_of_sale:
            orders = orders.filter(point_of_sale=point_of_sale)
    mail.orders.set(orders)
    return mail


def queue_reminders(overview, day_text, target):
    """Queues the mail for "all", "rest" or one point of sale (its id).

    "all" is one mail with the text of the day to every order of the day,
    "rest" one to the orders no mail went to yet. A point of sale gets its
    own text if it has one, to its orders no mail went to yet. Nobody left
    means no mail. Once a mail went out "all" is "rest", so a second click
    or a page left open never tells anybody twice.
    """
    production_day = day_text.production_day
    if target == "all" and overview["mails"]:
        target = "rest"
    if target == "all":
        text, point_of_sale, orders = day_text, None, overview["order_list"]
    elif target == "rest":
        text, point_of_sale, orders = day_text, None, overview["open_orders"]
    else:
        row = next(
            (
                row
                for row in overview["points"]
                if str(row["point_of_sale"].pk) == str(target)
            ),
            None,
        )
        if not row:
            return []
        text = row["own_text"] or day_text
        point_of_sale, orders = row["point_of_sale"], row["open_orders"]
    if not orders:
        return []
    return [queue_mail(production_day, text, point_of_sale, orders)]


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


def get_reminder_badge(production_day, order_ids):
    """The badge of the pickup emails tab: nothing while nothing is sent, a
    check when a mail went to every order, "12 / 14" when to some. Two small
    queries, order_ids are the orders of the day with their point of sale."""
    mails = list(
        ReminderMessage.objects.filter(
            production_day=production_day, state__in=MAIL_STATES
        ).only("point_of_sale_id")
    )
    if not mails:
        return None
    orders = [_Order(pk, point_of_sale) for pk, point_of_sale in order_ids]
    covered = set().union(*get_mail_orders(mails, orders).values())
    reached = sum(order.pk in covered for order in orders)
    if reached == len(orders):
        return "✓"
    return _("%(notified)s / %(points)s") % {
        "notified": reached,
        "points": len(orders),
    }


class _Order:
    """An order as get_mail_orders needs it."""

    def __init__(self, pk, point_of_sale_id):
        self.pk = pk
        self.point_of_sale_id = point_of_sale_id
