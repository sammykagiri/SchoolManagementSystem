"""
Template filters for permission checking
"""
from django import template

register = template.Library()


@register.filter
def has_permission(user, permission_string):
    """
    Check if the user has a specific permission.
    
    The permission_string should be in the format: 'permission_type_resource_type'
    Examples: 'view_term', 'add_student', 'change_class', 'delete_grade'
    
    Usage in template:
        {% if user|has_permission:'view_term' %}
        {% if user|has_permission:'add_student' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    # Check if user has a profile
    if not hasattr(user, 'profile'):
        return False
    
    # Parse permission_string (format: 'permission_type_resource_type')
    # Split on underscore, last part is resource_type, rest is permission_type
    parts = permission_string.split('_')
    if len(parts) < 2:
        return False
    
    permission_type = parts[0]  # e.g., 'view', 'add', 'change', 'delete'
    resource_type = '_'.join(parts[1:])  # e.g., 'term', 'student', 'school_class'
    
    # Call the profile's has_permission method
    try:
        return user.profile.has_permission(permission_type, resource_type)
    except (AttributeError, TypeError):
        return False












