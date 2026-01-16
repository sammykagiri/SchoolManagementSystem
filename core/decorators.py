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
            
            # Special handling for 'parent' role: check if user has a Parent profile
            # This must be checked BEFORE the school assignment check, as parents use Parent.school, not Profile.school
            # Check if this is a parent portal view
            is_parent_portal_view = (
                request.resolver_match and 
                'parent_portal' in request.resolver_match.url_name
            )
            
            if 'parent' in allowed_roles:
                # Check if user has a parent profile - use get() to avoid DoesNotExist exceptions
                from core.models import Parent
                try:
                    # Try to get parent profile directly from database (no refresh needed, just direct query)
                    parent = Parent.objects.select_related('school', 'user').get(user=request.user)
                    if parent and parent.school:
                        # User has a valid parent profile with school, allow access immediately
                        # Skip ALL other checks for parents accessing parent portal
                        # This prevents any error messages from being set
                        return view_func(request, *args, **kwargs)
                    elif parent:
                        # Parent profile exists but no school assigned
                        messages.error(request, 'Your parent account is not assigned to a school. Please contact administrator.')
                        return redirect('login')
                    else:
                        # Parent object exists but is None (shouldn't happen, but handle it)
                        if is_parent_portal_view:
                            messages.error(request, 'Parent profile not found. Please contact administrator.')
                            return redirect('login')
                        pass
                except Parent.DoesNotExist:
                    # No parent profile found
                    if is_parent_portal_view:
                        messages.error(request, 'Parent profile not found. Please contact administrator.')
                        return redirect('login')
                    # For non-parent-portal views, continue with normal role check
                    pass
                except Exception as e:
                    # Parent profile exists but might be invalid
                    # Log the exception for debugging
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f'Parent profile check failed for user {request.user.username}: {str(e)}', exc_info=True)
                    # If this is a parent portal view, redirect with error
                    if is_parent_portal_view:
                        messages.error(request, 'Parent profile not found or invalid. Please contact administrator.')
                        return redirect('login')
                    # For non-parent-portal views, continue with normal role check
                    pass
            
            # Check if user has school assigned (except for superadmin accessing manage school views, and parents)
            # Check if this is a manage school view
            is_manage_school_view = (
                request.resolver_match and 
                request.resolver_match.url_name in ['school_admin_list', 'school_admin_edit', 'school_admin_delete', 'school_add']
            )
            
            # If user doesn't have a school assigned and is not superadmin accessing manage school views, and not a parent accessing parent portal
            if not request.user.profile.school:
                if is_manage_school_view and is_superadmin_user(request.user):
                    # Superadmin can access manage school views even without school assignment
                    pass
                elif is_parent_portal_view:
                    # Parent accessing parent portal - they use Parent.school, not Profile.school
                    # Check if parent has a school using direct database query (not hasattr which can be unreliable)
                    from core.models import Parent
                    try:
                        parent = Parent.objects.select_related('school').get(user=request.user)
                        if not parent or not parent.school:
                            messages.error(request, 'Your parent account is not assigned to a school. Please contact administrator.')
                            return redirect('login')
                        # Parent has school, allow them to continue (they should have been caught by early check, but just in case)
                        # Don't set error message, just continue
                        pass
                    except Parent.DoesNotExist:
                        # No parent profile found - this should have been caught by early check
                        # But if we reach here, it means the early check didn't work
                        # Don't set error message yet, let the role check handle it
                        pass
                    except Exception:
                        # Parent profile check failed - don't set error message yet
                        pass
                else:
                    # User without school assignment cannot access any menu/view
                    # BUT: Check if they're a parent first (shouldn't reach here for parent portal, but safety check)
                    from core.models import Parent
                    try:
                        parent = Parent.objects.select_related('school').get(user=request.user)
                        if parent and parent.school:
                            # User is a parent with school trying to access non-parent page (e.g., dashboard)
                            # Redirect them to parent portal WITHOUT error message
                            return redirect('core:parent_portal_dashboard')
                        else:
                            # Parent without school
                            messages.error(request, 'Your parent account is not assigned to a school. Please contact administrator.')
                            return redirect('login')
                    except (Parent.DoesNotExist, Exception):
                        # Not a parent, show error
                        messages.error(request, 'You must be assigned to a school to access this page. Please contact administrator.')
                        return redirect('core:dashboard')
            
            # Check if user has any of the required roles
            user_roles = request.user.profile.roles_list
            # If no roles assigned, check old role field for backward compatibility
            if not user_roles and request.user.profile.role:
                user_roles = [request.user.profile.role]
            
            # If 'parent' is in allowed_roles, check again using direct database query
            # (This is a fallback in case the early check didn't work for some reason)
            # Parents might not have 'parent' in their UserProfile.roles_list
            if 'parent' in allowed_roles:
                from core.models import Parent
                try:
                    parent = Parent.objects.select_related('school').get(user=request.user)
                    if parent and parent.school:
                        # User has a valid parent profile, allow access
                        return view_func(request, *args, **kwargs)
                except Parent.DoesNotExist:
                    # No parent profile, continue with normal role check
                    pass
                except Exception:
                    # Parent profile check failed, continue with normal role check
                    pass
            
            if any(role in user_roles for role in allowed_roles):
                return view_func(request, *args, **kwargs)
            
            # If user doesn't have any of the required roles
            # BUT: Before setting error message, check one more time if user is a parent
            # (This is a final safety check in case all previous checks missed it)
            if 'parent' in allowed_roles:
                from core.models import Parent
                try:
                    parent = Parent.objects.select_related('school').get(user=request.user)
                    if parent and parent.school:
                        # User has a valid parent profile, allow access (shouldn't reach here, but safety check)
                        return view_func(request, *args, **kwargs)
                except (Parent.DoesNotExist, Exception):
                    # Parent check failed, continue to error message
                    pass
            
            # Determine where to redirect based on user's actual role to avoid redirect loops
            # Check if user is a parent BEFORE setting error message
            # This is important because parents might be redirected to dashboard after login,
            # and we don't want to show them an error message
            from core.models import Parent
            is_parent = False
            try:
                parent = Parent.objects.select_related('school').get(user=request.user)
                if parent and parent.school:
                    is_parent = True
            except (Parent.DoesNotExist, Exception):
                # Check if parent role is in user_roles as fallback
                is_parent = 'parent' in user_roles or (hasattr(request.user.profile, 'is_parent') and request.user.profile.is_parent)
            
            if is_parent and 'parent' in allowed_roles:
                # User is a parent trying to access parent portal - allow access (shouldn't reach here)
                return view_func(request, *args, **kwargs)
            elif is_parent:
                # Parent trying to access non-parent page (e.g., dashboard) - redirect to parent portal
                # WITHOUT error message (parents shouldn't see error when redirected from dashboard)
                return redirect('core:parent_portal_dashboard')
            
            # Only set error message if user is definitely not a parent or doesn't have required roles
            messages.error(request, 'You do not have permission to access this page.')
            
            # Check if user has any valid role that would allow dashboard access
            dashboard_roles = ['super_admin', 'school_admin', 'teacher', 'accountant']
            if any(role in user_roles for role in dashboard_roles):
                return redirect('core:dashboard')
            
            # If user has no valid roles or we're already being redirected from dashboard,
            # redirect to login to avoid infinite loop
            # Check if we're already trying to access dashboard to break the loop
            if request.resolver_match and request.resolver_match.url_name == 'dashboard':
                messages.error(request, 'Your account does not have the necessary permissions. Please contact administrator.')
                return redirect('login')
            
            # Default: try dashboard, but this should be caught by the check above
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
                
                # If still no profile after creation attempt, redirect with error
                if not hasattr(request.user, 'profile'):
                    messages.error(request, 'User profile not found. Please contact administrator.')
                    return redirect('core:home')
            
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
                    return redirect('core:home')
            
            if request.user.profile.has_permission(permission_type, resource_type):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'You do not have permission to perform this action.')
                # Redirect to home page instead of raising PermissionDenied for better UX
                return redirect('core:home')
                
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

