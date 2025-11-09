from django import forms
from .models import Training

class TrainingSessionForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['title', 'date', 'start_time', 'end_time', 'capacity']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }