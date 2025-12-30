"""
Role-based access control decorators
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def is_superadmin_user(user):
    """
    Check if a user is a superadmin (either Django superuser or has super_admin role)
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if hasattr(user, 'profile'):
        return user.profile.is_super_admin
    return False


def role_required(*allowed_roles):
    """
    Decorator to restrict view access to specific roles.
    
    Usage:
        @login_required
        @role_required('school_admin', 'teacher', 'accountant')
        def student_list(request):
            # Only admins, teachers, accountants can access
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access this page.')
                return redirect('login')
            
            # Superusers bypass role checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not hasattr(request.user, 'profile'):
                # Try to create a profile if it doesn't exist
                from core.models import UserProfile, School
                default_school = School.objects.first()
                UserProfile.objects.get_or_create(
                    user=request.user,
                    defaults={'school': default_school}
                )
                request.user.refresh_from_db()
                
                # If still no profile after creation attempt, redirect
                if not hasattr(request.user, 'profile'):
                    messages.error(request, 'User profile not found. Please contact administrator.')
                    return redirect('login')
            
            # Check if user has school assigned (except for superadmin accessing manage school views)
            # Check if this is a manage school view
            is_manage_school_view = (
                request.resolver_match and 
                request.resolver_match.url_name in ['school_admin_list', 'school_admin_edit', 'school_admin_delete', 'school_add']
            )
            
            # If user doesn't have a school assigned and is not superadmin accessing manage school views
            if not request.user.profile.school:
                if is_manage_school_view and is_superadmin_user(request.user):
                    # Superadmin can access manage school views even without school assignment
                    pass
                else:
                    # User without school assignment cannot access any menu/view
                    messages.error(request, 'You must be assigned to a school to access this page. Please contact administrator.')
                    return redirect('core:dashboard')
            
            # Check if user has any of the required roles
            user_roles = request.user.profile.roles_list
            # If no roles assigned, check old role field for backward compatibility
            if not user_roles and request.user.profile.role:
                user_roles = [request.user.profile.role]
            
            if any(role in user_roles for role in allowed_roles):
                return view_func(request, *args, **kwargs)
            
            # If user doesn't have any of the required roles
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('core:dashboard')
        
        return wrapper
    return decorator


def permission_required(permission_type, resource_type):
    """
    Decorator for views that checks whether a user has a specific permission,
    redirecting to the login page if necessary.
    
    Usage:
        @login_required
        @permission_required('add', 'student')
        def student_create(request):
            # Only users with add_student permission can access
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superusers have all permissions
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user has the required permission
            if not hasattr(request.user, 'profile'):
                # Try to create a profile if it doesn't exist
                from core.models import UserProfile, School
                default_school = School.objects.first()
                UserProfile.objects.get_or_create(
                    user=request.user,
                    defaults={'school': default_school}
                )
                request.user.refresh_from_db()
                
                # If still no profile after creation attempt, raise error
                if not hasattr(request.user, 'profile'):
                    raise PermissionDenied("User profile not found.")
            
            # Check if user has school assigned (except for superadmin accessing manage school views)
            is_manage_school_view = (
                request.resolver_match and 
                request.resolver_match.url_name in ['school_admin_list', 'school_admin_edit', 'school_admin_delete', 'school_add']
            )
            
            if not request.user.profile.school:
                if is_manage_school_view and is_superadmin_user(request.user):
                    # Superadmin can access manage school views even without school assignment
                    pass
                else:
                    # User without school assignment cannot access any menu/view
                    messages.error(request, 'You must be assigned to a school to access this page. Please contact administrator.')
                    raise PermissionDenied("You must be assigned to a school to access this page.")
            
            if request.user.profile.has_permission(permission_type, resource_type):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'You do not have permission to perform this action.')
                raise PermissionDenied("Insufficient permissions.")
                
        return _wrapped_view
    return decorator


def parent_or_admin_required(view_func):
    """
    Decorator to allow access to parents (for their own children) or admins.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        role = request.user.profile.role
        if role not in ['parent', 'school_admin', 'super_admin', 'teacher', 'accountant']:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

