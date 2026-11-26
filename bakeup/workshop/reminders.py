"""The pickup emails of a production day: the emails written for it, who
they go to and which orders were told already.

Every ReminderMessage of a day is one email:

- A draft (PLANNED) keeps its text and who it is for, not its orders: the
  points of sale chosen in the editor, whether the orders without a point of
  sale are in, and whether only the orders no email went to yet get it. No
  choice is every order of the day. The orders are looked up when the email
  is queued, so a draft written in the morning also reaches the orders that
  came in later.
- Queued (PLANNED_SENDING), being sent (SENDING) or sent (SENT), it keeps
  the orders it goes to in ReminderMessage.orders, set when it was queued.
  The management command send_reminder_emails sends the queued ones. A
  queued email can be taken back to a draft until the command takes it, see
  ReminderMessage.claim_for_sending.

An order is notified once a queued, sending or sent email has it. Emails
from before the orders were kept go by their point of sale, see
get_mail_orders.
"""

from django.template import Context, Template, TemplateSyntaxError
from django.utils import timezone
from django.utils.translation import gettext as _

from bakeup.pages.models import EmailSettings
from bakeup.workshop.models import ReminderMessage

MAIL_STATES = (
    ReminderMessage.State.PLANNED_SENDING,
    ReminderMessage.State.SENDING,
    ReminderMessage.State.SENT,
)

# The key of the orders without a point of sale, among the pks of the points
# in the recipients of the editor and the chips of the status line.
WITHOUT_POINT = "none"


def get_default_text(request, production_day):
    """A new email: the text from the email settings."""
    email_settings = EmailSettings.load(request_or_site=request)
    return ReminderMessage(
        production_day=production_day,
        subject=email_settings.get_subject_with_prefix(
            email_settings.production_day_reminder_subject
        ),
        body=email_settings.production_day_reminder_body,
    )


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


def get_day_orders(production_day):
    return list(
        production_day.customer_orders.select_related(
            "customer__user", "point_of_sale"
        ).order_by("point_of_sale__name", "pk")
    )


def get_notified(production_day, orders, exclude=None):
    """The ids of the orders a queued, sending or sent email has."""
    mails = ReminderMessage.objects.filter(
        production_day=production_day, state__in=MAIL_STATES
    )
    if exclude is not None and exclude.pk:
        mails = mails.exclude(pk=exclude.pk)
    mails = list(mails.only("pk", "point_of_sale_id"))
    return set().union(*get_mail_orders(mails, orders).values()) if mails else set()


def get_point_key(order):
    return str(order.point_of_sale_id) if order.point_of_sale_id else WITHOUT_POINT


def resolve_recipients(selection, only_unnotified, orders, notified):
    """The orders an email goes to: those of the chosen points (keys as in
    get_point_key), all with no choice, without the notified ones if only
    those are wanted."""
    selection = set(selection)
    return [
        order
        for order in orders
        if (not selection or get_point_key(order) in selection)
        and not (only_unnotified and order.pk in notified)
    ]


def get_selection(mail):
    """The keys of the points a stored email is for, empty for all."""
    if not mail.pk:
        return set()
    keys = {str(point.pk) for point in mail.points_of_sale.all()}
    if mail.without_point_of_sale:
        keys.add(WITHOUT_POINT)
    if not keys and mail.point_of_sale_id:
        keys.add(str(mail.point_of_sale_id))
    return keys


def store_selection(mail, selection, only_unnotified):
    """Keeps who a saved email is for, see get_selection."""
    selection = set(selection)
    mail.without_point_of_sale = WITHOUT_POINT in selection
    mail.only_unnotified = only_unnotified
    mail.save(update_fields=["without_point_of_sale", "only_unnotified"])
    mail.points_of_sale.set([int(key) for key in selection if key.isdigit()])


def get_mail_recipients(mail, orders, notified):
    """The orders of an email: kept since it was queued, or those it would
    go to if it was queued now."""
    if mail.is_planned:
        return resolve_recipients(
            get_selection(mail), mail.only_unnotified, orders, notified
        )
    ids = {order.pk for order in mail.get_orders()}
    return [order for order in orders if order.pk in ids]


def queue_mail(mail, orders):
    """Queues a draft for the command that sends it, with the orders it goes
    to from now on."""
    mail.state = ReminderMessage.State.PLANNED_SENDING
    mail.save(update_fields=["state"])
    mail.orders.set(orders)
    return mail


def take_back_mail(mail):
    """A queued email back to a draft, False once the command took it."""
    taken = ReminderMessage.objects.filter(
        pk=mail.pk, state=ReminderMessage.State.PLANNED_SENDING
    ).update(state=ReminderMessage.State.PLANNED)
    if taken:
        mail.orders.clear()
    return bool(taken)


def duplicate_mail(mail):
    """A new draft with the text and who it is for of an email."""
    copy = ReminderMessage.objects.create(
        production_day=mail.production_day,
        subject=mail.subject,
        body=mail.body,
        state=ReminderMessage.State.PLANNED,
    )
    store_selection(copy, get_selection(mail), mail.only_unnotified)
    return copy


