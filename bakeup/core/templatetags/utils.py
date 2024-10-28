import subprocess
from urllib.parse import urljoin

from django import template
from django.template.defaultfilters import linebreaksbr
from django.template.defaulttags import register
from django.urls import reverse
from wagtail.models import Site


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def multiply(value, arg):
    return value * arg


@register.filter
def divide(value, arg):
    try:
        return int(value) / int(arg)
    except (ValueError, ZeroDivisionError):
        return None


@register.filter
def verbose_name(instance):
    return instance._meta.verbose_name


@register.simple_tag
def current_git_tag():
    tag = subprocess.check_output(["git", "describe", "--tags"]).strip().decode("utf-8")
    return tag


@register.simple_tag
def current_git_commit():
    commit_hash = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .strip()
        .decode("utf-8")
    )
    return commit_hash


@register.filter(name="hex_to_rgb")
def hex_to_rgb(hex, format_string="{r},{g},{b}"):
    # Returns the RGB value of a hexadecimal color
    if hex:
        hex = hex.replace("#", "")
        out = {"r": int(hex[0:2], 16), "g": int(hex[2:4], 16), "b": int(hex[4:6], 16)}
        return format_string.format(**out)


@register.simple_tag(takes_context=True)
def fullurl(context, url):
    """Converts relative URL to absolute.

    For example:

        {% fullurl article.get_absolute_url %}

    or:

        {% fullurl "/custom-url/" %}

    """
    site = Site.objects.get(is_default_site=True)
    root_url = site.root_url
    return urljoin(root_url, url)


@register.simple_tag(takes_context=True)
def reverse_fullurl(context, view_name, *args, **kwargs):
    """Converts relative URL to absolute.

    For example:

        {% reverse_fullurl article.get_absolute_url %}

    or:

        {% fullurl "/custom-url/" %}

    """
    site = Site.objects.get(is_default_site=True)
    root_url = site.root_url
    path = reverse(view_name, args=args, kwargs=kwargs)
    return urljoin(root_url, path)


@register.tag(name="linebreaksbr_block")
def do_linebreaksbr_block(parser, token):
    nodelist = parser.parse(("endlinebreaksbr_block",))
    parser.delete_first_token()
    return LineBreaksBRNode(nodelist)


class LineBreaksBRNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        content = self.nodelist.render(context)
        return linebreaksbr(content)
