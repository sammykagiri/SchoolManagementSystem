"""
URL configuration for school_management project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.contrib.auth import views as auth_views
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('payments/', include('payments.urls')),
    path('communications/', include('communications.urls')),
    path('attendance/', include('attendance.urls')),
    path('timetable/', include('timetable.urls')),
    path('exams/', include('exams.urls')),
    path('homework/', include('homework.urls')),
    path('accounts/login/', core_views.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(template_name='auth/logout.html'), name='logout'),
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(template_name='auth/password_reset_form.html'), name='password_reset'),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='auth/password_reset_done.html'), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='auth/password_reset_confirm.html'), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='auth/password_reset_complete.html'), name='password_reset_complete'),
]

# Serve media files
if getattr(settings, 'USE_S3', False):
    # When using S3 (Railway storage), serve files through Django view
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', core_views.serve_media_file, name='serve_media'),
    ]
elif settings.DEBUG and getattr(settings, 'MEDIA_URL', None) and getattr(settings, 'MEDIA_ROOT', None):
    # In development with local storage, use Django's static file serving
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, 'MEDIA_ROOT', None):
    # In production with local storage, serve media files using a view
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
