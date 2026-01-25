from django import forms
from .models import Credit, BankStatementPattern
from core.models import Student, School


class CreditForm(forms.ModelForm):
    """Form for creating/editing credits"""
    class Meta:
        model = Credit
        fields = ['student', 'amount', 'source', 'description', 'payment']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'source': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'payment': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        if school:
            # Filter students by school
            self.fields['student'].queryset = Student.objects.filter(
                school=school,
                is_active=True
            ).order_by('student_id', 'first_name', 'last_name')
            
            # Filter payments by school
            from .models import Payment
            self.fields['payment'].queryset = Payment.objects.filter(
                school=school,
                status='completed'
            ).select_related('student').order_by('-payment_date')
        
        # Make payment optional
        self.fields['payment'].required = False
        self.fields['payment'].empty_label = 'None (manual credit)'
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError('Credit amount must be greater than zero.')
        return amount


class BankStatementPatternForm(forms.ModelForm):
    """Form for creating/editing bank statement patterns"""
    class Meta:
        model = BankStatementPattern
        fields = [
            'school', 'bank_name', 'pattern_name',
            'date_column', 'amount_column', 'reference_column',
            'student_id_pattern', 'amount_pattern',
            'date_format', 'has_header', 'delimiter', 'encoding', 'is_active'
        ]
        widgets = {
            'school': forms.Select(attrs={'class': 'form-select'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Equity Bank, KCB'}),
            'pattern_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Equity CSV Format'}),
            'date_column': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Date or 0'}),
            'amount_column': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Amount or 1'}),
            'reference_column': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Narrative or 2'}),
            'student_id_pattern': forms.TextInput(attrs={'class': 'form-control', 'placeholder': r'#(\d+) for M-Pesa format or r"STUDENT\s*(\d+)"'}),
            'amount_pattern': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional regex pattern'}),
            'date_format': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '%Y-%m-%d'}),
            'has_header': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'delimiter': forms.Select(attrs={'class': 'form-select'}, choices=[(',', 'Comma'), (';', 'Semicolon'), ('\t', 'Tab')]),
            'encoding': forms.Select(attrs={'class': 'form-select'}, choices=[('utf-8', 'UTF-8'), ('latin-1', 'Latin-1'), ('cp1252', 'Windows-1252')]),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # School field will be set in the view
        self.fields['school'].widget = forms.HiddenInput()
        self.fields['delimiter'].widget = forms.Select(choices=[
            (',', 'Comma (,)'),
            (';', 'Semicolon (;)'),
            ('\t', 'Tab'),
        ])
        self.fields['encoding'].widget = forms.Select(choices=[
            ('utf-8', 'UTF-8'),
            ('latin-1', 'Latin-1'),
            ('cp1252', 'Windows-1252'),
            ('iso-8859-1', 'ISO-8859-1'),
        ])
