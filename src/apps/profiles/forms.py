from django import forms
from django.contrib.auth.models import User
from .models import Profile, UserProfile

class ProfileEditForm(forms.ModelForm):
    """Form for editing user profile information."""
    
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Profile
        fields = ['bio', 'location', 'birth_date', 'avatar', 'phone_number', 'website', 
                  'major_1', 'major_2', 'minor_1', 'minor_2']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'cols': 40}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'major_1': forms.TextInput(attrs={'placeholder': 'Enter your primary major'}),
            'major_2': forms.TextInput(attrs={'placeholder': 'Enter your secondary major (optional)'}),
            'minor_1': forms.TextInput(attrs={'placeholder': 'Enter your primary minor'}),
            'minor_2': forms.TextInput(attrs={'placeholder': 'Enter your secondary minor (optional)'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Pre-populate user fields
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
    
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
