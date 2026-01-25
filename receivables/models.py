from django.db import models
from django.contrib.auth.models import User
from core.models import School, Student, StudentFee
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import uuid
import re


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
    
    def get_signed_token(self):
        """Generate an opaque signed token for this payment to use in URLs."""
        from django.core import signing
        payload = {'payid': str(self.payment_id)}
        return signing.dumps(payload)
    
    @classmethod
    def from_signed_token(cls, token):
        """Resolve a signed token back to a Payment object."""
        from django.core import signing
        from django.core.signing import BadSignature
        try:
            data = signing.loads(token)
            payment_id = data.get('payid')
            if not payment_id:
                return None
            return cls.objects.get(payment_id=payment_id)
        except (BadSignature, ValueError, cls.DoesNotExist, TypeError):
            return None

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


class PaymentAllocation(models.Model):
    """Model to track how payments are allocated to student fees"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='payment_allocations')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='allocations')
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payment_allocations')
    amount_allocated = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Allocation: {self.payment.payment_id} -> {self.student_fee} - KES {self.amount_allocated}"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['school', 'payment', 'student_fee']


class Receivable(models.Model):
    """Model to track outstanding receivables (fees owed by students)"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='receivables')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='receivables')
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='receivables')
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    due_date = models.DateField()
    is_cleared = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def balance(self):
        """Calculate outstanding balance"""
        return self.amount_due - self.amount_paid
    
    @property
    def is_overdue(self):
        """Check if receivable is overdue"""
        from django.utils import timezone
        return not self.is_cleared and timezone.now().date() > self.due_date
    
    def __str__(self):
        return f"Receivable: {self.student} - {self.student_fee.fee_category.name} - KES {self.balance}"
    
    def get_signed_token(self):
        """Generate an opaque signed token for this receivable to use in URLs."""
        from django.core import signing
        payload = {'recid': self.id}
        return signing.dumps(payload)
    
    @classmethod
    def from_signed_token(cls, token):
        """Resolve a signed token back to a Receivable object."""
        from django.core import signing
        from django.core.signing import BadSignature
        try:
            data = signing.loads(token)
            rec_id = data.get('recid')
            if not rec_id:
                return None
            return cls.objects.get(id=rec_id)
        except (BadSignature, ValueError, cls.DoesNotExist, TypeError):
            return None
    
    class Meta:
        ordering = ['due_date', 'student']
        unique_together = ['school', 'student_fee']


