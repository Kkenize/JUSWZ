import logging
from datetime import datetime

from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.models import User
from django.db import models
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


logger = logging.getLogger(__name__)

class Training(models.Model):
    title = models.CharField(max_length=100)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField()
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_sessions')
    participants = models.ManyToManyField(User, related_name='enrolled_trainings', blank=True)
    google_event_id = models.CharField(max_length=256, blank=True, null=True)
    google_calendar_id = models.CharField(max_length=256, blank=True, null=True)

    @property
    def is_full(self):
        return self.participants.count() >= self.capacity

    def __str__(self):
        return f"{self.title} - {self.date} ({self.instructor.username})"


class ShiftRequest(models.Model):
    """Handles both cover requests and swap requests for shifts."""
    REQUEST_TYPE_CHOICES = [
        ('cover', 'Cover Request'),
        ('swap', 'Swap Request'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    # The shift being requested
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='shift_requests')
    
    # Who made the request
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shift_requests_made')
    
    # Type of request
    request_type = models.CharField(max_length=10, choices=REQUEST_TYPE_CHOICES)
    
    # For swap requests: which shift to swap with
    swap_with_training = models.ForeignKey(
        Training, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='swap_requests_for'
    )
    
    # For cover requests: who offered to cover (set when someone offers)
    offered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cover_offers_made'
    )
    
    # Status tracking
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    # Additional info
    notes = models.TextField(blank=True)
    
    # Approval tracking
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shift_requests_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_type} for {self.training.title} by {self.requested_by.username} ({self.status})"
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        return self.status == 'approved'


class TimeOffRequest(models.Model):
    """Time-off requests from staff members."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_off_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)  # Optional: for partial days
    end_time = models.TimeField(null=True, blank=True)    # Optional: for partial days
    reason = models.TextField(blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='time_off_requests_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.start_date} to {self.end_date} ({self.status})"
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        return self.status == 'rejected'


class Availability(models.Model):
    """Recurring weekly availability patterns for staff members."""
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availability_patterns')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Availabilities'
        unique_together = ['user', 'day_of_week', 'start_time', 'end_time']
        ordering = ['day_of_week', 'start_time']
    
    def __str__(self):
        day_name = dict(self.DAY_CHOICES)[self.day_of_week]
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.user.username} - {day_name} {self.start_time}-{self.end_time} ({status})"


def create_google_calendar_event(user, training, *, save_event_id=True):
    """Attempt to sync the session to the user's Google Calendar."""

    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        token = SocialToken.objects.get(account=social_account)
    except (SocialAccount.DoesNotExist, SocialToken.DoesNotExist):
        logger.info("Skipping Google Calendar sync for %s; no OAuth token.", user)
        return None

    try:
        creds = Credentials(
            token.token,
            refresh_token=token.token_secret,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=None,
            client_secret=None,
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build("calendar", "v3", credentials=creds)

        start_dt = datetime.combine(training.date, training.start_time).isoformat()
        end_dt = datetime.combine(training.date, training.end_time).isoformat()

        event = {
            "summary": training.title,
            "description": "Training session",
            "start": {"dateTime": start_dt, "timeZone": "America/New_York"},
            "end": {"dateTime": end_dt, "timeZone": "America/New_York"},
        }
        training.google_calendar_id = 'primary'
        created_event = service.events().insert(calendarId=training.google_calendar_id, body=event).execute()

    except HttpError as exc:
        logger.warning("Google Calendar API error for %s: %s", user, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to sync Google Calendar for %s: %s", user, exc)
        return None

    if save_event_id and created_event and created_event.get('id'):
        training.google_event_id = created_event['id']
        training.save(update_fields=['google_event_id', 'google_calendar_id'])

    logger.info("Synced training %s to Google Calendar for %s", training.id, user)
    return created_event


def remove_google_calendar_event(user, training):
    """Remove the training session from the user's Google Calendar."""
    
    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        token = SocialToken.objects.get(account=social_account)
    except (SocialAccount.DoesNotExist, SocialToken.DoesNotExist):
        logger.info("Skipping Google Calendar sync for %s; no OAuth token.", user)
        return None
    
    try:
        creds = Credentials(
            token.token,
            refresh_token=token.token_secret,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=None,
            client_secret=None,
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build("calendar", "v3", credentials=creds)

        if training.google_event_id:
            try:
                service.events().delete(calendarId=training.google_calendar_id,eventId=training.google_event_id).execute()

            except HttpError as e:
                if e.resp.status == 410:
                    logger.info("Google event already deleted for %s.", user)
                else:
                    raise

            # Always clear ID because the event is definitely gone now
            training.google_event_id = None
            training.save(update_fields=['google_event_id'])
            logger.info("Synced deletion for %s.", user)

    except Exception as exc:
        logger.warning("Failed to sync Google Calendar for %s: %s", user, exc)
        return None