"""
Template filters for Indian date formatting (dd-mm-yyyy)
"""
from django import template
from datetime import datetime

register = template.Library()


@register.filter
def indian_date(value):
    """
    Format date as dd-mm-yyyy (Indian format)
    
    Usage in template:
        {{ student.date_of_birth|indian_date }}
    """
    if value is None:
        return ""
    
    try:
        if isinstance(value, str):
            # Try to parse if it's a string
            value = datetime.strptime(value, '%Y-%m-%d').date()
        return value.strftime('%d-%m-%Y')
    except (ValueError, TypeError, AttributeError):
        return str(value)


@register.filter
def indian_datetime(value):
    """
    Format datetime as dd-mm-yyyy HH:MM (Indian format)
    """
    if value is None:
        return ""
    
    try:
        if isinstance(value, str):
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return value.strftime('%d-%m-%Y %H:%M')
    except (ValueError, TypeError, AttributeError):
        return str(value)

