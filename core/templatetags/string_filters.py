from django import template

register = template.Library()


@register.filter(name='replace_underscore')
def replace_underscore(value):
    """Replace underscores with spaces in a string"""
    if value:
        return str(value).replace('_', ' ')
    return value


@register.filter(name='humanize')
def humanize(value):
    """Convert snake_case to Title Case with spaces"""
    if value:
        return str(value).replace('_', ' ').title()
    return value


@register.filter(name='abs_filter')
def abs_filter(value):
    """Return absolute value of a number"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value