def get_points(orders, notified, keys=()):
    """The points of sale of the orders of the day, in the order of their
    names, the orders without one last: one dict per point with its orders
    and how many no email went to yet. keys adds the points a draft was
    written for that have no orders any more."""
    points = {}
    for order in orders:
        key = get_point_key(order)
        point = points.setdefault(
            key,
            {
                "key": key,
                "point_of_sale": order.point_of_sale,
                "name": order.point_of_sale.name
                if order.point_of_sale
                else _("Without point of sale"),
                "short_name": order.point_of_sale.get_short_name()
                if order.point_of_sale
                else _("Without point of sale"),
                "orders": 0,
                "open": 0,
            },
        )
        point["orders"] += 1
        point["open"] += order.pk not in notified
    missing = [key for key in keys if key not in points]
    if missing:
        from bakeup.shop.models import PointOfSale

        for point_of_sale in PointOfSale.objects.filter(
            pk__in=[key for key in missing if key.isdigit()]
        ):
            points[str(point_of_sale.pk)] = {
                "key": str(point_of_sale.pk),
                "point_of_sale": point_of_sale,
                "name": point_of_sale.name,
                "short_name": point_of_sale.get_short_name(),
                "orders": 0,
                "open": 0,
            }
        if WITHOUT_POINT in missing:
            points[WITHOUT_POINT] = {
                "key": WITHOUT_POINT,
                "point_of_sale": None,
                "name": _("Without point of sale"),
                "short_name": _("Without point of sale"),
                "orders": 0,
                "open": 0,
            }
    return sorted(
        points.values(),
        key=lambda point: (point["key"] == WITHOUT_POINT, point["name"].lower()),
    )


def get_recipients_label(mail, points):
    """Who an email is for, in short: "All", or the short names of its
    points of sale."""
    selection = get_selection(mail)
    if not selection:
        return _("All")
    names = {point["key"]: point["short_name"] for point in points}
    for point_of_sale in mail.points_of_sale.all():
        names.setdefault(str(point_of_sale.pk), point_of_sale.get_short_name())
    if mail.point_of_sale_id:
        names.setdefault(
            str(mail.point_of_sale_id), mail.point_of_sale.get_short_name()
        )
    names.setdefault(WITHOUT_POINT, _("Without point of sale"))
    return ", ".join(
        sorted(
            (names[key] for key in selection),
            key=lambda name: (name == _("Without point of sale"), name.lower()),
        )
    )


def render_subject(mail, client):
    """The subject as the list shows it: the shop name and day filled in."""
    context = Context(
        {
            "site_name": client.name,
            "production_day": mail.production_day.day_of_sale.strftime("%d.%m.%Y"),
        }
    )
    try:
        return Template(mail.subject).render(context)
    except TemplateSyntaxError:
        return mail.subject


def format_time(mail):
    """The time alone on the day it went out, with the date later on."""
    when = timezone.localtime(mail.sent_date or mail.updated or mail.created)
    return when.strftime(
        "%H:%M" if when.date() == timezone.localdate() else "%d.%m. %H:%M"
    )


def get_reminder_overview(production_day, client):
    """The pickup emails of the day: how many orders were notified, per
    point of sale, and every email of the day, the drafts first, then the
    newest first."""
    orders = get_day_orders(production_day)
    mails = list(
        ReminderMessage.objects.filter(production_day=production_day)
        .select_related("point_of_sale", "production_day")
        .prefetch_related("points_of_sale")
    )
    sent_mails = [mail for mail in mails if not mail.is_planned]
    mail_orders = get_mail_orders(sent_mails, orders)
    notified = set().union(*mail_orders.values()) if mail_orders else set()
    points = get_points(orders, notified)
    by_pk = {order.pk: order for order in orders}
    for mail in mails:
        if mail.is_planned:
            mail.recipients = resolve_recipients(
                get_selection(mail), mail.only_unnotified, orders, notified
            )
        else:
            mail.recipients = [by_pk[pk] for pk in mail_orders[mail.pk] if pk in by_pk]
        mail.recipients_label = get_recipients_label(mail, points)
        mail.display_subject = render_subject(mail, client)
        mail.display_time = format_time(mail)
        mail.delivered = len(mail.send_log or [])
        mail.failed = len(mail.error_log or {})
    mails.sort(
        key=lambda mail: (
            not mail.is_planned,
            -(mail.sent_date or mail.updated or mail.created).timestamp(),
            -mail.pk,
        )
    )
    return {
        "orders": len(orders),
        "order_list": orders,
        "notified_ids": notified,
        "notified": sum(order.pk in notified for order in orders),
        "points": points,
        "mails": mails,
        "has_sent": bool(sent_mails),
    }


def get_preview_order(orders):
    """The first order with a customer to fill in the placeholders, or None."""
    return next((order for order in orders if order.customer_id), None)


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
