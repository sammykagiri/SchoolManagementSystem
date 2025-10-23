from django import forms
from .models import Term

class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ['name', 'term_number', 'academic_year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
