from django import template
from django.contrib.auth.models import User

register = template.Library()


@register.filter(name='has_role')
def has_role(user, role_name):
    """Check if user has a specific role"""
    if not user or not user.is_authenticated:
        return False
    
    # Django superusers have all roles
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'profile'):
        return False
    
    # Check new roles system
    if user.profile.roles.filter(name=role_name).exists():
        return True
    
    # Fallback to old role field
    return user.profile.role == role_name if user.profile.role else False


@register.filter(name='has_any_role')
def has_any_role(user, role_names):
    """Check if user has any of the specified roles"""
    if not user or not user.is_authenticated:
        return False
    
    # Django superusers have all roles
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'profile'):
        return False
    
    # Split comma-separated role names
    if isinstance(role_names, str):
        role_list = [r.strip() for r in role_names.split(',')]
    else:
        role_list = list(role_names)
    
    # Check new roles system
    if user.profile.roles.filter(name__in=role_list).exists():
        return True
    
    # Fallback to old role field
    return user.profile.role in role_list if user.profile.role else False


@register.simple_tag
def is_super_admin(user):
    """Check if user is super admin"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_super_admin


@register.simple_tag
def is_school_admin(user):
    """Check if user is school admin"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_school_admin


@register.simple_tag
def is_teacher(user):
    """Check if user is teacher"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_teacher


@register.simple_tag
def is_accountant(user):
    """Check if user is accountant"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_accountant


@register.simple_tag
def is_parent(user):
    """Check if user is parent"""
    if not user or not user.is_authenticated:
        return False
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_parent


@register.simple_tag
def is_student(user):
    """Check if user is student"""
    if not user or not user.is_authenticated:
        return False
    if not hasattr(user, 'profile'):
        return False
    return user.profile.is_student


@register.simple_tag
def user_roles(user):
    """Get list of role names for a user"""
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return ['super_admin']
    if not hasattr(user, 'profile'):
        return []
    
    roles = list(user.profile.roles.values_list('name', flat=True))
    if not roles and user.profile.role:
        roles = [user.profile.role]
    return roles

