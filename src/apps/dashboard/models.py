import logging
from datetime import datetime, timedelta

from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.models import User
from django.conf import settings
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


class WorkspaceReservation(models.Model):
    """Workspace reservation requests from collaborators."""
    WORKSPACE_CHOICES = [
        ('hatch_front', 'Hatch Front'),
        ('hatch_back', 'Hatch Back'),
        ('prototyping_studio', 'Prototyping Studio'),
        ('prototyping_shop', 'Prototyping Shop'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_reservations')
    workspace = models.CharField(max_length=50, choices=WORKSPACE_CHOICES)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.TextField()
    estimated_participants = models.PositiveIntegerField(null=True, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspace_reservations_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        workspace_display = dict(self.WORKSPACE_CHOICES).get(self.workspace, self.workspace)
        return f"{self.user.username} - {workspace_display} on {self.date} ({self.status})"
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        return self.status == 'rejected'
    
    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        # Validate end_time > start_time
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")
        
        # Validate date >= today when creating (only if this is a new instance)
        if not self.pk and self.date and self.date < timezone.localdate():
            raise ValidationError("Reservation date cannot be in the past.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Availability(models.Model):
    """Supports both recurring weekly and one-time availability for staff members."""
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

    # For recurring weekly patterns
    day_of_week = models.IntegerField(choices=DAY_CHOICES, null=True, blank=True)

    # For one-time availability
    specific_date = models.DateField(null=True, blank=True)

    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Availabilities'
        unique_together = ['user', 'day_of_week', 'specific_date', 'start_time', 'end_time']
        ordering = ['day_of_week', 'specific_date', 'start_time']

    def __str__(self):
        if self.specific_date:
            label = self.specific_date.strftime("%b %d, %Y")
        else:
            label = dict(self.DAY_CHOICES).get(self.day_of_week, "Unknown Day")
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.user.username} - {label} {self.start_time}-{self.end_time} ({status})"


class Certificate(models.Model):
    """Certificates issued to users for completing training sessions."""
    STATUS_CHOICES = [
        ('pending', 'Pending email'),
        ('sent', 'Sent'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='certificates')
    certificate_id = models.CharField(max_length=100, blank=True, null=True)
    issued_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    certificate_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    evidence_link = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificates_issued'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issued_on', '-created_at']
        unique_together = ['user', 'training']  # One certificate per user per training
    
    def __str__(self):
        return f"{self.user.username} - {self.training.title} ({self.issued_on})"
    
    @property
    def is_expired(self):
        if not self.expires_on:
            return False
        from django.utils import timezone
        return self.expires_on < timezone.localdate()


class Issue(models.Model):
    """Issue reports submitted by users."""
    URGENCY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    # Issue details
    title = models.CharField(max_length=200)
    description = models.TextField()
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='medium')
    
    # User information (auto-captured)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_issues')
    user_name = models.CharField(max_length=200)  # Stored name at time of submission
    user_email = models.EmailField()
    user_phone = models.CharField(max_length=15, blank=True)  # Optional
    
    # Status and resolution
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    # Assignment (for flagging to specific admin/staff)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_issues'
    )
    
    # Resolution details
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_issues'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.status})"
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_resolved(self):
        return self.status == 'resolved'
    
    @property
    def is_dismissed(self):
        return self.status == 'dismissed'
    
    @property
    def urgency_priority(self):
        """Return numeric priority for sorting (higher = more urgent)"""
        priority_map = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1,
        }
        return priority_map.get(self.urgency, 0)


