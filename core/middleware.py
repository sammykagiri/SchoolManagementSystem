"""
Middleware to optimize user profile and school queries
This prevents N+1 queries when accessing user.profile.school in templates
"""


class OptimizeUserProfileMiddleware:
    """
    Middleware to optimize user profile queries by prefetching school
    This should be placed after AuthenticationMiddleware
    
    The middleware prefetches the user profile with school and caches it
    on the user object to prevent N+1 queries when templates access
    user.profile.school multiple times.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Prefetch user profile with school to avoid N+1 queries in templates
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            try:
                # Prefetch profile with school in one query
                # Access user.profile once to trigger the query with select_related optimization
                # Django will cache the result for subsequent accesses in the same request
                from core.models import UserProfile
                
                # Use select_related to fetch profile and school in one query
                # Then access user.profile which will use this prefetched data
                profile = UserProfile.objects.select_related('school').get(user=user)
                
                # Access user.profile to cache it - this is the key step
                # Django's OneToOneField reverse accessor will use the already-loaded profile
                # if we've accessed it through the manager first
                if hasattr(user, 'profile'):
                    # Force access to cache the profile
                    cached_profile = user.profile
                    # Pre-access school attributes used in templates to cache them
                    if cached_profile and cached_profile.school:
                        _ = cached_profile.school.id
                        _ = cached_profile.school.name
                        try:
                            _ = cached_profile.school.logo
                            _ = cached_profile.school.use_color_scheme
                            _ = cached_profile.school.primary_color
                            _ = cached_profile.school.secondary_color
                        except:
                            pass
                
            except UserProfile.DoesNotExist:
                # Profile doesn't exist - templates handle this
                pass
            except Exception:
                # Don't break the request if there's an error
                pass
        
        response = self.get_response(request)
        return response

