from django.db import models
from django.contrib.auth.models import User
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from allauth.socialaccount.models import SocialToken
from datetime import datetime
from allauth.socialaccount.models import SocialAccount

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

def create_google_calendar_event(user, training):
    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        token = SocialToken.objects.get(account=social_account)
    except (SocialAccount.DoesNotExist, SocialToken.DoesNotExist):
        print("No Google token found for user.")
        return None

    creds = Credentials(
        token.token,
        refresh_token=token.token_secret,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=None,  # not required for this flow
        client_secret=None,
    )

    # Refresh expired tokens automatically
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("calendar", "v3", credentials=creds)

    start_dt = datetime.combine(training.date, training.start_time).isoformat()
    end_dt = datetime.combine(training.date, training.end_time).isoformat()

    event = {
        "summary": training.title,
        "description": f"Training session",
        "start": {"dateTime": start_dt, "timeZone": "America/New_York"},
        "end": {"dateTime": end_dt, "timeZone": "America/New_York"},
    }

    created_event = service.events().insert(calendarId="primary", body=event).execute()
    training.google_event_id = created_event['id']
    training.save(update_fields=['google_event_id'])
    print(f"Event created: {created_event.get('htmlLink')}")
    return created_event
