from django import template

register = template.Library()


@register.filter
def replace(value, args):
    """
    Simple replace filter: {{ value|replace:"old|new" }}
    If args doesn't contain '|', returns original value.
    """
    if value is None:
        return value
    if not args or '|' not in args:
        return value
    old, new = args.split('|', 1)
    return str(value).replace(old, new)


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary is None:
        return None
    return dictionary.get(key)





