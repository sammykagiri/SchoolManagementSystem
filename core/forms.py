from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Student, Grade, TransportRoute, Role, UserProfile, School


class StudentForm(forms.ModelForm):
    """Form for creating and updating students"""
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'gender', 'date_of_birth', 
            'grade', 'admission_date', 'parent_name', 'parent_phone', 
            'parent_email', 'address', 'transport_route', 'uses_transport', 
            'pays_meals', 'pays_activities', 'photo', 'parents'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'admission_date': forms.DateInput(attrs={'type': 'date'}),
            'parent_email': forms.EmailInput(),
            'address': forms.Textarea(attrs={'rows': 3}),
            'uses_transport': forms.CheckboxInput(),
            'pays_meals': forms.CheckboxInput(),
            'pays_activities': forms.CheckboxInput(),
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
            'parents': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        if school:
            # Filter grades by school
            self.fields['grade'].queryset = Grade.objects.filter(school=school)
            self.fields['transport_route'].queryset = TransportRoute.objects.filter(school=school, is_active=True)
            # Filter parents by school
            from .models import Parent
            self.fields['parents'].queryset = Parent.objects.filter(school=school, is_active=True)
        
        # Make required fields more obvious
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['gender'].required = True
        self.fields['date_of_birth'].required = True
        self.fields['grade'].required = True
        self.fields['admission_date'].required = True
        self.fields['parent_name'].required = True
        self.fields['parent_phone'].required = True
        
        # Add help text
        self.fields['parent_email'].help_text = 'Optional - for sending receipts and notifications'
        self.fields['address'].help_text = 'Optional - student home address'
        self.fields['transport_route'].help_text = 'Optional - if student uses school transport'
        self.fields['photo'].help_text = 'Optional - Upload student photo (JPG, PNG, max 5MB)'
        self.fields['parents'].help_text = 'Select parent accounts linked to this student (optional)'
        
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ in ['TextInput', 'EmailInput', 'DateInput']:
                field.widget.attrs['class'] = 'form-control'
            elif field.widget.__class__.__name__ == 'Select':
                field.widget.attrs['class'] = 'form-select'
            elif field.widget.__class__.__name__ == 'Textarea':
                field.widget.attrs['class'] = 'form-control'
            elif field.widget.__class__.__name__ == 'CheckboxInput':
                field.widget.attrs['class'] = 'form-check-input'
            elif field.widget.__class__.__name__ == 'FileInput':
                field.widget.attrs['class'] = 'form-control'
    
    def clean_parent_phone(self):
        """Validate parent phone number"""
        phone = self.cleaned_data.get('parent_phone')
        if phone:
            # Remove any non-digit characters for validation
            digits_only = ''.join(filter(str.isdigit, phone))
            if len(digits_only) < 10:
                raise ValidationError('Phone number must be at least 10 digits long.')
        return phone
    
    def clean_parent_email(self):
        """Validate parent email if provided"""
        email = self.cleaned_data.get('parent_email')
        if email:
            # Basic email validation is handled by EmailField
            pass
        return email
    
    def clean_date_of_birth(self):
        """Validate date of birth"""
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            from datetime import date
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            
            if age < 3:
                raise ValidationError('Student must be at least 3 years old.')
            if age > 25:
                raise ValidationError('Student age seems too high. Please check the date of birth.')
        return dob
    
    def clean_admission_date(self):
        """Validate admission date"""
        admission_date = self.cleaned_data.get('admission_date')
        dob = self.cleaned_data.get('date_of_birth')
        
        if admission_date and dob:
            if admission_date < dob:
                raise ValidationError('Admission date cannot be before date of birth.')
        
        return admission_date


class UserForm(UserCreationForm):
    """Form for creating users"""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    is_staff = forms.BooleanField(required=False, label="Staff Status", 
                                  help_text="Designates whether the user can log into the admin site.")
    is_active = forms.BooleanField(required=False, label="Active", 
                                    help_text="Designates whether this user should be treated as active.")
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active')


class UserEditForm(forms.ModelForm):
    """Form for editing users"""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    is_staff = forms.BooleanField(required=False, label="Staff Status", 
                                  help_text="Designates whether the user can log into the admin site.")
    is_active = forms.BooleanField(required=False, label="Active", 
                                    help_text="Designates whether this user should be treated as active.")
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')


class UserProfileForm(forms.ModelForm):
    """Form for user profile with role assignment"""
    class Meta:
        model = UserProfile
        fields = ('school', 'roles', 'is_active')
        widgets = {
            'school': forms.Select(attrs={'class': 'form-select'}),
            'roles': forms.CheckboxSelectMultiple(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active roles only
        self.fields['roles'].queryset = Role.objects.filter(is_active=True)
        self.fields['roles'].help_text = 'Select one or more roles for this user'
        self.fields['school'].help_text = 'Assign user to a school'
    
    def clean_roles(self):
        roles = self.cleaned_data.get('roles')
        if not roles or roles.count() == 0:
            raise ValidationError("Please assign at least one role to this user.")
        return roles
