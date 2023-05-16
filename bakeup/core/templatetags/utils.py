import subprocess
from django.template.defaulttags import register


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
    tag = subprocess.check_output(["git", "describe", "--tags"]).strip().decode('utf-8')
    return tag


@register.simple_tag
def current_git_commit():
    commit_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode('utf-8')
    return commit_hash


@register.filter(name='hex_to_rgb')
def hex_to_rgb(hex, format_string='{r},{g},{b}'):
    # Returns the RGB value of a hexadecimal color
	hex = hex.replace('#','')
	out = {	'r':int(hex[0:2], 16),
		'g':int(hex[2:4], 16),
		'b':int(hex[4:6], 16)}
	return format_string.format(**out)