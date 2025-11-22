"""
Template filters for Indian currency formatting
"""
from django import template

register = template.Library()


@register.filter
def indian_currency(value):
    """
    Format number as Indian Rupee (₹)
    
    Usage in template:
        {{ student_fee.amount_charged|indian_currency }}
    """
    if value is None:
        return "₹ 0.00"
    try:
        return f"₹ {float(value):,.2f}"
    except (ValueError, TypeError):
        return "₹ 0.00"


@register.filter
def currency(value):
    """Alias for indian_currency"""
    return indian_currency(value)

