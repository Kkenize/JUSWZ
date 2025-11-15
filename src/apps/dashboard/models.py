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

    @property
    def is_full(self):
        return self.participants.count() >= self.capacity

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

        created_event = service.events().insert(calendarId="primary", body=event).execute()
    except HttpError as exc:
        logger.warning("Google Calendar API error for %s: %s", user, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to sync Google Calendar for %s: %s", user, exc)
        return None

    if save_event_id and created_event and created_event.get('id'):
        training.google_event_id = created_event['id']
        training.save(update_fields=['google_event_id'])

    logger.info("Synced training %s to Google Calendar for %s", training.id, user)
    return created_event
