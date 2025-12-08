from django import forms
from django.contrib.auth.models import User
from .models import Training, ShiftRequest, TimeOffRequest, Availability, WorkspaceReservation, Certificate, Issue

class TrainingSessionForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['title', 'date', 'start_time', 'end_time', 'capacity']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class ShiftRequestForm(forms.ModelForm):
    class Meta:
        model = ShiftRequest
        fields = ['request_type', 'notes', 'swap_with_training']
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional: Reason for request'}),
            'swap_with_training': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        training = kwargs.pop('training', None)
        super().__init__(*args, **kwargs)
        
        # Only show user's own future trainings as swap options
        if user and training:
            from django.utils import timezone
            self.fields['swap_with_training'].queryset = Training.objects.filter(
                instructor=user,
                date__gte=timezone.localdate()
            ).exclude(id=training.id).order_by('date', 'start_time')
        
        self.fields['swap_with_training'].required = False
        self.fields['swap_with_training'].empty_label = "None (just need coverage)"
        self.fields['notes'].required = False


class TimeOffRequestForm(forms.ModelForm):
    class Meta:
        model = TimeOffRequest
        fields = ['start_date', 'end_date', 'start_time', 'end_time', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional: Reason for time off'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date must be on or after start date.")
        
        if start_time and end_time and start_date == end_date and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time for same-day requests.")
        
        return cleaned_data


class AvailabilityForm(forms.ModelForm):
    class Meta:
        model = Availability
        fields = ['day_of_week', 'specific_date', 'start_time', 'end_time', 'is_available']
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'specific_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'form-check-input form-check-input-lg',
                'role': 'switch'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        day_of_week = cleaned_data.get('day_of_week')
        specific_date = cleaned_data.get('specific_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        # Must choose either recurring or single date
        if not day_of_week and not specific_date:
            raise forms.ValidationError(
                "You must select either a day of the week or a specific date."
            )

        if day_of_week and specific_date:
            raise forms.ValidationError(
                "You cannot select both a day of the week and a specific date."
            )

        # Time validation
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time.")

        return cleaned_data


class WorkspaceReservationForm(forms.ModelForm):
    class Meta:
        model = WorkspaceReservation
        fields = ['workspace', 'date', 'start_time', 'end_time', 'purpose', 'estimated_participants']
        widgets = {
            'workspace': forms.Select(attrs={'class': 'form-select', 'id': 'workspace'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control', 'id': 'start_time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control', 'id': 'end_time'}),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe the course, project, or event...', 'id': 'purpose'}),
            'estimated_participants': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 30, 'placeholder': 'e.g., 10', 'id': 'participants'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        # Validate end_time > start_time
        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError("End time must be after start time.")
        
        # Validate date >= today when creating (only if this is a new instance)
        if not self.instance.pk and date:
            from django.utils import timezone
            if date < timezone.localdate():
                raise forms.ValidationError("Reservation date cannot be in the past.")
        
        return cleaned_data


class CertificateUploadForm(forms.ModelForm):
    """Form to create certificates for users who completed training sessions."""
    
    notify_user = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send notification to learner"
    )
    
    class Meta:
        model = Certificate
        fields = ['user', 'training', 'issued_on', 'expires_on', 'notes']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select learner'}),
            'training': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select training session'}),
            'issued_on': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expires_on': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes for the learner or internal team'}),
        }
        labels = {
            'user': 'Learner',
            'training': 'Training Session',
            'issued_on': 'Issued On',
            'expires_on': 'Expires On (optional)',
            'notes': 'Notes',
        }

    def __init__(self, *args, trainings=None, learners=None, **kwargs):
        super().__init__(*args, **kwargs)
        trainings = trainings if trainings is not None else Training.objects.none()
        learners = learners if learners is not None else User.objects.none()
        self.fields['training'].queryset = trainings
        self.fields['user'].queryset = learners
        self.fields['expires_on'].required = False
        self.fields['notes'].required = False


class ReportIssueForm(forms.ModelForm):
    """Form for users to report issues."""
    
    class Meta:
        model = Issue
        fields = ['title', 'description', 'urgency']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief summary of the issue'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Please provide detailed information about the issue...'
            }),
            'urgency': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'title': 'Issue Title',
            'description': 'Description',
            'urgency': 'Urgency Level',
        }


class CertificateEditForm(forms.ModelForm):
    """Form for staff/admin to edit issued certificates."""

    class Meta:
        model = Certificate
        fields = ['issued_on', 'expires_on', 'status', 'notes']
        widgets = {
            'issued_on': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expires_on': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes for the learner or internal team'}),
        }
        labels = {
            'issued_on': 'Issued On',
            'expires_on': 'Expires On (optional)',
            'status': 'Status',
            'notes': 'Notes',
        }


class ResolveIssueForm(forms.Form):
    """Form for admin/staff to resolve or dismiss issues."""
    
    action = forms.ChoiceField(
        choices=[('resolved', 'Resolved'), ('dismissed', 'Dismissed')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Action'
    )
    resolution_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Optional message to the user who reported this issue...'
        }),
        label='Message to User (Optional)'
    )


class FlagIssueForm(forms.Form):
    """Form for admin/staff to flag an issue to a specific admin/staff member."""
    
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Assign To',
        empty_label='Select a staff/admin member...'
    )
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        # Get all staff and admin users except the current user
        from apps.profiles.models import UserProfile
        staff_admin_profiles = UserProfile.objects.filter(
            role__in=['staff', 'admin']
        ).exclude(user=current_user).select_related('user')
        users_queryset = User.objects.filter(
            id__in=[p.user.id for p in staff_admin_profiles]
        ).order_by('first_name', 'last_name', 'username')
        
        # Customize the label to show name and email
        class CustomModelChoiceField(forms.ModelChoiceField):
            def label_from_instance(self, obj):
                name = obj.get_full_name() or obj.username
                return f"{name} ({obj.email})"
        
        # Replace the field with a custom one
        self.fields['assigned_to'] = CustomModelChoiceField(
            queryset=users_queryset,
            widget=forms.Select(attrs={'class': 'form-select'}),
            label='Assign To',
            empty_label='Select a staff/admin member...'
        )
