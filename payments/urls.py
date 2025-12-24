from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payments
    path('', views.payment_list, name='payment_list'),
    path('<uuid:payment_id>/', views.payment_detail, name='payment_detail'),
    
    # M-Pesa payments
    path('mpesa/initiate/<int:student_fee_id>/', views.initiate_mpesa_payment, name='initiate_mpesa_payment'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('mpesa/status/<uuid:payment_id>/', views.check_payment_status, name='check_payment_status'),
    
    # Other payment methods
    path('cash/<int:student_fee_id>/', views.record_cash_payment, name='record_cash_payment'),
    path('bank/<int:student_fee_id>/', views.record_bank_payment, name='record_bank_payment'),
    
    # Receipts
    path('receipts/', views.payment_receipt_list, name='receipt_list'),
    path('receipts/generate/<uuid:payment_id>/', views.generate_receipt, name='generate_receipt'),
    # Receipt numbers include slashes (e.g., RCPT/2025/0003), so use <path:...> to allow '/'
    path('receipts/<path:receipt_number>/', views.view_receipt, name='view_receipt'),
    
    # Fee summary
    path('fees/summary/', views.fee_summary, name='fee_summary'),
    path('fees/report/', views.fee_report, name='fee_report'),
    
    # Financial Reports
    path('reports/', views.financial_reports, name='financial_reports'),
    path('reports/collection/', views.payment_collection_report, name='payment_collection_report'),
    path('reports/outstanding/', views.outstanding_fees_report, name='outstanding_fees_report'),
    path('reports/summary/', views.collection_summary_report, name='collection_summary_report'),
    path('reports/methods/', views.payment_method_analysis, name='payment_method_analysis'),
    
    # Reminders
    path('reminders/', views.payment_reminder_list, name='reminder_list'),
    path('reminders/send/<int:student_fee_id>/', views.send_reminder, name='send_reminder'),
] 