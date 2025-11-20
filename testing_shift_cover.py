#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.dashboard.models import Training, ShiftRequest
from apps.dashboard.models import remove_google_calendar_event, create_google_calendar_event
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

User = get_user_model()

# Get the current user (david)
username = 'david'
user = User.objects.filter(username=username).first()

if not user:
    print(f"User '{username}' not found.")
    sys.exit(1)

# Find a shift by another instructor (future shift, not already covered by user)
today = timezone.localdate()
other_shifts = Training.objects.filter(
    date__gte=today
).exclude(instructor=user).select_related('instructor').order_by('date', 'start_time')[:10]

if not other_shifts:
    print("No shifts found by other instructors.")
    sys.exit(1)

# Pick a shift that doesn't already have a pending cover request from this user
shift_to_cover = None
for shift in other_shifts:
    existing = ShiftRequest.objects.filter(
        training=shift,
        request_type='cover',
        status='pending',
        offered_by=user
    ).first()
    if not existing:
        shift_to_cover = shift
        break

if not shift_to_cover:
    print("All available shifts already have pending cover requests from you.")
    # Use the first one anyway
    shift_to_cover = other_shifts[0]

print(f"✓ Found shift: {shift_to_cover.title} on {shift_to_cover.date} by {shift_to_cover.instructor.get_full_name() or shift_to_cover.instructor.username}")

# Create a cover request and offer
cover_request = ShiftRequest.objects.create(
    training=shift_to_cover,
    requested_by=shift_to_cover.instructor,
    request_type='cover',
    offered_by=user,
    status='pending',
    notes=f"Test cover offer by {user.get_full_name() or user.username}"
)
print(f"✓ Created cover request (ID: {cover_request.id})")

print(f"\n📋 Cover Request Details:")
print(f"  Shift: {cover_request.training.title}")
print(f"  Date: {cover_request.training.date}")
print(f"  Time: {cover_request.training.start_time} - {cover_request.training.end_time}")
print(f"  Original Instructor: {cover_request.training.instructor.get_full_name() or cover_request.training.instructor.username}")
print(f"  Offered by: {cover_request.offered_by.get_full_name() or cover_request.offered_by.username} (you)")
print(f"  Status: {cover_request.status}")

# Now approve it directly (simulating the approval process)
print(f"\n✅ Approving cover request...")

try:
    # Store original instructor before transaction
    old_instructor = cover_request.training.instructor
    new_instructor = cover_request.offered_by  # This is the user (david)
    
    # Remove old calendar event BEFORE transaction
    print(f"  Removing event from {old_instructor.get_full_name() or old_instructor.username}'s calendar...")
    remove_google_calendar_event(old_instructor, cover_request.training)
    
    # Update database inside transaction
    with transaction.atomic():
        cover_request.status = 'approved'
        cover_request.approved_by = old_instructor  # The original instructor approves
        cover_request.approved_at = timezone.now()
        cover_request.save()
        
        # Transfer the shift
        cover_request.training.instructor = new_instructor
        # Clear the old event ID since we're creating a new event in a different calendar
        cover_request.training.google_event_id = None
        cover_request.training.save()
    
    # Refresh training object
    cover_request.training.refresh_from_db()
    
    # Create new calendar event AFTER transaction
    print(f"  Creating event in {new_instructor.get_full_name() or new_instructor.username}'s calendar...")
    create_google_calendar_event(new_instructor, cover_request.training)
    
    print(f"✓ Cover request approved!")
    print(f"\n📋 Updated Shift Details:")
    print(f"  Shift: {cover_request.training.title}")
    print(f"  Date: {cover_request.training.date}")
    print(f"  Time: {cover_request.training.start_time} - {cover_request.training.end_time}")
    print(f"  New Instructor: {cover_request.training.instructor.get_full_name() or cover_request.training.instructor.username} (you!)")
    print(f"  Request Status: {cover_request.status}")
    
    # Check if event ID was saved
    cover_request.training.refresh_from_db()
    if cover_request.training.google_event_id:
        print(f"  Google Event ID: {cover_request.training.google_event_id}")
        print(f"  ✓ Event ID saved to database")
    else:
        print(f"  ⚠ Google Event ID not saved (check logs)")
    
    print(f"\n📅 Check your Google Calendar - the event should now be in your calendar!")
    print(f"   The event should have been removed from {old_instructor.get_full_name() or old_instructor.username}'s calendar.")
    
except Exception as e:
    print(f"❌ Error approving cover request: {e}")
    import traceback
    traceback.print_exc()

