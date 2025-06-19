from django.db import models
from django.contrib.auth.models import User
from core.models import School, Student, StudentFee
from django.core.validators import MinValueValidator
import uuid


class Payment(models.Model):
    """Model for payment records"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='payments')
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]
    
    payment_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.payment_id} - {self.student} - KES {self.amount}"

    class Meta:
        ordering = ['-payment_date']
        unique_together = ['school', 'payment_id']


class MpesaPayment(models.Model):
    """Model for M-Pesa specific payment details"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='mpesa_payments')
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='mpesa_details')
    phone_number = models.CharField(max_length=15)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.TextField(blank=True)
    mpesa_receipt_number = models.CharField(max_length=100, blank=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"M-Pesa Payment - {self.payment.payment_id}"

    class Meta:
        verbose_name = "M-Pesa Payment"
        verbose_name_plural = "M-Pesa Payments"
        unique_together = ['school', 'payment']


class PaymentReceipt(models.Model):
    """Model for payment receipts"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='payment_receipts')
    receipt_number = models.CharField(max_length=50)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='receipts')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField()
    payment_method = models.CharField(max_length=20)
    fee_category = models.CharField(max_length=100)
    term = models.CharField(max_length=100)
    academic_year = models.CharField(max_length=9)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.student}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            # Generate receipt number
            import datetime
            year = datetime.datetime.now().year
            count = PaymentReceipt.objects.filter(
                issued_at__year=year, school=self.school
            ).count() + 1
            self.receipt_number = f"RCPT/{year}/{count:04d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-issued_at']
        unique_together = ['school', 'receipt_number']


class PaymentReminder(models.Model):
    """Model for payment reminders"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='payment_reminders')
    REMINDER_TYPE_CHOICES = [
        ('due_date', 'Due Date Reminder'),
        ('overdue', 'Overdue Payment'),
        ('partial', 'Partial Payment'),
        ('receipt', 'Payment Receipt'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reminders')
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='reminders')
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE_CHOICES)
    message = models.TextField()
    sent_via_email = models.BooleanField(default=False)
    sent_via_sms = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.reminder_type} - {self.student} - {self.created_at.date()}"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['school', 'student', 'student_fee', 'reminder_type', 'created_at']
