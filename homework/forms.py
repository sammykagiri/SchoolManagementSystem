"""
Forms for homework module
"""
from django import forms
from .models import Assignment, AssignmentSubmission
from core.models import SchoolClass
from timetable.models import Subject


class AssignmentForm(forms.ModelForm):
    """Form for creating and updating assignments"""
    
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'subject', 'school_class', 'due_date',
            'max_marks', 'attachment', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.txt'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        if school:
            self.fields['subject'].queryset = Subject.objects.filter(school=school, is_active=True)
            self.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, is_active=True)
        
        # Make required fields obvious
        self.fields['title'].required = True
        self.fields['subject'].required = True
        self.fields['school_class'].required = True
        self.fields['due_date'].required = True
        self.fields['max_marks'].required = True
        
        # Add help text
        self.fields['attachment'].help_text = 'Optional - Upload assignment file (PDF, DOC, DOCX, TXT)'
        self.fields['description'].help_text = 'Provide detailed instructions for the assignment'


class AssignmentSubmissionForm(forms.ModelForm):
    """Form for student assignment submission"""
    
    class Meta:
        model = AssignmentSubmission
        fields = ['submission_file', 'submission_text']
        widgets = {
            'submission_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png'
            }),
            'submission_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Enter your submission text here (if not uploading a file)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['submission_file'].help_text = 'Upload your assignment file (PDF, DOC, DOCX, TXT, Images)'
        self.fields['submission_text'].help_text = 'Or type your submission directly (if no file)'
    
    def clean(self):
        cleaned_data = super().clean()
        submission_file = cleaned_data.get('submission_file')
        submission_text = cleaned_data.get('submission_text')
        
        if not submission_file and not submission_text:
            raise forms.ValidationError(
                'Either upload a file or provide text submission. Both cannot be empty.'
            )
        
        return cleaned_data


class GradeSubmissionForm(forms.ModelForm):
    """Form for teacher to grade assignment submission"""
    
    class Meta:
        model = AssignmentSubmission
        fields = ['marks_obtained', 'feedback']
        widgets = {
            'marks_obtained': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Provide feedback to the student...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        assignment = kwargs.pop('assignment', None)
        super().__init__(*args, **kwargs)
        
        if assignment:
            self.fields['marks_obtained'].widget.attrs['max'] = str(assignment.max_marks)
            self.fields['marks_obtained'].help_text = f'Maximum marks: {assignment.max_marks}'
        
        self.fields['marks_obtained'].required = True
        self.fields['feedback'].help_text = 'Optional - Provide feedback to help the student improve'