class Credit(models.Model):
    """Model to track credit balances for students"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='credits')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='credits')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    source = models.CharField(
        max_length=50,
        choices=[
            ('overpayment', 'Overpayment'),
            ('refund', 'Refund'),
            ('adjustment', 'Adjustment'),
            ('reassignment', 'Payment Reassignment'),
            ('other', 'Other'),
        ],
        default='overpayment'
    )
    description = models.TextField(blank=True)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='credits',
        help_text='Payment that created this credit (if applicable)'
    )
    is_applied = models.BooleanField(default=False, help_text='Whether this credit has been applied to fees')
    applied_to_fee = models.ForeignKey(
        StudentFee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_credits',
        help_text='Fee this credit was applied to (if applicable)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Credit: {self.student} - KES {self.amount} ({self.get_source_display()})"
    
    def get_signed_token(self):
        """Generate an opaque signed token for this credit to use in URLs."""
        from django.core import signing
        payload = {'crid': self.id}
        return signing.dumps(payload)
    
    @classmethod
    def from_signed_token(cls, token):
        """Resolve a signed token back to a Credit object."""
        from django.core import signing
        from django.core.signing import BadSignature
        try:
            data = signing.loads(token)
            cr_id = data.get('crid')
            if not cr_id:
                return None
            return cls.objects.get(id=cr_id)
        except (BadSignature, ValueError, cls.DoesNotExist, TypeError):
            return None
    
    class Meta:
        ordering = ['-created_at']


class BankStatementPattern(models.Model):
    """Model to define patterns for parsing bank statements per bank and school"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='bank_statement_patterns')
    bank_name = models.CharField(max_length=100, help_text='Name of the bank (e.g., Equity Bank, KCB, etc.)')
    pattern_name = models.CharField(max_length=100, help_text='Descriptive name for this pattern')
    
    # CSV column mapping
    date_column = models.CharField(
        max_length=50,
        help_text='Column name or index for transaction date (e.g., "Date", "Transaction Date", "0")'
    )
    amount_column = models.CharField(
        max_length=50,
        help_text='Column name or index for amount (e.g., "Amount", "Debit", "Credit", "1")'
    )
    reference_column = models.CharField(
        max_length=50,
        help_text='Column name or index for narrative/reference containing M-Pesa details (e.g., "Narrative", "Description", "2")'
    )
    transaction_reference_column = models.CharField(
        max_length=50,
        blank=True,
        help_text='Column name or index for unique bank transaction reference number (e.g., "Transaction Ref", "Reference", "3") - used for duplicate detection'
    )
    student_id_pattern = models.CharField(
        max_length=200,
        blank=True,
        help_text='Regex pattern to extract student ID from reference (e.g., r"STUDENT\\s*(\\d+)" or r"(\\d{5})" or r"#(\\d+)" for M-Pesa format BUSINESS#STUDENT_ID)'
    )
    amount_pattern = models.CharField(
        max_length=200,
        blank=True,
        help_text='Regex pattern to extract amount if needed (optional)'
    )
    
    # Date format
    date_format = models.CharField(
        max_length=50,
        default='%Y-%m-%d',
        help_text='Date format in Python strftime format (e.g., "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y")'
    )
    
    # CSV settings
    has_header = models.BooleanField(default=True, help_text='Whether CSV file has header row')
    delimiter = models.CharField(max_length=5, default=',', help_text='CSV delimiter (comma, semicolon, tab)')
    encoding = models.CharField(max_length=20, default='utf-8', help_text='File encoding (utf-8, latin-1, etc.)')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.bank_name} - {self.pattern_name} ({self.school.name})"
    
    def extract_student_id(self, reference_text):
        """
        Extract student ID from reference text using the pattern.
        Also supports default M-Pesa format: BUSINESS_NUMBER#STUDENT_ID
        
        Examples:
        - "123456#00001" -> "00001" (M-Pesa format)
        - "STUDENT 00001" with pattern r"STUDENT\\s*(\\d+)" -> "00001"
        - "MPS 254721266013 TK18K8USG7 064010#00001 SAMUEL KAGIRI" -> "00001"
        """
        if not reference_text:
            return None
        
        # Try custom pattern first
        if self.student_id_pattern:
            match = re.search(self.student_id_pattern, reference_text, re.IGNORECASE)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        # Try default M-Pesa pattern: BUSINESS_NUMBER#STUDENT_ID
        # Format: BUSINESS_NUMBER#STUDENT_ID (e.g., "123456#00001" or "064010#00001")
        mpesa_match = re.search(r'#(\d+)', reference_text)
        if mpesa_match:
            return mpesa_match.group(1)
        
        return None
    
    def extract_mpesa_details(self, narrative_text):
        """
        Extract M-Pesa details from narrative text.
        Format: "MPS [Mobile] [M-Pesa Ref] [Business#StudentID] [Name]"
        Example: "MPS 254721266013 TK18K8USG7 064010#00001 SAMUEL KAGIRI"
        
        Returns:
            dict with keys: mobile_number, mpesa_reference, business_number, student_id, name
        """
        if not narrative_text:
            return {}
        
        details = {}
        
        # Pattern: MPS [Mobile] [M-Pesa Ref] [Business#StudentID] [Name]
        # M-Pesa reference is typically alphanumeric, 10-12 chars (e.g., TK18K8USG7)
        # Mobile number is typically 12 digits starting with 254
        # Business#StudentID format: digits#digits
        
        # Extract M-Pesa reference (alphanumeric, typically after mobile number)
        mpesa_ref_match = re.search(r'\b([A-Z0-9]{8,12})\b', narrative_text)
        if mpesa_ref_match:
            # Check if it looks like an M-Pesa reference (starts with letters, has numbers)
            ref = mpesa_ref_match.group(1)
            if re.match(r'^[A-Z]{2,}[A-Z0-9]+$', ref):
                details['mpesa_reference'] = ref
        
        # Extract mobile number (12 digits starting with 254)
        mobile_match = re.search(r'\b(254\d{9})\b', narrative_text)
        if mobile_match:
            details['mobile_number'] = mobile_match.group(1)
        
        # Extract business number and student ID (format: digits#digits)
        business_student_match = re.search(r'(\d+)#(\d+)', narrative_text)
        if business_student_match:
            details['business_number'] = business_student_match.group(1)
            details['student_id'] = business_student_match.group(2)
        
        # Extract name (everything after the business#studentID, or last word sequence)
        # This is optional and may not always be present
        name_match = re.search(r'\d+#\d+\s+(.+?)(?:\s|$)', narrative_text)
        if name_match:
            details['name'] = name_match.group(1).strip()
        
        return details
    
    def get_signed_token(self):
        """Generate an opaque signed token for this pattern to use in URLs."""
        from django.core import signing
        payload = {'patid': self.id}
        return signing.dumps(payload)
    
    @classmethod
    def from_signed_token(cls, token):
        """Resolve a signed token back to a BankStatementPattern object."""
        from django.core import signing
        from django.core.signing import BadSignature
        try:
            data = signing.loads(token)
            pat_id = data.get('patid')
            if not pat_id:
                return None
            return cls.objects.get(id=pat_id)
        except (BadSignature, ValueError, cls.DoesNotExist, TypeError):
            return None
    
    class Meta:
        ordering = ['school', 'bank_name', 'pattern_name']
        unique_together = ['school', 'bank_name', 'pattern_name']


