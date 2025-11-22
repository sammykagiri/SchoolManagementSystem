"""
Role-based access control decorators
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages


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
            
            if not hasattr(request.user, 'profile'):
                messages.error(request, 'User profile not found. Please contact administrator.')
                return redirect('login')
            
            user_role = request.user.profile.role
            if user_role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('core:dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
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

