from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Student, Grade, TransportRoute, Role, UserProfile, School, SchoolClass


class StudentForm(forms.ModelForm):
    """Form for creating and updating students"""
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'gender', 'date_of_birth', 
            'grade', 'school_class', 'admission_date', 'parent_name', 'parent_phone', 
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
            'school_class': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        if school:
            # Filter grades by school
            self.fields['grade'].queryset = Grade.objects.filter(school=school)
            # Filter school classes by school and active status, include class_teacher
            self.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, is_active=True).select_related('class_teacher')
            self.fields['transport_route'].queryset = TransportRoute.objects.filter(school=school, is_active=True)
            # Filter parents by school
            from .models import Parent
            self.fields['parents'].queryset = Parent.objects.filter(school=school, is_active=True)
        
        # Filter school_class based on selected grade when editing
        if self.instance and self.instance.pk and self.instance.grade:
            # Filter classes by the student's grade
            queryset = SchoolClass.objects.filter(
                school=school if school else self.instance.school,
                grade=self.instance.grade,
                is_active=True
            ).select_related('class_teacher')
            # Ensure the currently assigned class is included even if it doesn't match the grade filter
            if self.instance.school_class:
                queryset = queryset | SchoolClass.objects.filter(
                    id=self.instance.school_class.id,
                    school=school if school else self.instance.school
                ).select_related('class_teacher')
            self.fields['school_class'].queryset = queryset.distinct()
        
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
        self.fields['school_class'].help_text = 'Optional - assign student to a specific class'
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
        # Extract current_user from kwargs if provided
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        # Filter active roles only
        roles_queryset = Role.objects.filter(is_active=True)
        
        # Check if current user is a superadmin
        is_superadmin = False
        if self.current_user:
            is_superadmin = (
                self.current_user.is_superuser or 
                (hasattr(self.current_user, 'profile') and self.current_user.profile.is_super_admin)
            )
            if not is_superadmin:
                # Exclude super_admin role for non-superadmins
                roles_queryset = roles_queryset.exclude(name='super_admin')
                
                # Hide school field for school admins - they can only assign users to their own school
                if hasattr(self.current_user, 'profile') and self.current_user.profile.school:
                    admin_school = self.current_user.profile.school
                    # Always use HiddenInput for school admins
                    self.fields['school'].widget = forms.HiddenInput()
                    # Set the value to the admin's school
                    if self.instance and self.instance.pk:
                        # For existing users, the value should already be set from the instance
                        # But ensure it's the admin's school (view-level checks prevent mismatches)
                        if self.instance.school != admin_school:
                            # Force to admin's school (this shouldn't happen due to view checks)
                            self.fields['school'].initial = admin_school
                    else:
                        # For new users, set to admin's school
                        self.fields['school'].initial = admin_school
                        self.fields['school'].required = False  # Hidden fields don't need to be required
                else:
                    # School admin without a school - hide the field
                    self.fields['school'].widget = forms.HiddenInput()
        
        self.fields['roles'].queryset = roles_queryset
        self.fields['roles'].help_text = 'Select one or more roles for this user'
        if is_superadmin:
            self.fields['school'].help_text = 'Assign user to a school'
    
    def clean_school(self):
        """Validate school assignment - only superadmins can change it"""
        school = self.cleaned_data.get('school')
        
        if self.current_user:
            is_superadmin = (
                self.current_user.is_superuser or 
                (hasattr(self.current_user, 'profile') and self.current_user.profile.is_super_admin)
            )
            
            if not is_superadmin:
                # School admins can only assign users to their own school
                if hasattr(self.current_user, 'profile') and self.current_user.profile.school:
                    admin_school = self.current_user.profile.school
                    # If editing existing user, check if school is being changed
                    if self.instance and self.instance.pk:
                        original_school = self.instance.school
                        if school != original_school and school != admin_school:
                            raise ValidationError("You do not have permission to change the school assignment. Only superadmins can reassign users to different schools.")
                    # For new users or if school matches admin's school, allow it
                    if school != admin_school:
                        raise ValidationError("You can only assign users to your own school. Only superadmins can reassign users to different schools.")
                else:
                    raise ValidationError("You must be assigned to a school before you can assign users.")
        
        return school
    
    def clean_roles(self):
        roles = self.cleaned_data.get('roles')
        if not roles or roles.count() == 0:
            raise ValidationError("Please assign at least one role to this user.")
        
        # Prevent school admins from assigning super_admin role
        if self.current_user:
            is_superadmin = (
                self.current_user.is_superuser or 
                (hasattr(self.current_user, 'profile') and self.current_user.profile.is_super_admin)
            )
            if not is_superadmin:
                super_admin_role = roles.filter(name='super_admin')
                if super_admin_role.exists():
                    raise ValidationError("You do not have permission to assign the super_admin role.")
        
        return roles
