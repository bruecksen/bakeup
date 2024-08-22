from django import template
from django.contrib import messages
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from wagtail.models import Site
from wagtail.rich_text import RichText

from bakeup.newsletter.forms import SubscribeForm

from ..rich_text import rewrite_db_html_for_email

register = template.Library()


@register.inclusion_tag("newsletter/subscribe.html", takes_context=True)
def newsletter_subscribe_form(context, button_text="Subscribe"):
    """Renders the Subscribe form template tag.
    :param context: Data for the template
    :type context: dict
    :return: Data for the rendered template tag
    :rtype: dict
    """
    request = context.get("request")
    if request.method == "POST":  # POST method?
        form = SubscribeForm(
            request.POST
        )  # create a subscribe form and populate it with posted data
    else:  # GET or any other method?
        form = SubscribeForm()  # create a blank subscribe form

    return {
        "messages": messages.get_messages(request),
        "site": Site.find_for_request(request),
        "request": request,
        "subscribe_api_url": reverse("newsletter:subscribe_api"),
        "form": form,
        "errors": form.errors.as_json(),
        "NEWSLETTER_SUBSCRIBE_FORM_BUTTON_LABEL": button_text,
        "FORM_EXPIRED_ERROR": _("Form expired (try to refresh the page)"),
        "FORM_UNEXPECTED_ERROR": _("Internal Server Error (try again later)"),
    }


@register.filter
def newsletter_richtext(value):
    if not isinstance(value, RichText):
        if not isinstance(value, str):
            raise ValueError("Expected string value")
        value = RichText(value)

    return mark_safe(rewrite_db_html_for_email(value))  # noqa: S308


class MRMLError(Exception):
    pass


class MRMLRenderNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context) -> str:
        # Importing here because mrml is an optional dependency
        import mrml

        mjml_source = self.nodelist.render(context)
        try:
            return mrml.to_html(mjml_source)
        except OSError as error:
            # The MRML library raises OSError exceptions when something goes wrong.
            message = error.args[0]
            raise MRMLError(f"Failed to render MJML: {message!r}") from error


@register.tag(name="mrml")
def mrml_tag(parser, token) -> MRMLRenderNode:
    """
    Compile MJML template after rendering the contents as a django template.

    Usage:
        {% mrml %}
            .. MJML template code ..
        {% endmrml %}
    """
    nodelist = parser.parse(("endmrml",))
    parser.delete_first_token()
    tokens = token.split_contents()
    if len(tokens) != 1:
        raise template.TemplateSyntaxError(
            f"{tokens[0]!r} tag doesn't receive any arguments."
        )
    return MRMLRenderNode(nodelist)
