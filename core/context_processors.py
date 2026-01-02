"""
Context processors for templates
"""


def user_profile_optimized(request):
    """
    Context processor to optimize user profile and school access in templates
    This prefetches the profile and school to avoid N+1 queries
    """
    context = {}
    
    if request.user.is_authenticated:
        from core.models import UserProfile
        try:
            # Prefetch profile with school in one query
            profile = UserProfile.objects.select_related('school').get(user=request.user)
            # Add optimized profile to context
            context['user_profile'] = profile
            context['user_school'] = profile.school if profile.school else None
        except UserProfile.DoesNotExist:
            context['user_profile'] = None
            context['user_school'] = None
    
    return context

