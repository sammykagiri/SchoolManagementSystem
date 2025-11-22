from django import template

register = template.Library()


@register.filter(name='has_permission')
def has_permission(user, permission_codename):
    """
    Check if user has a specific permission.
    Accepts format: 'permission_type_resource_type' (e.g., 'view_student', 'add_payment')
    or 'permission_type.resource_type' (e.g., 'view.student', 'add.payment')
    """
    if not user or not user.is_authenticated:
        return False
    
    # Django superusers have all permissions
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'profile'):
        return False
    
    # Parse permission codename
    if '.' in permission_codename:
        permission_type, resource_type = permission_codename.split('.', 1)
    elif '_' in permission_codename:
        # Try to split by underscore (format: permission_type_resource_type)
        parts = permission_codename.split('_', 1)
        if len(parts) == 2:
            permission_type, resource_type = parts
        else:
            # Fallback to Django's built-in permission system
            return user.has_perm(permission_codename)
    else:
        # Fallback to Django's built-in permission system
        return user.has_perm(permission_codename)
    
    # Check if user has permission through roles
    user_roles = user.profile.roles.all()
    for role in user_roles:
        if role.permissions.filter(
            permission_type=permission_type,
            resource_type=resource_type
        ).exists():
            return True
    
    # Check Django's built-in permission system
    codename = f"{permission_type}_{resource_type}"
    return user.has_perm(f"core.{codename}")


@register.filter(name='has_resource_permission')
def has_resource_permission(user, permission_string):
    """
    Check if user has permission for a resource.
    Format: 'permission_type.resource_type' (e.g., 'view.student', 'add.payment')
    """
    if not user or not user.is_authenticated:
        return False
    
    # Django superusers have all permissions
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'profile'):
        return False
    
    try:
        permission_type, resource_type = permission_string.split('.', 1)
    except ValueError:
        return False
    
    # Check if user has permission through roles
    user_roles = user.profile.roles.all()
    for role in user_roles:
        if role.permissions.filter(
            permission_type=permission_type,
            resource_type=resource_type
        ).exists():
            return True
    
    # Check Django's built-in permission system
    codename = f"{permission_type}_{resource_type}"
    return user.has_perm(f"core.{codename}")


@register.simple_tag
def can_view(user, resource_type):
    """Check if user can view a resource type"""
    return has_resource_permission(user, f"view.{resource_type}")


@register.simple_tag
def can_add(user, resource_type):
    """Check if user can add a resource type"""
    return has_resource_permission(user, f"add.{resource_type}")


@register.simple_tag
def can_change(user, resource_type):
    """Check if user can change a resource type"""
    return has_resource_permission(user, f"change.{resource_type}")


@register.simple_tag
def can_delete(user, resource_type):
    """Check if user can delete a resource type"""
    return has_resource_permission(user, f"delete.{resource_type}")


@register.simple_tag
def user_permissions(user):
    """Get list of permission strings for a user (format: 'permission_type.resource_type')"""
    if not user or not user.is_authenticated:
        return []
    
    if user.is_superuser:
        # Return all permissions (or a special marker)
        return ['*']
    
    if not hasattr(user, 'profile'):
        return []
    
    # Get permissions from roles
    user_roles = user.profile.roles.all()
    permissions = set()
    for role in user_roles:
        # Get permission_type and resource_type pairs
        perms = role.permissions.values_list('permission_type', 'resource_type')
        for perm_type, resource_type in perms:
            permissions.add(f"{perm_type}.{resource_type}")
    
    # Also include Django's built-in permissions
    django_perms = user.get_all_permissions()
    for perm in django_perms:
        # Extract codename from 'app.codename' format
        if '.' in perm:
            codename = perm.split('.', 1)[1]
            # Try to parse as permission_type_resource_type
            if '_' in codename:
                parts = codename.split('_', 1)
                if len(parts) == 2:
                    permissions.add(f"{parts[0]}.{parts[1]}")
            else:
                permissions.add(codename)
    
    return list(permissions)

