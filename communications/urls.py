from django.urls import path
from . import views

app_name = 'communications'

urlpatterns = [
    # Communication templates
    path('templates/', views.template_list, name='template_list'),
    #path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:template_id>/', views.template_detail, name='template_detail'),
    path('templates/<int:template_id>/update/', views.template_update, name='template_update'),
    path('templates/<int:template_id>/delete/', views.template_delete, name='template_delete'),
    
    # Email messages
    path('emails/', views.email_list, name='email_list'),
    path('emails/<int:email_id>/', views.email_detail, name='email_detail'),
    
    # SMS messages
    path('sms/', views.sms_list, name='sms_list'),
    path('sms/<int:sms_id>/', views.sms_detail, name='sms_detail'),
    
    # Communication logs
    path('logs/', views.communication_log_list, name='log_list'),
    path('logs/<int:log_id>/', views.communication_log_detail, name='log_detail'),
    
    # Send communications
    path('send/email/<int:student_id>/', views.send_email, name='send_email'),
    path('send/sms/<int:student_id>/', views.send_sms, name='send_sms'),
] 