def extract_student_id_from_mpesa_reference(reference_text):
    """
    Utility function to extract student ID from M-Pesa reference.
    M-Pesa format: BUSINESS_NUMBER#STUDENT_ID
    
    Args:
        reference_text: The AccountReference from M-Pesa (e.g., "123456#00001")
    
    Returns:
        Student ID string or None if not found
    
    Example:
        >>> extract_student_id_from_mpesa_reference("123456#00001")
        '00001'
    """
    if not reference_text:
        return None
    
    # M-Pesa pattern: BUSINESS_NUMBER#STUDENT_ID
    match = re.search(r'#(\d+)', reference_text)
    if match:
        return match.group(1)
    
    return None


class BankStatementUpload(models.Model):
    """Model to track uploaded bank statements"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='bank_statement_uploads')
    pattern = models.ForeignKey(
        BankStatementPattern,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploads'
    )
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    total_transactions = models.IntegerField(default=0)
    matched_payments = models.IntegerField(default=0)
    unmatched_payments = models.IntegerField(default=0)
    duplicate_transactions = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Bank Statement: {self.file_name} - {self.get_status_display()} ({self.school.name})"
    
    class Meta:
        ordering = ['-uploaded_at']


class UnmatchedTransaction(models.Model):
    """Model to track unmatched transactions from bank statements"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='unmatched_transactions')
    upload = models.ForeignKey(
        BankStatementUpload,
        on_delete=models.CASCADE,
        related_name='unmatched_transactions',
        null=True,
        blank=True
    )
    transaction_date = models.DateField()
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    reference_number = models.CharField(max_length=200, blank=True, help_text='Transaction reference/narrative from bank statement')
    bank_reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text='Unique bank transaction reference number (for duplicate detection per school)'
    )
    mpesa_reference = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text='M-Pesa transaction reference (e.g., TK18K8USG7) - unique identifier'
    )
    mobile_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text='Mobile number from M-Pesa narrative (e.g., 254721266013)'
    )
    extracted_student_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Student ID extracted from reference (if any)'
    )
    bank_account = models.CharField(max_length=100, blank=True, help_text='Bank account number if available')
    transaction_type = models.CharField(
        max_length=20,
        choices=[
            ('credit', 'Credit (Deposit)'),
            ('debit', 'Debit (Withdrawal)'),
        ],
        default='credit'
    )
    
    # Matching status
    STATUS_CHOICES = [
        ('unmatched', 'Unmatched'),
        ('matched', 'Matched'),
        ('ignored', 'Ignored'),
        ('manual', 'Manual Match'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unmatched')
    
    # If matched, link to payment
    matched_payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_transactions',
        help_text='Payment this transaction was matched to'
    )
    matched_student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unmatched_transactions',
        help_text='Student this transaction was matched to'
    )
    
    # Notes and actions
    notes = models.TextField(blank=True, help_text='Internal notes about this transaction')
    matched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_transactions')
    matched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Unmatched: {self.transaction_date} - KES {self.amount} - {self.reference_number[:50]}"
    
    def get_signed_token(self):
        """Generate an opaque signed token for this transaction to use in URLs."""
        from django.core import signing
        payload = {'untid': self.id}
        return signing.dumps(payload)
    
    @classmethod
    def from_signed_token(cls, token):
        """Resolve a signed token back to an UnmatchedTransaction object."""
        from django.core import signing
        from django.core.signing import BadSignature
        try:
            data = signing.loads(token)
            unt_id = data.get('untid')
            if not unt_id:
                return None
            return cls.objects.get(id=unt_id)
        except (BadSignature, ValueError, cls.DoesNotExist, TypeError):
            return None
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        # Ensure bank_reference_number is unique per school (when not null)
        unique_together = [['school', 'bank_reference_number']]
        indexes = [
            models.Index(fields=['school', 'status', 'transaction_date']),
            models.Index(fields=['school', 'extracted_student_id']),
            models.Index(fields=['school', 'bank_reference_number'], name='unmatched_bank_ref_idx'),
            models.Index(fields=['school', 'mpesa_reference'], name='unmatched_mpesa_ref_idx'),
        ]


