from django import forms
from .models import Training, ShiftRequest, TimeOffRequest, Availability

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
        fields = ['day_of_week', 'start_time', 'end_time', 'is_available']
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input form-check-input-lg', 'role': 'switch'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time.")
        
        return cleaned_data