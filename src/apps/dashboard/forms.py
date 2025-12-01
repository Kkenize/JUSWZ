from django import forms
from django.contrib.auth.models import User
from .models import Training, ShiftRequest, TimeOffRequest, Availability, WorkspaceReservation

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


class CertificateUploadForm(forms.Form):
    """Simple form to capture certificate metadata; backend persistence to be wired later."""

    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select learner'}),
        label="Student/Collaborator"
    )
    training = forms.ModelChoiceField(
        queryset=Training.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'placeholder': 'Select training session'}),
        label="Training Session"
    )
    certificate_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., CERT-2024-0198'}),
        label="Certificate ID (optional)"
    )
    issued_on = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Issued On"
    )
    expires_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Expires On (optional)"
    )
    certificate_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        label="Certificate File (PDF/image)"
    )
    evidence_link = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Link to evidence or portfolio'}),
        label="Evidence URL (optional)"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes for the learner or internal team'}),
        label="Notes"
    )
    notify_user = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send notification to learner"
    )

    def __init__(self, *args, trainings=None, learners=None, **kwargs):
        super().__init__(*args, **kwargs)
        trainings = trainings if trainings is not None else Training.objects.none()
        learners = learners if learners is not None else User.objects.none()
        self.fields['training'].queryset = trainings
        self.fields['user'].queryset = learners
