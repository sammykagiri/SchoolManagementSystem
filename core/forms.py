from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Student, Grade, TransportRoute, Role, UserProfile, School, SchoolClass, FeeCategory, Parent


class StudentForm(forms.ModelForm):
    """Form for creating and updating students"""
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'middle_name', 'last_name', 'upi', 'gender', 'date_of_birth', 
            'grade', 'school_class', 'admission_date', 'parent_name', 'parent_phone', 
            'parent_email', 'address', 'transport_route', 'uses_transport', 
            'photo', 'parents', 'optional_fee_categories'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'admission_date': forms.DateInput(attrs={'type': 'date'}),
            'parent_email': forms.EmailInput(),
            'address': forms.Textarea(attrs={'rows': 3}),
            'uses_transport': forms.CheckboxInput(),
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
            'parents': forms.CheckboxSelectMultiple(attrs={'style': 'display: none;'}),  # Hidden - handled by custom UI
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'optional_fee_categories': forms.CheckboxSelectMultiple(),
            'upi': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '11',
                'pattern': '[0-9]{11}',
                'placeholder': 'Enter 11-digit NEMIS/UPI number'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        if school:
            # Filter grades by school
            self.fields['grade'].queryset = Grade.objects.filter(school=school)
            # Filter school classes by school and active status, include class_teacher
            self.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, is_active=True).select_related('class_teacher')
            # Filter active routes - check date ranges
            from django.utils import timezone
            from django.db.models import Q
            today = timezone.now().date()
            active_routes = TransportRoute.objects.filter(
                school=school,
                is_active=True
            ).filter(
                Q(active_start_date__isnull=True) | Q(active_start_date__lte=today)
            ).filter(
                Q(active_end_date__isnull=True) | Q(active_end_date__gte=today)
            )
            self.fields['transport_route'].queryset = active_routes
            # Filter parents by school
            from .models import Parent
            self.fields['parents'].queryset = Parent.objects.filter(school=school, is_active=True)
            
            # Filter optional fee categories by school and set defaults
            if school:
                optional_categories = FeeCategory.objects.filter(school=school, is_optional=True)
                self.fields['optional_fee_categories'].queryset = optional_categories
                
                # Set initial values for new students based on apply_by_default
                if not self.instance.pk:  # New student
                    default_categories = optional_categories.filter(apply_by_default=True)
                    self.fields['optional_fee_categories'].initial = list(default_categories.values_list('id', flat=True))
            else:
                # No school provided - hide the field
                self.fields['optional_fee_categories'].queryset = FeeCategory.objects.none()
        
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
        
        # Make parent fields optional (since we're using linked parent accounts)
        self.fields['parent_name'].required = False
        self.fields['parent_phone'].required = False
        self.fields['parent_email'].required = False
        self.fields['address'].required = False
        
        # Add help text
        if 'upi' in self.fields:
            self.fields['upi'].help_text = '11-digit NEMIS / UPI number issued by the Ministry of Education (optional)'
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
    
    def clean_upi(self):
        """Validate UPI field"""
        upi = self.cleaned_data.get('upi')
        
        if upi:
            # Remove any whitespace
            upi = upi.strip()
            
            # Check if it contains only digits
            if not upi.isdigit():
                raise ValidationError('UPI number must contain only digits.')
            
            # Check if it's exactly 11 characters
            if len(upi) != 11:
                raise ValidationError('UPI number must be exactly 11 digits.')
            
            # Check for uniqueness (excluding current instance if updating)
            existing_student = Student.objects.filter(upi=upi).exclude(pk=self.instance.pk if self.instance.pk else None).first()
            if existing_student:
                raise ValidationError(f'This UPI number is already assigned to student: {existing_student.full_name} ({existing_student.student_id}).')
        
        return upi
    
    def clean(self):
        """Additional form-level validation"""
        cleaned_data = super().clean()
        
        # Ensure UPI is stored without whitespace
        if 'upi' in cleaned_data and cleaned_data['upi']:
            cleaned_data['upi'] = cleaned_data['upi'].strip()
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to automatically set uses_transport based on transport_route"""
        student = super().save(commit=False)

        # Automatically set uses_transport based on transport_route assignment
        # If a route is assigned, student uses transport; otherwise, they don't
        student.uses_transport = bool(student.transport_route)

        if commit:
            student.save()
            self.save_m2m()

        return student


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
    
    def __init__(self, *args, **kwargs):
        # Extract school from kwargs if provided
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        # Update help text based on school
        if self.school:
            if self.school.short_name:
                self.fields['username'].help_text = f'Required. Your username will be automatically formatted as "username@{self.school.short_name}" to ensure uniqueness across schools.'
            else:
                self.fields['username'].help_text = f'Required. School short name must be set before creating users. Please set the school short name first.'
        else:
            self.fields['username'].help_text = 'Required. Username will be formatted as "username@shortname" based on the selected school.'
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            return username
        
        # Get school from form instance or from POST data
        school = self.school
        if not school and hasattr(self, 'data') and self.data:
            # Try to get school from profile form data
            school_id = self.data.get('school')
            if school_id:
                try:
                    from .models import School
                    school = School.objects.get(id=school_id)
                except (School.DoesNotExist, ValueError):
                    pass
        
        if school:
            # Require short_name for user creation
            if not school.short_name:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    'School short name is required for user creation. '
                    'Please set the school short name in school settings first. '
                    'Format: one word or two words separated by dot (.), underscore (_), or hyphen (-).'
                )
            
            # Use short_name
            school_identifier = school.short_name.lower().strip()
            
            # Get base username (strip whitespace, convert to lowercase, and remove @ if user already added it)
            base_username = username.strip().lower()
            # Remove any existing @school suffix if user mistakenly added it
            if '@' in base_username:
                base_username = base_username.split('@')[0].strip().lower()
            
            # Create final username with school suffix (already lowercase)
            final_username = f"{base_username}@{school_identifier}"
            
            # Ensure username doesn't exceed 150 characters (Django's limit)
            if len(final_username) > 150:
                max_base_len = 150 - len(f"@{school_identifier}") - 1
                if max_base_len > 0:
                    base_username = base_username[:max_base_len]
                    final_username = f"{base_username}@{school_identifier}"
                else:
                    # School identifier is too long - truncate it
                    max_school_len = 150 - len(base_username) - 1
                    school_identifier = school_identifier[:max_school_len]
                    final_username = f"{base_username}@{school_identifier}"
            
            # Check if username is already taken
            from django.contrib.auth.models import User
            if User.objects.filter(username=final_username).exists():
                # Try to append a number
                counter = 1
                while True:
                    new_username = f"{base_username}{counter}@{school_identifier}"
                    if len(new_username) > 150:
                        max_base_len = 150 - len(f"{counter}@{school_identifier}") - 1
                        if max_base_len > 0:
                            base_username = base_username[:max_base_len]
                            new_username = f"{base_username}{counter}@{school_identifier}"
                        else:
                            max_school_len = 150 - len(f"{base_username}{counter}") - 1
                            school_identifier = school_identifier[:max_school_len]
                            new_username = f"{base_username}{counter}@{school_identifier}"
                    
                    if not User.objects.filter(username=new_username).exists():
                        final_username = new_username
                        break
                    counter += 1
                    if counter > 1000:  # Safety limit
                        from django.core.exceptions import ValidationError
                        raise ValidationError('Unable to generate a unique username. Please try a different base username.')
            
            return final_username
        
        # If no school, return username as-is (shouldn't happen in normal flow)
        return username


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


class ParentRegistrationForm(UserCreationForm):
    """Form for parent/guardian registration"""
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)
    phone = forms.CharField(max_length=15, required=False, help_text='Contact phone number')
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, help_text='Address')
    preferred_contact_method = forms.ChoiceField(
        choices=[
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('email', 'Email'),
        ],
        initial='phone',
        required=False,
        help_text='Preferred method of contact'
    )
    # Custom widget to filter out empty strings
    class FilteredCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
        def value_from_datadict(self, data, files, name):
            """Filter out empty strings from the data"""
            values = super().value_from_datadict(data, files, name)
            if values is None:
                return []
            # Filter out empty strings, None, and whitespace-only values
            filtered = [v for v in values if v is not None and str(v).strip() != '']
            return filtered if filtered else []
    
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        widget=FilteredCheckboxSelectMultiple(),
        help_text='Select students to link to this parent account (optional - can be done later)',
        error_messages={
            'invalid_choice': 'Select a valid student.',
            'list': 'Select a valid list of students.',
            'invalid': 'Select a valid student.',
        }
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
    
    # Note: phone, address, preferred_contact_method, and students are not User model fields
    # They are handled separately in the save() method
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        # Store school in form instance for use in clean methods
        self.school = school
        
        # Store school for later use in to_python wrapper
        form_school = school
        
        # Override the students field's to_python to handle empty strings
        original_to_python = self.fields['students'].to_python
        def to_python_wrapper(value):
            # Handle empty strings and None
            if not value or value == '' or (isinstance(value, list) and len(value) == 1 and value[0] == ''):
                return []
            # Filter out empty strings from list
            if isinstance(value, list):
                value = [v for v in value if v and v.strip() and v != '']
                if not value:
                    return []
            
            # Ensure queryset is set before validation
            if not self.fields['students'].queryset.exists() and form_school:
                self.fields['students'].queryset = Student.objects.filter(
                    school=form_school,
                    is_active=True
                ).order_by('first_name', 'last_name')
            
            try:
                return original_to_python(value)
            except (ValidationError, ValueError) as e:
                # If validation fails, try to get students directly by ID
                if isinstance(value, list) and value and form_school:
                    try:
                        student_ids = [int(v) for v in value if str(v).isdigit()]
                        if student_ids:
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=form_school,
                                is_active=True
                            )
                            if students.exists():
                                return list(students)
                    except (ValueError, TypeError):
                        pass
                # If all else fails, return empty list
                return []
        self.fields['students'].to_python = to_python_wrapper
        
        if school:
            # Filter students by school
            self.fields['students'].queryset = Student.objects.filter(
                school=school, 
                is_active=True
            ).order_by('first_name', 'last_name')
        else:
            self.fields['students'].queryset = Student.objects.none()
        
        # Make fields more user-friendly
        if school:
            school_id = school.name.lower().replace(' ', '_').replace('-', '_')[:20]
            import re
            school_id = re.sub(r'[^a-z0-9_]', '', school_id)
            if school.short_name:
                self.fields['username'].help_text = f'Required. Your username will be automatically formatted as "username@{school.short_name}" to ensure uniqueness across schools.'
            else:
                self.fields['username'].help_text = f'Required. School short name must be set before registering parents. Please contact administrator to set the school short name first.'
        else:
            self.fields['username'].help_text = 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
        self.fields['password1'].help_text = 'Your password must contain at least 8 characters.'
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email
        
        # Check if email exists for a parent in the same school
        if self.school:
            # Debug: Log the school being checked
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'clean_email - Checking for email: {email} in school: {self.school.name} (ID: {self.school.id})')
            
            # Check if a parent with this email (via User.email) already exists in this school
            # We check by User.email since that's what the form uses
            existing_parent = Parent.objects.filter(
                school=self.school,
                user__email=email
            ).first()
            
            if existing_parent:
                logger.warning(f'clean_email - Found existing parent with email {email} in school {self.school.name} (ID: {self.school.id})')
                raise ValidationError('A parent with this email already exists in this school.')
            
            # Also check Parent.email field as a fallback (in case it was set differently)
            # But only if it's not the same as user__email to avoid duplicate checks
            existing_parent_by_parent_email = Parent.objects.filter(
                school=self.school,
                email=email
            ).exclude(user__email=email).first()
            
            if existing_parent_by_parent_email:
                logger.warning(f'clean_email - Found existing parent with email {email} in Parent.email field for school {self.school.name} (ID: {self.school.id})')
                raise ValidationError('A parent with this email already exists in this school.')
            
            # If a User with this email exists and is a parent in a different school,
            # we'll handle it in the save() method by updating their school assignment
            # So we allow the form to proceed here
        else:
            # If no school is set, log a warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning('clean_email - No school set in form, skipping school-specific validation')
        
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            return username
        
        # Get school from form instance or POST data
        school = self.school
        if not school and hasattr(self, 'data') and self.data:
            school_id = self.data.get('school')
            if school_id:
                try:
                    school = School.objects.get(id=school_id)
                except (School.DoesNotExist, ValueError):
                    pass
        
        if school:
            # Generate unique username by appending school identifier
            # Use school short_name (required for parent registration)
            import re
            import logging
            logger = logging.getLogger(__name__)
            
            # Require short_name for parent registration
            if not school.short_name:
                raise ValidationError(
                    'School short name is required for parent registration. '
                    'Please set the school short name in school settings first. '
                    'Format: one word or two words separated by dot (.), underscore (_), or hyphen (-).'
                )
            
            # Use short_name
            school_identifier = school.short_name.lower().strip()
            
            # Ensure school_identifier is not empty
            if not school_identifier:
                raise ValidationError('School short name cannot be empty.')
            
            # Get base username (strip whitespace, convert to lowercase, and remove @ if user already added it)
            base_username = username.strip().lower()
            # Remove any existing @school suffix if user mistakenly added it
            if '@' in base_username:
                base_username = base_username.split('@')[0].strip().lower()
            
            # Create final username with school suffix (already lowercase)
            final_username = f"{base_username}@{school_identifier}"
            
            # Ensure username doesn't exceed 150 characters (Django's limit)
            if len(final_username) > 150:
                # Truncate base username if needed
                max_base_len = 150 - len(f"@{school_identifier}") - 1
                if max_base_len > 0:
                    base_username = base_username[:max_base_len]
                    final_username = f"{base_username}@{school_identifier}"
                else:
                    # If school identifier is too long, truncate it
                    max_school_len = 150 - len(base_username) - 1
                    school_identifier = school_identifier[:max_school_len] if max_school_len > 0 else 'school'
                    final_username = f"{base_username}@{school_identifier}"
            
            logger.info(f'clean_username - Formatting username: "{username}" -> "{final_username}" for school: {school.name} (ID: {school.id})')
            
            # Check if this username already exists globally
            if User.objects.filter(username=final_username).exists():
                # If it exists, check if it's for a parent in the same school
                existing_user = User.objects.get(username=final_username)
                if hasattr(existing_user, 'parent_profile'):
                    existing_parent = existing_user.parent_profile
                    if existing_parent.school == school:
                        raise ValidationError('This username is already taken in this school.')
                    # If it's a different school, append a number to make it unique
                    counter = 1
                    while User.objects.filter(username=final_username).exists():
                        counter += 1
                        new_username = f"{base_username}{counter}@{school_identifier}"
                        if len(new_username) > 150:
                            max_base_len = 150 - len(f"{counter}@{school_identifier}") - 1
                            if max_base_len > 0:
                                base_username = base_username[:max_base_len]
                            new_username = f"{base_username}{counter}@{school_identifier}"
                        final_username = new_username
                        if counter > 100:  # Safety limit to prevent infinite loop
                            raise ValidationError('Unable to generate a unique username. Please try a different base username.')
            
            # Update cleaned_data with the final username
            self.cleaned_data['username'] = final_username
            logger.info(f'clean_username - Final username: "{final_username}"')
            return final_username
        else:
            # If no school, use standard validation (for superuser creating without school)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning('clean_username - No school set, using username without school suffix')
            if User.objects.filter(username=username).exists():
                raise ValidationError('A user with this username already exists.')
            return username
    
    def clean_students(self):
        """Clean and validate students field - handle empty strings and invalid values"""
        # First, check if we have raw data with empty strings
        if hasattr(self, 'data') and self.data:
            raw_students = self.data.getlist('students', [])
            # Filter out empty strings, None, and whitespace-only values
            raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
            
            # If no valid student IDs after filtering, return empty list
            if not raw_students:
                # Explicitly set cleaned_data to empty list to avoid validation errors
                return []
        
        # Try to get cleaned data (this will validate the IDs if any were provided)
        # If cleaned_data doesn't have 'students' yet, it means validation hasn't run
        # In that case, we need to handle it manually
        if 'students' not in self.cleaned_data:
            # Check raw data again
            if hasattr(self, 'data') and self.data:
                raw_students = self.data.getlist('students', [])
                raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
                if not raw_students:
                    return []
                
                # Try to get students directly by ID
                school = getattr(self, 'school', None)
                if not school and hasattr(self, 'data') and self.data:
                    school_id = self.data.get('school')
                    if school_id:
                        try:
                            school = School.objects.get(id=school_id)
                        except (School.DoesNotExist, ValueError):
                            pass
                
                if school:
                    try:
                        student_ids = []
                        for s in raw_students:
                            try:
                                sid = int(s)
                                student_ids.append(sid)
                            except (ValueError, TypeError):
                                continue
                        
                        if student_ids:
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=school,
                                is_active=True
                            )
                            if students.exists():
                                return list(students)
                    except Exception:
                        pass
                return []
        
        # If we have cleaned_data with students, use it
        try:
            if 'students' in self.cleaned_data:
                students = self.cleaned_data['students']
                # Filter out any invalid entries and ensure all are valid Student instances
                if students:
                    valid_students = []
                    for student in students:
                        if student and isinstance(student, Student):
                            valid_students.append(student)
                    if valid_students:
                        return valid_students
        except (ValidationError, ValueError, KeyError):
            # If validation fails, try raw data fallback
            pass
        
        # Fallback: Try to get from raw data if cleaned_data is empty or missing
        if hasattr(self, 'data') and self.data:
            raw_students = self.data.getlist('students', [])
            raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
            if raw_students:
                school = getattr(self, 'school', None)
                if not school and hasattr(self, 'data') and self.data:
                    school_id = self.data.get('school')
                    if school_id:
                        try:
                            school = School.objects.get(id=school_id)
                        except (School.DoesNotExist, ValueError):
                            pass
                
                if school:
                    try:
                        student_ids = []
                        for s in raw_students:
                            try:
                                sid = int(s)
                                student_ids.append(sid)
                            except (ValueError, TypeError):
                                continue
                        
                        if student_ids:
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=school,
                                is_active=True
                            )
                            if students.exists():
                                return list(students)
                    except Exception:
                        pass
        
        return []
    
    def save(self, commit=True, school=None):
        email = self.cleaned_data.get('email')
        
        # Validate school is provided
        if not school:
            raise ValidationError('School is required to create a parent account.')
        
        # Log the school being used
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'ParentRegistrationForm.save - Using school: {school.name} (ID: {school.id})')
        
        # Check if a User with this email already exists
        existing_user = User.objects.filter(email=email).first()
        
        # Check if we should create a new user or use existing one
        should_create_new_user = True
        user = None
        parent = None
        
        if existing_user:
            # User already exists - check if they're already a parent
            if hasattr(existing_user, 'parent_profile'):
                existing_parent = existing_user.parent_profile
                # If parent exists in the same school, we can't create another (would violate unique_together)
                if existing_parent.school == school:
                    raise ValidationError('A parent with this email already exists in this school.')
                # If parent exists in a different school, that's okay - different schools can have parents with the same email
                # They are different entities with different usernames (different school postfixes)
                # We'll create a new user account for this school
                should_create_new_user = True
            else:
                # User exists but is not a parent - create Parent profile for existing user
                should_create_new_user = False
                user = existing_user
                # Update user details if provided
                if self.cleaned_data.get('first_name'):
                    user.first_name = self.cleaned_data.get('first_name', user.first_name)
                if self.cleaned_data.get('last_name'):
                    user.last_name = self.cleaned_data.get('last_name', user.last_name)
                user.save()
                
                if commit and school:
                    logger.info(f'ParentRegistrationForm.save - Creating Parent profile for user {user.username} in school {school.name} (ID: {school.id})')
                    parent = Parent.objects.create(
                        user=user,
                        school=school,
                        phone=self.cleaned_data.get('phone', ''),
                        email=self.cleaned_data.get('email', ''),
                        address=self.cleaned_data.get('address', ''),
                        preferred_contact_method=self.cleaned_data.get('preferred_contact_method', 'phone'),
                        photo=self.cleaned_data.get('photo'),
                        is_active=True
                    )
                    logger.info(f'ParentRegistrationForm.save - Created Parent profile ID: {parent.id} for school: {parent.school.name} (ID: {parent.school.id})')
                    # Update UserProfile's school to match Parent's school
                    if hasattr(user, 'profile'):
                        user.profile.school = school
                        user.profile.save()
                        logger.info(f'ParentRegistrationForm.save - Updated UserProfile school to {school.name} (ID: {school.id})')
                        # Automatically assign "Parent" role if it exists
                        try:
                            parent_role = Role.objects.filter(name='parent', is_active=True).first()
                            if parent_role and not user.profile.roles.filter(name='parent').exists():
                                user.profile.roles.add(parent_role)
                                logger.info(f'ParentRegistrationForm.save - Assigned "Parent" role to user {user.username}')
                        except Exception as e:
                            logger.warning(f'ParentRegistrationForm.save - Could not assign Parent role: {e}')
                else:
                    return user
        
        if should_create_new_user:
            # New user - create User and Parent
            user = super().save(commit=False)
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            
            if commit:
                user.save()
                
                # Create Parent profile
                if school:
                    logger.info(f'ParentRegistrationForm.save - Creating new User and Parent profile in school {school.name} (ID: {school.id})')
                    parent = Parent.objects.create(
                        user=user,
                        school=school,
                        phone=self.cleaned_data.get('phone', ''),
                        email=self.cleaned_data.get('email', ''),
                        address=self.cleaned_data.get('address', ''),
                        preferred_contact_method=self.cleaned_data.get('preferred_contact_method', 'phone'),
                        photo=self.cleaned_data.get('photo'),
                        is_active=True
                    )
                    logger.info(f'ParentRegistrationForm.save - Created new Parent profile ID: {parent.id} for school: {parent.school.name} (ID: {parent.school.id})')
                    # Update UserProfile's school to match Parent's school
                    # The signal creates UserProfile with default school, so we need to update it
                    if hasattr(user, 'profile'):
                        user.profile.school = school
                        user.profile.save()
                        logger.info(f'ParentRegistrationForm.save - Updated UserProfile school to {school.name} (ID: {school.id})')
                        # Automatically assign "Parent" role if it exists
                        try:
                            parent_role = Role.objects.filter(name='parent', is_active=True).first()
                            if parent_role and not user.profile.roles.filter(name='parent').exists():
                                user.profile.roles.add(parent_role)
                                logger.info(f'ParentRegistrationForm.save - Assigned "Parent" role to user {user.username}')
                        except Exception as e:
                            logger.warning(f'ParentRegistrationForm.save - Could not assign Parent role: {e}')
                else:
                    return user
        
        if commit and school:
            # Ensure parent is set (should always be set at this point if commit=True and school is not None)
            if parent is None:
                # This shouldn't happen, but log it and try to get parent from user
                logger.warning(f'ParentRegistrationForm.save - parent is None when it should be set. User: {user.username if user else "None"}')
                if user and hasattr(user, 'parent_profile'):
                    parent = user.parent_profile
                else:
                    raise ValueError('Parent was not created. This should not happen.')
            
            # Link selected students - always check raw form data first (more reliable)
            students = []
            
            # Check if we have form data (from POST request)
            # Try multiple sources: _post_data (from view), self.data (form's data), or cleaned_data
            post_data = None
            if hasattr(self, '_post_data') and self._post_data:
                post_data = self._post_data
            elif hasattr(self, 'data') and self.data is not None:
                post_data = self.data
            
            if post_data:
                try:
                    # Try getlist first (for QueryDict)
                    if hasattr(post_data, 'getlist'):
                        raw_students = post_data.getlist('students', [])
                    else:
                        # Fallback for regular dict
                        raw_students = post_data.get('students', [])
                        if not isinstance(raw_students, list):
                            raw_students = [raw_students] if raw_students else []
                    
                    # Filter out empty strings, None, and whitespace-only values
                    raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
                    
                    if raw_students and school:
                        try:
                            # Convert to integers and filter
                            student_ids = []
                            for sid in raw_students:
                                try:
                                    student_id = int(sid)
                                    student_ids.append(student_id)
                                except (ValueError, TypeError):
                                    continue
                            
                            if student_ids:
                                # Fetch students from database
                                fetched_students = Student.objects.filter(
                                    id__in=student_ids,
                                    school=school,
                                    is_active=True
                                )
                                if fetched_students.exists():
                                    students = list(fetched_students)
                        except Exception as e:
                            # Log error but don't fail the save
                            logger.error(f'Error linking students to parent during registration: {e}')
                except (AttributeError, KeyError) as e:
                    # If getlist fails, try alternative method
                    logger.warning(f'Could not get students from form data: {e}')
            
            # Fallback to cleaned_data if raw data didn't work (shouldn't happen, but just in case)
            if not students:
                students = self.cleaned_data.get('students', [])
            
            # Set the students - only set if we have students to avoid clearing on registration
            # For registration, if no students selected, don't set (preserves empty state)
            if students:
                parent.children.set(students)
                logger.info(f'Linked {len(students)} students to parent {parent.id} during registration')
            
            return parent
        
        return user


class ParentEditForm(forms.ModelForm):
    """Form for editing parent/guardian information"""
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)
    phone = forms.CharField(max_length=15, required=False, help_text='Contact phone number')
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, help_text='Address')
    preferred_contact_method = forms.ChoiceField(
        choices=[
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('email', 'Email'),
        ],
        required=False,
        help_text='Preferred method of contact'
    )
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        widget=ParentRegistrationForm.FilteredCheckboxSelectMultiple(),
        help_text='Select students to link to this parent account'
    )
    is_active = forms.BooleanField(required=False, help_text='Active status')
    
    class Meta:
        model = Parent
        fields = ('phone', 'address', 'preferred_contact_method', 'photo', 'is_active', 'students')
    
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        # Get the user from the parent instance
        if instance and instance.user:
            self.user = instance.user
            # Initialize user fields
            self.fields['email'] = forms.EmailField(
                required=True,
                initial=instance.user.email,
                help_text='Required. Enter a valid email address.'
            )
            self.fields['first_name'] = forms.CharField(
                required=True,
                max_length=150,
                initial=instance.user.first_name
            )
            self.fields['last_name'] = forms.CharField(
                required=True,
                max_length=150,
                initial=instance.user.last_name
            )
        else:
            self.user = None
        
        # Store school for later use
        self.school = school
        
        # Override the students field's to_python to handle empty strings (same as ParentRegistrationForm)
        form_school = school
        original_to_python = self.fields['students'].to_python
        def to_python_wrapper(value):
            # Handle None, empty strings, and empty lists
            if value is None:
                return []
            if value == '':
                return []
            if isinstance(value, list):
                # Filter out empty strings, None, and whitespace-only values
                filtered = [v for v in value if v is not None and str(v).strip() != '']
                if not filtered:
                    return []
                value = filtered
            
            # Ensure queryset is set before validation
            if not self.fields['students'].queryset.exists() and form_school:
                self.fields['students'].queryset = Student.objects.filter(
                    school=form_school,
                    is_active=True
                ).order_by('first_name', 'last_name')
            
            try:
                return original_to_python(value)
            except (ValidationError, ValueError) as e:
                # If validation fails, try to get students directly by ID
                if isinstance(value, list) and value and form_school:
                    try:
                        student_ids = []
                        for v in value:
                            try:
                                sid = int(v)
                                student_ids.append(sid)
                            except (ValueError, TypeError):
                                pass
                        if student_ids:
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=form_school,
                                is_active=True
                            )
                            if students.exists():
                                return list(students)
                    except (ValueError, TypeError):
                        pass
                # If all else fails, return empty list
                return []
        self.fields['students'].to_python = to_python_wrapper
        
        if school:
            # Filter students by school
            self.fields['students'].queryset = Student.objects.filter(
                school=school, 
                is_active=True
            ).order_by('first_name', 'last_name')
            
            # Set initial students if editing
            if instance:
                self.fields['students'].initial = instance.children.all()
        else:
            self.fields['students'].queryset = Student.objects.none()
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email
        
        # Get the current parent instance
        instance = getattr(self, 'instance', None)
        current_parent = None
        if instance and instance.pk:
            current_parent = instance
        
        # Check if email is being changed
        if self.user and email == self.user.email:
            # Email not changed - no need to validate
            return email
        
        # Email is being changed - check if it conflicts with another parent in the same school
        school = getattr(self, 'school', None)
        if not school and current_parent:
            school = current_parent.school
        
        if school:
            # Check if another parent in the same school has this email
            existing_parent = Parent.objects.filter(
                school=school,
                user__email=email
            ).exclude(pk=current_parent.pk if current_parent else None).first()
            
            if existing_parent:
                raise ValidationError('A parent with this email already exists in this school.')
            
            # Also check Parent.email field as fallback
            existing_parent_by_email = Parent.objects.filter(
                school=school,
                email=email
            ).exclude(pk=current_parent.pk if current_parent else None).exclude(user__email=email).first()
            
            if existing_parent_by_email:
                raise ValidationError('A parent with this email already exists in this school.')
        else:
            # No school context - check if any user (not just parent) has this email
            if self.user:
                if User.objects.filter(email=email).exclude(id=self.user.id).exists():
                    raise ValidationError('A user with this email already exists.')
            else:
                if User.objects.filter(email=email).exists():
                    raise ValidationError('A user with this email already exists.')
        
        return email
    
    def clean_students(self):
        """Clean and validate students field - handle empty strings and invalid values"""
        # First, check if we have raw data with empty strings
        if hasattr(self, 'data') and self.data:
            raw_students = self.data.getlist('students', [])
            # Filter out empty strings, None, and whitespace-only values
            raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
            
            # If no valid student IDs after filtering, return empty list
            if not raw_students:
                return []
        
        # Try to get cleaned data (this will validate the IDs if any were provided)
        if 'students' not in self.cleaned_data:
            # Check raw data again
            if hasattr(self, 'data') and self.data:
                raw_students = self.data.getlist('students', [])
                raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
                if not raw_students:
                    return []
                
                # Try to get students directly by ID
                school = getattr(self, 'school', None)
                if school:
                    try:
                        student_ids = []
                        for s in raw_students:
                            try:
                                sid = int(s)
                                student_ids.append(sid)
                            except (ValueError, TypeError):
                                continue
                        
                        if student_ids:
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=school,
                                is_active=True
                            )
                            if students.exists():
                                return list(students)
                    except Exception:
                        pass
                return []
        
        # If we have cleaned_data with students, use it
        try:
            if 'students' in self.cleaned_data:
                students = self.cleaned_data['students']
                # Filter out any invalid entries and ensure all are valid Student instances
                if students:
                    valid_students = []
                    for student in students:
                        if student and isinstance(student, Student):
                            valid_students.append(student)
                    if valid_students:
                        return valid_students
        except (ValidationError, ValueError, KeyError):
            # If validation fails, try raw data fallback
            pass
        
        # Fallback: Try to get from raw data if cleaned_data is empty or missing
        if hasattr(self, 'data') and self.data:
            raw_students = self.data.getlist('students', [])
            raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
            if raw_students:
                school = getattr(self, 'school', None)
                if not school and hasattr(self, 'data') and self.data:
                    school_id = self.data.get('school')
                    if school_id:
                        try:
                            school = School.objects.get(id=school_id)
                        except (School.DoesNotExist, ValueError):
                            pass
                
                if school:
                    try:
                        student_ids = []
                        for s in raw_students:
                            try:
                                sid = int(s)
                                student_ids.append(sid)
                            except (ValueError, TypeError):
                                continue
                        
                        if student_ids:
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=school,
                                is_active=True
                            )
                            if students.exists():
                                return list(students)
                    except Exception:
                        pass
        
        return []
    
    def save(self, commit=True):
        parent = super().save(commit=False)
        
        # Update user information
        if self.user:
            self.user.email = self.cleaned_data.get('email', self.user.email)
            self.user.first_name = self.cleaned_data.get('first_name', self.user.first_name)
            self.user.last_name = self.cleaned_data.get('last_name', self.user.last_name)
            if commit:
                self.user.save()
        
        # Update parent email if provided
        if 'email' in self.cleaned_data:
            parent.email = self.cleaned_data['email']
        
        # Handle is_active checkbox (if not checked, it won't be in POST data)
        if 'is_active' in self.cleaned_data:
            parent.is_active = self.cleaned_data['is_active']
        else:
            parent.is_active = False
        
        if commit:
            parent.save()
            
            # Update linked students - always check raw form data first (more reliable)
            students = []
            students_field_present = False  # Track if students field was in POST data
            
            # Check if we have form data (from POST request)
            # Try multiple sources: _post_data (from view), self.data (form's data), or cleaned_data
            post_data = None
            if hasattr(self, '_post_data') and self._post_data:
                post_data = self._post_data
            elif hasattr(self, 'data') and self.data is not None:
                post_data = self.data
            
            if post_data:
                try:
                    # Check if 'students' field was present in POST data
                    # For QueryDict, check if key exists (even if empty list)
                    if hasattr(post_data, 'getlist'):
                        # QueryDict: check if key exists
                        students_field_present = 'students' in post_data
                        raw_students = post_data.getlist('students', [])
                    else:
                        # Regular dict: check if key exists
                        students_field_present = 'students' in post_data
                        raw_students = post_data.get('students', [])
                        if not isinstance(raw_students, list):
                            raw_students = [raw_students] if raw_students else []
                    
                    # Filter out empty strings, None, and whitespace-only values
                    raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
                    
                    # If field was present but all values were empty/whitespace, user explicitly cleared all students
                    if students_field_present and len(raw_students) == 0:
                        # Field was in POST but empty - user explicitly cleared all links
                        students = []
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f'Students field was in POST but empty - clearing all links for parent {parent.id}')
                    elif raw_students:
                        # Get school from instance or form
                        school = getattr(self, 'school', None)
                        if not school and hasattr(parent, 'school'):
                            school = parent.school
                        
                        if school:
                            try:
                                # Convert to integers and filter
                                student_ids = []
                                for sid in raw_students:
                                    try:
                                        student_id = int(sid)
                                        student_ids.append(student_id)
                                    except (ValueError, TypeError):
                                        continue
                                
                                if student_ids:
                                    # Fetch students from database
                                    fetched_students = Student.objects.filter(
                                        id__in=student_ids,
                                        school=school,
                                        is_active=True
                                    )
                                    if fetched_students.exists():
                                        students = list(fetched_students)
                                        # Log for debugging
                                        import logging
                                        logger = logging.getLogger(__name__)
                                        logger.info(f'Linking {len(students)} students to parent {parent.id}')
                            except Exception as e:
                                # Log error but don't fail the save
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.error(f'Error linking students to parent: {e}')
                except (AttributeError, KeyError) as e:
                    # If getlist fails, try alternative method
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Could not get students from form data: {e}')
            
            # Fallback to cleaned_data if raw data didn't work
            if not students and students_field_present:
                students = self.cleaned_data.get('students', [])
                if students:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f'Using cleaned_data: {len(students)} students for parent {parent.id}')
            
            # Set the students based on POST data
            # If students field was in POST, use it (even if empty - user explicitly cleared all links)
            # If students field was NOT in POST, preserve existing links (user didn't touch the field)
            if students_field_present:
                # Field was in POST - update with what was submitted (even if empty list means clear all links)
                parent.children.set(students)
                # Log the result
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f'Updated students for parent {parent.id}: Set {len(students)} students (field was in POST). Previous count: {parent.children.count()}')
            else:
                # Students field not in POST - this means user didn't interact with the field
                # Preserve existing links (don't call set() at all)
                import logging
                logger = logging.getLogger(__name__)
                existing_count = parent.children.count()
                logger.info(f'Students field not in POST data - preserving existing {existing_count} links for parent {parent.id}')
            
            # Log final state for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'Parent {parent.id} now has {parent.children.count()} linked students')
        
        return parent
