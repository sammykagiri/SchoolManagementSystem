from django.contrib import admin
from .models import Payment, MpesaPayment, PaymentReceipt, PaymentReminder


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'student', 'payment_method', 'amount', 'status', 'payment_date']
    list_filter = ['payment_method', 'status', 'payment_date']
    search_fields = ['payment_id', 'student__student_id', 'student__first_name', 'student__last_name', 'reference_number']
    ordering = ['-payment_date']
    readonly_fields = ['payment_id', 'created_at', 'updated_at']
    fieldsets = (
        ('Payment Information', {
            'fields': ('payment_id', 'student', 'student_fee', 'amount', 'payment_method', 'status')
        }),
        ('Reference Information', {
            'fields': ('reference_number', 'transaction_id', 'processed_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('payment_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ['payment', 'phone_number', 'result_code', 'mpesa_receipt_number', 'transaction_date']
    list_filter = ['result_code', 'transaction_date']
    search_fields = ['payment__payment_id', 'phone_number', 'mpesa_receipt_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'student', 'amount_paid', 'payment_method', 'issued_at']
    list_filter = ['payment_method', 'issued_at']
    search_fields = ['receipt_number', 'student__student_id', 'student__first_name', 'student__last_name']
    ordering = ['-issued_at']
    readonly_fields = ['receipt_number', 'issued_at']


@admin.register(PaymentReminder)
class PaymentReminderAdmin(admin.ModelAdmin):
    list_display = ['student', 'reminder_type', 'sent_via_email', 'sent_via_sms', 'created_at']
    list_filter = ['reminder_type', 'sent_via_email', 'sent_via_sms', 'created_at']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
