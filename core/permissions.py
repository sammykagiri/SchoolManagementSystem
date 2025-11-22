"""
Custom permission classes for role-based access control
"""
from rest_framework.permissions import BasePermission
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin


class HasResourcePermission(BasePermission):
    """
    Custom permission class that checks if the user has the required permission
    for the resource based on the viewset action.
    """
    def __init__(self, resource_type):
        self.resource_type = resource_type
        
    def has_permission(self, request, view):
        # Superusers always have permission
        if request.user.is_superuser:
            return True
            
        # Map viewset actions to permission types
        action_map = {
            'list': 'view',
            'retrieve': 'view',
            'create': 'add',
            'update': 'change',
            'partial_update': 'change',
            'destroy': 'delete'
        }
        
        # Get the required permission type based on the viewset action
        permission_type = action_map.get(view.action, 'view')
        
        # Check if the user has the required permission
        if hasattr(request.user, 'profile'):
            return request.user.profile.has_permission(permission_type, self.resource_type)
            
        return False


def HasResourcePermissionFactory(resource_type):
    """Factory function to create permission classes for specific resources"""
    class _Permission(HasResourcePermission):
        def __init__(self):
            super().__init__(resource_type)
    return _Permission


class CustomPermissionRequiredMixin(LoginRequiredMixin):
    """Mixin for class-based views that require custom permissions"""
    permission_type = None
    resource_type = None

    def has_custom_permission(self):
        if self.request.user.is_superuser:
            return True

        profile = getattr(self.request.user, 'profile', None)
        if profile and self.permission_type and self.resource_type:
            return profile.has_permission(self.permission_type, self.resource_type)
        return False

    def dispatch(self, request, *args, **kwargs):
        if not self.has_custom_permission():
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().dispatch(request, *args, **kwargs)