def create_google_calendar_event(user, training, *, save_event_id=True):
    """Attempt to sync the session to the user's Google Calendar."""

    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        token = SocialToken.objects.get(account=social_account)
    except (SocialAccount.DoesNotExist, SocialToken.DoesNotExist):
        logger.info("Skipping Google Calendar sync for %s; no OAuth token.", user)
        return None

    try:
        # Get OAuth client credentials from settings
        client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None)
        client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', None)
        
        creds = Credentials(
            token.token,
            refresh_token=token.token_secret,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
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

    # Only save event ID if this user is the instructor (to avoid overwriting with participant event IDs)
    if save_event_id and created_event and created_event.get('id'):
        # Only save event ID for instructors, not participants
        if training.instructor == user:
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
        # Get OAuth client credentials from settings
        client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None)
        client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', None)
        
        creds = Credentials(
            token.token,
            refresh_token=token.token_secret,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build("calendar", "v3", credentials=creds)

        # Try to delete using stored event ID if available
        # Note: We don't check if user is the instructor because after swaps, the instructor may have changed
        deleted = False
        if training.google_event_id:
            try:
                service.events().delete(
                    calendarId=training.google_calendar_id or 'primary',
                    eventId=training.google_event_id
                ).execute()
                deleted = True
                logger.info("Deleted Google Calendar event %s for %s", training.google_event_id, user)
            except HttpError as e:
                if e.resp.status == 410:
                    logger.info("Google event already deleted for %s.", user)
                    deleted = True
                elif e.resp.status == 404:
                    logger.info("Google event not found (may have been deleted manually or wrong calendar) for %s. Will try search.", user)
                    # Don't mark as deleted, try search instead
                else:
                    logger.warning("Failed to delete event by ID for %s: %s. Will try search.", user, e)
        
        # If deletion by ID failed or ID not available, try to find and delete by title/date
        if not deleted:
            try:
                # Search for events matching the training title and date
                start_dt = datetime.combine(training.date, training.start_time)
                end_dt = datetime.combine(training.date, training.end_time)
                
                # Search in a wider window around the event time
                time_min = (start_dt - timedelta(hours=2)).isoformat() + 'Z'
                time_max = (end_dt + timedelta(hours=2)).isoformat() + 'Z'
                
                # First try searching by title
                events_result = service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    q=training.title,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                
                # If no results with title search, try without query (broader search)
                if not events:
                    events_result = service.events().list(
                        calendarId='primary',
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    events = events_result.get('items', [])
                
                for event in events:
                    # Check if this event matches our training by time
                    event_start = event['start'].get('dateTime', event['start'].get('date'))
                    if event_start:
                        # Parse the datetime - handle timezone-aware and naive datetimes
                        try:
                            if 'T' in event_start:
                                # Remove timezone info for comparison
                                event_dt_str = event_start.split('+')[0].split('-')[0:3]
                                if len(event_dt_str) >= 2:
                                    event_dt_str = '-'.join(event_dt_str[:3]) + 'T' + event_start.split('T')[1].split('+')[0].split('-')[0]
                                event_dt = datetime.fromisoformat(event_dt_str.replace('Z', ''))
                            else:
                                event_dt = datetime.fromisoformat(event_start)
                        except:
                            continue
                        
                        # Check if time matches (within 30 minutes)
                        time_diff = abs((event_dt - start_dt).total_seconds())
                        if time_diff < 1800:  # Within 30 minutes
                            service.events().delete(
                                calendarId='primary',
                                eventId=event['id']
                            ).execute()
                            logger.info("Deleted Google Calendar event by search for %s (event: %s)", user, event.get('summary', 'Unknown'))
                            deleted = True
                            break
            except Exception as e:
                logger.warning("Failed to search/delete event for %s: %s", user, e)
        
        # Clear stored event ID if we successfully deleted
        # Note: We clear it regardless of current instructor because the event is gone from this user's calendar
        if deleted and training.google_event_id:
            # Only clear if this user was the original instructor (to avoid clearing for participants)
            # But actually, we should clear it if we successfully deleted it
            training.google_event_id = None
            training.save(update_fields=['google_event_id'])

    except Exception as exc:
        logger.warning("Failed to sync Google Calendar for %s: %s", user, exc)
        return None