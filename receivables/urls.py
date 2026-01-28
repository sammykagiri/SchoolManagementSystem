from django.urls import path
from . import views

app_name = 'receivables'

urlpatterns = [
    # Receivables - main page for the receivables app
    path('', views.receivable_list, name='receivable_list'),
    path('api/receivables/search/', views.api_receivable_search, name='api_receivable_search'),
    
    # Payments
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/delete/<str:payment_id>/', views.payment_delete, name='payment_delete'),
    
    # M-Pesa payments
    path('mpesa/initiate/<int:student_fee_id>/', views.initiate_mpesa_payment, name='initiate_mpesa_payment'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('mpesa/status/<str:payment_id>/', views.check_payment_status, name='check_payment_status'),
    
    # Other payment methods
    path('cash/<int:student_fee_id>/', views.record_cash_payment, name='record_cash_payment'),
    path('bank/<int:student_fee_id>/', views.record_bank_payment, name='record_bank_payment'),
    
    # Receipts
    path('receipts/', views.payment_receipt_list, name='receipt_list'),
    path('receipts/generate/<str:payment_id>/', views.generate_receipt, name='generate_receipt'),
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
    
    # Credits
    path('credits/', views.credit_list, name='credit_list'),
    path('credits/create/', views.credit_create, name='credit_create'),
    path('credits/apply-all/', views.credit_apply_all, name='credit_apply_all'),
    path('credits/<str:credit_id>/edit/', views.credit_edit, name='credit_edit'),
    path('credits/<str:credit_id>/apply/', views.credit_apply, name='credit_apply'),
    path('credits/<str:credit_id>/delete/', views.credit_delete, name='credit_delete'),
    
    # Bank Statement Patterns
    path('bank-statements/patterns/', views.bank_statement_pattern_list, name='bank_statement_pattern_list'),
    path('bank-statements/patterns/create/', views.bank_statement_pattern_create, name='bank_statement_pattern_create'),
    path('bank-statements/patterns/<str:pattern_id>/edit/', views.bank_statement_pattern_edit, name='bank_statement_pattern_edit'),
    path('bank-statements/patterns/<str:pattern_id>/delete/', views.bank_statement_pattern_delete, name='bank_statement_pattern_delete'),
    
    # Bank Statement Upload
    path('bank-statements/upload/', views.bank_statement_upload, name='bank_statement_upload'),
    
    # Unmatched Transactions
    path('unmatched-transactions/', views.unmatched_transaction_list, name='unmatched_transaction_list'),
    path('unmatched-transactions/<str:transaction_id>/', views.unmatched_transaction_detail, name='unmatched_transaction_detail'),
    path('unmatched-transactions/<str:transaction_id>/match/', views.unmatched_transaction_match, name='unmatched_transaction_match'),
    path('unmatched-transactions/<str:transaction_id>/ignore/', views.unmatched_transaction_ignore, name='unmatched_transaction_ignore'),
    path('unmatched-transactions/<str:transaction_id>/delete/', views.unmatched_transaction_delete, name='unmatched_transaction_delete'),
    
    # API endpoints for receivables
    path('api/receivables/<str:receivable_id>/allocations/', views.api_receivable_allocations, name='api_receivable_allocations'),
    
    # Detail views - must come last as they're catch-alls for tokens
    # Receivable detail comes first - it will check if token is a payment and redirect if needed
    path('<str:receivable_id>/', views.receivable_detail, name='receivable_detail'),
    path('<str:payment_id>/', views.payment_detail, name='payment_detail'),
] 