# ==================== Signals ====================

@receiver(post_save, sender=StudentFee)
def sync_receivable_from_student_fee(sender, instance, created, **kwargs):
    """Automatically create/update receivable when StudentFee is created/updated"""
    if created or kwargs.get('update_fields') is None or 'amount_paid' in kwargs.get('update_fields', []):
        receivable, created_rec = Receivable.objects.get_or_create(
            school=instance.school,
            student_fee=instance,
            defaults={
                'student': instance.student,
                'amount_due': instance.amount_charged,
                'amount_paid': instance.amount_paid,
                'due_date': instance.due_date,
                'is_cleared': instance.is_paid,
            }
        )
        if not created_rec:
            # Update existing receivable
            receivable.amount_due = instance.amount_charged
            receivable.amount_paid = instance.amount_paid
            receivable.due_date = instance.due_date
            receivable.is_cleared = instance.is_paid
            if instance.is_paid and not receivable.cleared_at:
                from django.utils import timezone
                receivable.cleared_at = timezone.now()
            receivable.save()


@receiver(post_save, sender=Payment)
def create_payment_allocation(sender, instance, created, **kwargs):
    """Automatically create payment allocation when Payment is created"""
    if created and instance.status == 'completed':
        # Check if allocation already exists
        existing_allocation = PaymentAllocation.objects.filter(
            school=instance.school,
            payment=instance,
            student_fee=instance.student_fee
        ).first()
        
        if not existing_allocation:
            # Create allocation
            PaymentAllocation.objects.create(
                school=instance.school,
                payment=instance,
                student_fee=instance.student_fee,
                amount_allocated=instance.amount,
                created_by=instance.processed_by
            )
            
            # Update receivable
            try:
                receivable = Receivable.objects.get(
                    school=instance.school,
                    student_fee=instance.student_fee
                )
                receivable.amount_paid = instance.student_fee.amount_paid
                receivable.is_cleared = instance.student_fee.is_paid
                if instance.student_fee.is_paid and not receivable.cleared_at:
                    from django.utils import timezone
                    receivable.cleared_at = timezone.now()
                receivable.save()
            except Receivable.DoesNotExist:
                pass
