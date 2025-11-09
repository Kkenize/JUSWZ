from django.db import models
from django.contrib.auth.models import User

class Training(models.Model):
    title = models.CharField(max_length=100)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField()
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_sessions')
    participants = models.ManyToManyField(User, related_name='enrolled_trainings', blank=True)

    @property
    def is_full(self):
        return self.participants.count() >= self.capacity
