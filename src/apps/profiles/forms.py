from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Profile, UserProfile

class ProfileEditForm(forms.ModelForm):
    """Form for editing user profile information."""
    
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Profile
        fields = ['school', 'department', 'bio', 'birth_date', 'avatar', 'phone_number', 'website', 
                  'major_1', 'major_2', 'minor_1', 'minor_2', 'graduation_year']
        widgets = {
            'school': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Boston College'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your department'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'form-control', 'placeholder': 'Tell us about yourself...'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., (555) 123-4567'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
            'major_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your primary major'}),
            'major_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your secondary major (optional)'}),
            'minor_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your primary minor (optional)'}),
            'minor_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your secondary minor (optional)'}),
            'graduation_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2025', 'min': timezone.now().year}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make required fields
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['school'].required = True
        self.fields['department'].required = True
        
        # Add CSS classes to all fields
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
        
        if self.user:
            # Pre-populate user fields
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
            
            # Set default school if not set
            if not self.instance.pk or not self.instance.school:
                self.fields['school'].initial = 'Boston College'
            
            # Make graduation year required only for students
            user_profile = getattr(self.user, 'userprofile', None)
            if user_profile and user_profile.role != 'student':
                self.fields['graduation_year'].required = False
                self.fields['major_1'].required = False
                self.fields['major_2'].required = False
                self.fields['minor_1'].required = False
                self.fields['minor_2'].required = False
            else:
                # For students, graduation year should be at least this year
                self.fields['graduation_year'].widget.attrs['min'] = timezone.now().year
    
    def clean_department(self):
        """Validate department is provided."""
        department = self.cleaned_data.get('department')
        if not department or not department.strip():
            raise forms.ValidationError("Department is required.")
        return department
    
    def clean_graduation_year(self):
        """Validate graduation year is at least this year for students."""
        graduation_year = self.cleaned_data.get('graduation_year')
        if graduation_year:
            current_year = timezone.now().year
            if graduation_year < current_year:
                raise forms.ValidationError(f"Graduation year must be at least {current_year}.")
        return graduation_year
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        if commit and self.user:
            # Update user fields
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
            
            profile.save()
        
        return profile

class AdminRoleForm(forms.ModelForm):
    """Form for admin to change user roles."""
    
    class Meta:
        model = UserProfile
        fields = ['role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].label = 'User Role'

class AdminUserSearchForm(forms.Form):
    """Form for searching users in admin interface."""
    
    search_query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by username, email, or name...'
        })
    )
    role_filter = forms.ChoiceField(
        choices=[('', 'All Roles')] + UserProfile.ROLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
