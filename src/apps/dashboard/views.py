import json
from datetime import datetime, time as time_cls, timedelta

from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.forms import modelformset_factory
from django import forms
from django.utils import timezone
from django.db.models import Count, Case, When, IntegerField, Q
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme
from apps.profiles.models import UserProfile
from django.http import HttpResponseForbidden, JsonResponse
from .models import Training, ShiftRequest, TimeOffRequest, Availability, WorkspaceReservation, create_google_calendar_event, remove_google_calendar_event
from .forms import TrainingSessionForm, ShiftRequestForm, TimeOffRequestForm, AvailabilityForm, WorkspaceReservationForm, CertificateUploadForm
from .prerequisites import TRAINING_SECTIONS, get_training_metadata, serialize_prereq_map


@never_cache
def landing_page(request):
    """Public landing page for non-logged-in users"""
    return render(request, 'dashboard/landing.html')


@never_cache
@login_required
def dashboard_redirect(request):
    """Redirects user to their specific dashboard based on their role."""
    user_profile = request.user.userprofile

    if user_profile.role == 'admin':
        return redirect('dashboard:admin')
    elif user_profile.role == 'staff':
        return redirect('dashboard:staff')
    elif user_profile.role == 'collaborator':
        return redirect('dashboard:collaborator')
    else:
        return redirect('dashboard:student')


# ---------- ROLE-PROTECTED DASHBOARDS ----------

@never_cache
@login_required
def student_dashboard(request):
    """Student-only dashboard"""
    user_profile = request.user.userprofile
    return render(request, 'dashboard/student_dashboard.html', {
        "user_profile": user_profile,
        "reserved_trainings_count": request.user.enrolled_trainings.filter(date__gte=timezone.localdate()).count(),
    })
    
@never_cache
@login_required
def collaborator_dashboard(request):
    """Collaborator-only dashboard"""
    user_profile = request.user.userprofile
    if user_profile.role != 'collaborator':
        return HttpResponseForbidden("You do not have permission to access this page.")
    return render(request, 'dashboard/collaborator_dashboard.html', {
        "user_profile": user_profile
    })

@never_cache
@login_required
def staff_dashboard(request):
    """Staff-only dashboard"""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")

    pending_workspace_requests = WorkspaceReservation.objects.filter(status='pending').count()
    certificate_backlog = Training.objects.filter(date__lte=timezone.localdate()).count()

    return render(request, 'dashboard/staff_dashboard.html', {
        "user_profile": user_profile,
        "pending_workspace_requests": pending_workspace_requests,
        "certificate_backlog": certificate_backlog,
    })


@never_cache
@login_required
def admin_dashboard(request):
    """Admin-only dashboard"""
    user_profile = request.user.userprofile
    if user_profile.role != 'admin':
        return HttpResponseForbidden("You do not have permission to access this page.")
    return render(request, 'dashboard/admin_dashboard.html', {
        "user_profile": user_profile
    })

@never_cache
@login_required
def training_management(request):
    """Accessible by both staff and admin"""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")
    trainings = [
    {"name": "3D Printing Training"},
    {"name": "Textile Training"},
    {"name": "Laser Training"},
    {"name": "Vinyl Training"},
    {"name": "2D Printing Training"},
    {"name": "Woodworking Training"},
    {"name": "Electronics Training"},
    {"name": "Metalworking Training"},
    ]
    return render(request, "training/training_management.html", {
        "user_profile": user_profile,
        "trainings": trainings
    })

@never_cache
@login_required
def training_list(request):
    """Flat list of all scheduled trainings for bulk actions."""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    trainings = Training.objects.all().order_by('date', 'start_time')
    serialized = [
        {
            "id": t.id,
            "title": t.title,
            "date": t.date,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "capacity": t.capacity,
        }
        for t in trainings
    ]
    return render(request, "training/training_list.html", {
        "user_profile": user_profile,
        "page_title": "All Trainings",
        "trainings": serialized,
    })

@never_cache
@login_required
def training_past(request):
    """Analytics view for past trainings hosted/attended by the user."""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    filter_mode = request.GET.get('filter', 'hosted').lower()
    sort_mode = request.GET.get('sort', 'recent').lower()
    today = timezone.localdate()

    base_qs = Training.objects.filter(date__lte=today).select_related('instructor').prefetch_related('participants').annotate(participant_total=Count('participants', distinct=True))

    can_view_all = user_profile.role == 'admin'
    if filter_mode == 'all' and can_view_all:
        qs = base_qs
    else:
        filter_mode = 'hosted'
        qs = base_qs.filter(instructor=request.user)

    if sort_mode == 'title':
        qs = qs.order_by('title', '-date', '-start_time')
    elif sort_mode == 'attendance':
        qs = qs.order_by('-participant_total', '-date')
    else:
        sort_mode = 'recent'
        qs = qs.order_by('-date', '-start_time')

    trainings_data = []
    total_attendance = 0
    total_capacity = 0
    total_completed = 0

    for training in qs:
        participants_count = getattr(training, 'participant_total', training.participants.count())
        total_attendance += participants_count
        total_capacity += training.capacity
        total_completed += participants_count
        trainings_data.append({
            "obj": training,
            "attendance_summary": f"{participants_count} attended / {training.capacity} registered",
            "participants": participants_count,
            "completion_summary": f"{participants_count} certified",
            "no_shows": max(training.capacity - participants_count, 0),
            "has_feedback": participants_count > 0,
        })

    attendance_rate = (total_attendance / total_capacity * 100) if total_capacity else 0
    completion_rate = (total_completed / total_capacity * 100) if total_capacity else 0

    stats = {
        "total_sessions": len(trainings_data),
        "total_attendance": total_attendance,
        "attendance_rate": round(attendance_rate, 1),
        "completion_rate": round(completion_rate, 1),
    }

    return render(request, "training/training_past.html", {
        "user_profile": user_profile,
        "page_title": "My Past Trainings",
        "trainings": trainings_data,
        "filter_mode": filter_mode,
        "sort_mode": sort_mode,
        "stats": stats,
    })


@never_cache
@login_required
def training_certificates(request):
    """Staff view: add certificates for learner trainings and review recent awards."""

    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    trainings = Training.objects.order_by('-date', 'title')
    learners = User.objects.filter(userprofile__role__in=['student', 'collaborator']).order_by(
        'first_name', 'last_name', 'username'
    )
    form = CertificateUploadForm(
        request.POST or None,
        request.FILES or None,
        trainings=trainings,
        learners=learners
    )

    submitted_certificate = None
    if request.method == 'POST':
        if form.is_valid():
            submitted_certificate = form.cleaned_data
            messages.success(
                request,
                "Certificate captured. Backend save/notification hooks can connect to this submission."
            )
        else:
            messages.error(request, "Please correct the highlighted errors before submitting.")

    recent_certifications = []

    waiting_for_certificate = []
    recent_trainings = trainings.filter(
        date__lte=timezone.localdate()
    ).prefetch_related("participants").order_by("-date")[:6]

    for training in recent_trainings:
        attendees = []
        for user in training.participants.order_by("first_name", "last_name", "username"):
            display_name = (user.get_full_name() or "").strip() or user.username
            attendees.append({
                "id": user.id,
                "name": display_name,
                "email": user.email,
                "username": user.username,
            })

        waiting_for_certificate.append({
            "id": training.id,
            "title": training.title,
            "date": training.date,
            "participants": len(attendees),
            "attendees": attendees,
        })

    return render(request, "training/staff_certificates.html", {
        "user_profile": user_profile,
        "form": form,
        "trainings": trainings,
        "learners": learners,
        "recent_certifications": recent_certifications,
        "waiting_for_certificate": waiting_for_certificate,
        "submitted_certificate": submitted_certificate,
    })


@never_cache
@login_required
def training_bulk_edit(request):
    """Bulk edit selected trainings."""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    ids_param = request.GET.get('ids') or request.POST.get('ids')
    if not ids_param:
        messages.warning(request, "Select at least one training to edit.")
        return redirect('dashboard:training_list')

    try:
        id_list = [int(_id) for _id in ids_param.split(',') if _id.strip().isdigit()]
    except ValueError:
        id_list = []

    queryset = Training.objects.filter(id__in=id_list).order_by('date', 'start_time')
    if not queryset.exists():
        messages.warning(request, "No matching trainings found to edit.")
        return redirect('dashboard:training_list')

    TrainingFormSet = modelformset_factory(Training, form=TrainingSessionForm, extra=0, can_delete=False)

    if request.method == 'POST':
        formset = TrainingFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Selected trainings were updated.")
            return redirect('dashboard:training_list')
    else:
        formset = TrainingFormSet(queryset=queryset)

    return render(request, "training/training_bulk_edit.html", {
        "user_profile": user_profile,
        "page_title": "Bulk Edit Trainings",
        "formset": formset,
        "selected_ids": ",".join(str(pk) for pk in queryset.values_list('id', flat=True)),
    })

@never_cache
@login_required
def training_bulk_remove(request):
    """Bulk remove selected trainings."""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method != 'POST':
        messages.warning(request, "Invalid request for bulk removal.")
        return redirect('dashboard:training_list')

    ids_param = request.POST.get('ids', '')
    id_list = [int(_id) for _id in ids_param.split(',') if _id.strip().isdigit()]
    if not id_list:
        messages.warning(request, "Select at least one training to remove.")
        return redirect('dashboard:training_list')

    qs = Training.objects.filter(id__in=id_list)
    deleted_count = qs.count()
    qs.delete()
    messages.success(request, f"Removed {deleted_count} training{'s' if deleted_count != 1 else ''}.")
    return redirect('dashboard:training_list')
    
@never_cache
@login_required
def calendar_add(request):
    """Base calendar for adding training sessions"""
    user_profile = request.user.userprofile

    # Provide the full training history so the sidebar panels (history/overview)
    # can surface past sessions for duplication and context while adding a new one.
    training_sessions = [
        {
            "id": t.id,
            "title": t.title,
            "date": t.date.isoformat(),
            "start_time": t.start_time.strftime("%H:%M"),
            "end_time": t.end_time.strftime("%H:%M"),
            "capacity": t.capacity,
        }
        for t in Training.objects.all().order_by('-date', '-start_time')
    ]

    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)
            training.instructor = request.user
            training.save()

            # Create Google Calendar event
            create_google_calendar_event(request.user, training)

            return redirect('dashboard:training_management')
    # prefill title if provided in querystring
    pre_title = request.GET.get('title')
    initial = {'title': pre_title} if pre_title else None
    return render(request, 'training/calendar_add.html', {
        "user_profile": user_profile,
        "page_title": "Add Training Calendar",
        "form": TrainingSessionForm(initial=initial) if initial else TrainingSessionForm(),
        "training_sessions": training_sessions,
        "selected_title": pre_title or "",
        "calendar_mode": "add",
    })


@never_cache
@login_required
def calendar_edit(request):
    """Base calendar for editing training sessions"""
    user_profile = request.user.userprofile
    training_id = request.GET.get('id')
    training = get_object_or_404(Training, id=training_id, instructor=request.user) if training_id else None
    
    if request.method == 'POST' and training:
        form = TrainingSessionForm(request.POST, instance=training)
        if form.is_valid():
            form.save()
            return redirect('dashboard:training_management')
            
    return render(request, 'training/calendar_edit.html', {
        "user_profile": user_profile,
        "page_title": "Edit Training Calendar",
        "form": TrainingSessionForm(instance=training) if training else None,
        "calendar_mode": "edit",
    })


@never_cache
@login_required
def calendar_remove(request):
    """Base calendar for removing training sessions"""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    today = timezone.localdate()
    selected_training_title = (
        request.GET.get('training_id')
        or request.GET.get('title')
        or request.GET.get('training')
    )

    trainings_qs = Training.objects.filter(date__gte=today).order_by('date', 'start_time')
    has_training_filter = bool(selected_training_title)
    if has_training_filter:
        trainings_qs = trainings_qs.filter(title=selected_training_title)
    else:
        trainings_qs = trainings_qs.none()
    training_sessions = [
        {
            "id": t.id,
            "title": t.title,
            "date": t.date.isoformat(),
            "start_time": t.start_time.strftime("%H:%M"),
            "end_time": t.end_time.strftime("%H:%M"),
            "capacity": t.capacity,
        }
        for t in trainings_qs
    ]

    if request.method == 'POST':
        training_id = request.POST.get('id')
        if training_id:
            deleted, _ = Training.objects.filter(id=training_id).delete()
            if deleted:
                messages.success(request, "Training session removed.")
            else:
                messages.warning(request, "Could not find that training session to remove.")
            return redirect('dashboard:training_management')
            
    return render(request, 'training/calendar_remove.html', {
        "user_profile": user_profile,
        "page_title": "Remove Training Calendar",
        "training_sessions": training_sessions,
        "calendar_mode": "remove",
    })


@login_required
def training_list_api(request):
    """Return JSON list of trainings for the calendar frontend."""
    trainings = Training.objects.all().order_by('date', 'start_time')
    data = []
    for t in trainings:
        data.append({
            'id': t.id,
            'title': t.title,
            'start': f"{t.date.isoformat()}T{t.start_time.strftime('%H:%M:%S')}",
            'end': f"{t.date.isoformat()}T{t.end_time.strftime('%H:%M:%S')}",
        })
    return JsonResponse(data, safe=False)

@login_required
def my_shifts_api(request):
    """Return JSON list of shifts for the My Shifts calendar frontend."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    today = timezone.localdate()
    next_week = today + timedelta(days=7)
    filter_mode = request.GET.get('filter', 'my_shifts')
    
    if filter_mode == 'my_shifts':
        trainings = Training.objects.filter(
            instructor=request.user,
            date__gte=today,
            date__lte=next_week
        ).order_by('date', 'start_time')
    else:
        trainings = Training.objects.filter(
            date__gte=today,
            date__lte=next_week
        ).select_related('instructor').order_by('date', 'start_time')
    
    data = []
    for t in trainings:
        event_data = {
            'id': t.id,
            'title': t.title,
            'start': f"{t.date.isoformat()}T{t.start_time.strftime('%H:%M:%S')}",
            'end': f"{t.date.isoformat()}T{t.end_time.strftime('%H:%M:%S')}",
        }
        # Add instructor name for all trainers view
        if filter_mode == 'all_trainers':
            instructor_name = t.instructor.get_full_name() or t.instructor.username
            event_data['title'] = f"{t.title} ({instructor_name})"
            # Highlight user's own shifts
            if t.instructor == request.user:
                event_data['backgroundColor'] = '#f6c851'
                event_data['borderColor'] = '#d9b03b'
            else:
                event_data['backgroundColor'] = '#5b9bd5'
                event_data['borderColor'] = '#4a7ba7'
        else:
            event_data['backgroundColor'] = '#f6c851'
            event_data['borderColor'] = '#d9b03b'
        
        data.append(event_data)
    
    return JsonResponse(data, safe=False)


def _get_completed_levels_by_category(user):
    """Return a mapping of category -> set(levels completed) for the user."""

    if not user.is_authenticated:
        return {}

    today = timezone.localdate()
    completed: dict[str, set[int]] = defaultdict(set)
    user_trainings = user.enrolled_trainings.filter(date__lte=today).only('title', 'date')
    for training in user_trainings:
        metadata = get_training_metadata(training.title)
        if not metadata:
            continue
        category = metadata.get('category')
        level = metadata.get('level')
        if not category or level is None:
            continue
        completed[category].add(int(level))
    return {category: set(levels) for category, levels in completed.items()}


def _get_training_start_datetime(training):
    """Return an aware datetime for the start of the provided training."""

    start_time = training.start_time or time_cls(0, 0)
    naive_start = datetime.combine(training.date, start_time)
    if timezone.is_naive(naive_start):
        return timezone.make_aware(naive_start, timezone.get_current_timezone())
    return naive_start


def _can_user_cancel_training(training, reference_time=None):
    """Return True if the user may cancel the training at the given moment."""

    reference = reference_time or timezone.now()
    start_dt = _get_training_start_datetime(training)
    return (start_dt - reference) > timedelta(minutes=15)


def _get_completed_level_one_categories(user):
    """Return a set of category keys where the user finished a Level 1 training."""

    completed_levels = _get_completed_levels_by_category(user)
    return {
        category
        for category, levels in completed_levels.items()
        if 1 in levels
    }


def _build_level_unlock_map(user):
    """Return a map describing which training levels are unlocked for the user."""

    completed_levels = _get_completed_levels_by_category(user)
    level_unlocks = {}

    for category_key, config in TRAINING_SECTIONS.items():
        category_completed = completed_levels.get(category_key, set())
        levels = config.get("levels", {})
        label = config.get("label", category_key.replace("_", " ").title())
        levels_data = {}

        for level, titles in sorted(levels.items(), key=lambda item: int(item[0])):
            level_number = int(level)
            prerequisite_met = (
                level_number == 1 or (level_number - 1) in category_completed
            )
            levels_data[f"level{level_number}"] = {
                "number": level_number,
                "titles": list(titles),
                "locked": False if level_number == 1 else not prerequisite_met,
                "completed": level_number in category_completed,
            }

        level_unlocks[category_key] = {
            "label": label,
            "levels": levels_data,
            "level1_completed": 1 in category_completed,
            "level2_completed": 2 in category_completed,
        }

    return level_unlocks


def _get_safe_next_url(request, default_route_name):
    """Return a safe next URL for redirects, falling back to a named route."""

    candidate = request.POST.get('next') or request.GET.get('next')
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}):
        return candidate
    return reverse(default_route_name)

@never_cache
@login_required
def my_trainings(request):
    """Student view: allows students to browse and reserve training sessions."""
    user_profile = request.user.userprofile

    # Only students should access this view
    if user_profile.role not in ['student', 'collaborator']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    today = timezone.localdate()
    now = timezone.now()
    reserved_trainings_qs = request.user.enrolled_trainings.filter(date__gte=today).order_by('date', 'start_time')
    reserved_trainings = [
        {
            "id": training.id,
            "title": training.title,
            "date": training.date,
            "start_time": training.start_time,
            "end_time": training.end_time,
            "can_cancel": _can_user_cancel_training(training, reference_time=now),
        }
        for training in reserved_trainings_qs
    ]

    trainings = [
        {"name": "3D Printing Training"},
        {"name": "Textile Training"},
        {"name": "Laser Cutter Training"},
        {"name": "Vinyl Cutter Training"},
        {"name": "2D Printing Training"},
        {"name": "Woodworking Training"},
        {"name": "Electronics Training"},
        {"name": "Metalworking Training"},
    ]

    return render(request, "training/my_trainings.html", {
        "user_profile": user_profile,
        "trainings": trainings,
        "level_unlocks": _build_level_unlock_map(request.user),
        "reserved_trainings": reserved_trainings,
    })

@never_cache
@login_required
def training_reserve(request):
    """Student training reservation calendar with prerequisite gating."""

    user_profile = request.user.userprofile
    if user_profile.role not in ['student', 'collaborator']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == 'POST':
        return _handle_reservation_post(request)

    today = timezone.localdate()
    selected_training_title = (
        request.GET.get('training_id')
        or request.GET.get('title')
        or request.GET.get('training')
    )

    trainings_qs = Training.objects.filter(date__gte=today).order_by('date', 'start_time')
    has_training_filter = bool(selected_training_title)
    if has_training_filter:
        trainings_qs = trainings_qs.filter(title=selected_training_title)
    else:
        trainings_qs = trainings_qs.none()

    training_sessions = [
        {
            "id": t.id,
            "title": t.title,
            "date": t.date.isoformat(),
            "start_time": t.start_time.strftime("%H:%M"),
            "end_time": t.end_time.strftime("%H:%M"),
            "capacity": t.capacity,
        }
        for t in trainings_qs
    ]

    completed_categories = sorted(_get_completed_level_one_categories(request.user))
    reserved_sessions = list(request.user.enrolled_trainings.values_list('id', flat=True))
    reserved_training_details = []
    if selected_training_title:
        reserved_training_details = [
            {
                "id": t.id,
                "title": t.title,
                "date": t.date.isoformat(),
                "start_time": t.start_time.strftime("%H:%M"),
                "end_time": t.end_time.strftime("%H:%M") if t.end_time else None,
            }
            for t in Training.objects
                .filter(id__in=reserved_sessions, title=selected_training_title)
                .order_by('-date', '-start_time')
        ]    

    return render(request, "training/training_reserve.html", {
        "user_profile": user_profile,
        "training_sessions": training_sessions,
        "calendar_mode": "reserve",
        "page_title": "Reserve Training Calendar",
        "prerequisite_map": serialize_prereq_map(),
        "completed_categories": completed_categories,
        "reserved_sessions": reserved_sessions,
        "selected_training_title": selected_training_title or "",
        "has_training_filter": has_training_filter,
        "reserved_training_details": reserved_training_details,
    })


def _handle_reservation_post(request):
    payload = {}
    if request.content_type == 'application/json':
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            payload = {}
    else:
        # Support form submissions / URL encoded data
        payload = request.POST

    training_id = payload.get('training_id')
    if not training_id:
        return JsonResponse({
            "ok": False,
            "error": "Missing training id.",
        }, status=400)

    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "error": "Training session not found.",
        }, status=404)

    user = request.user
    action = (payload.get('action') or 'reserve').strip().lower()

    if action == 'cancel':
        if not training.participants.filter(id=user.id).exists():
            return JsonResponse({
                "ok": False,
                "error": "You are not registered for this session.",
            }, status=400)

        if not _can_user_cancel_training(training):
            return JsonResponse({
                "ok": False,
                "error": "Cancellations are only allowed up to 15 minutes before the training start time.",
            }, status=400)
        
        # delete Google Calendar event if exists
        remove_google_calendar_event(user, training)
        training.participants.remove(user)

        reserved_ids = list(
            user.enrolled_trainings
            .filter(date__gte=timezone.localdate())
            .values_list('id', flat=True)
        )

        return JsonResponse({
            "ok": True,
            "message": "Reservation cancelled.",
            "training_id": training.id,
            "action": "cancel",
            "reserved_sessions": reserved_ids,
        })

    if action and action != 'reserve':
        return JsonResponse({
            "ok": False,
            "error": "Unsupported action.",
        }, status=400)

    metadata = get_training_metadata(training.title)
    completed_categories = _get_completed_level_one_categories(user)

    if metadata and metadata.get('level', 1) > 1 and metadata['category'] not in completed_categories:
        return JsonResponse({
            "ok": False,
            "error": "Complete Level 1 in this category to unlock this training.",
        }, status=403)

    if training.participants.filter(id=user.id).exists():
        return JsonResponse({
            "ok": False,
            "error": "You have already reserved this session.",
        }, status=400)

    if training.is_full:
        return JsonResponse({
            "ok": False,
            "error": "Sorry, this session is already full.",
        }, status=400)

    training.participants.add(user)
    create_google_calendar_event(user, training, save_event_id=True)

    updated_completed = sorted(_get_completed_level_one_categories(user))
    response = {
        "ok": True,
        "message": "Reservation confirmed! Check your dashboard for details.",
        "training_id": training.id,
        "completed_categories": updated_completed,
    }

    if metadata:
        response.update({
            "category": metadata['category'],
            "category_label": metadata.get('category_label'),
            "level": metadata.get('level'),
        })

    return JsonResponse(response)


@never_cache
@login_required
def training_list_student(request):
    return render(request, 'training/training_list_student.html')

@never_cache
@login_required
def help_support(request):
    """Help & Support page"""
    user_profile = request.user.userprofile
    return render(request, 'dashboard/help_support.html', {
        "user_profile": user_profile
    })


# ========== SHIFT REQUESTS & AVAILABILITY MANAGEMENT ==========

@never_cache
@login_required
def shift_detail_api(request, training_id):
    """API endpoint to get shift details for modal."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    training = get_object_or_404(Training, id=training_id)
    is_instructor = training.instructor == request.user
    
    data = {
        'id': training.id,
        'title': training.title,
        'date': training.date.isoformat(),
        'start_time': training.start_time.strftime('%H:%M'),
        'end_time': training.end_time.strftime('%H:%M'),
        'capacity': training.capacity,
        'participants_count': training.participants.count(),
        'instructor': training.instructor.get_full_name() or training.instructor.username,
        'instructor_id': training.instructor.id,
        'is_instructor': is_instructor,
        'can_request_cover': is_instructor and training.date >= timezone.localdate(),
        'can_offer_cover': not is_instructor and training.date >= timezone.localdate(),
    }
    
    return JsonResponse(data)


@never_cache
@login_required
def request_cover(request, training_id):
    """Request someone to cover a shift."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    training = get_object_or_404(Training, id=training_id)
    
    if training.instructor != request.user:
        messages.error(request, "You can only request cover for your own shifts.")
        return redirect('dashboard:my_shifts')
    
    if training.date < timezone.localdate():
        messages.error(request, "Cannot request cover for past shifts.")
        return redirect('dashboard:my_shifts')
    
    # Check if request already exists
    existing = ShiftRequest.objects.filter(
        training=training,
        requested_by=request.user,
        request_type='cover',
        status='pending'
    ).first()
    
    if existing:
        messages.info(request, "You already have a pending cover request for this shift.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    if request.method == 'POST':
        form = ShiftRequestForm(request.POST, user=request.user, training=training)
        if form.is_valid():
            shift_request = form.save(commit=False)
            shift_request.training = training
            shift_request.requested_by = request.user
            shift_request.request_type = 'cover'
            shift_request.save()
            messages.success(request, "Cover request created successfully!")
            return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    else:
        form = ShiftRequestForm(user=request.user, training=training)
        form.fields['request_type'].initial = 'cover'
        form.fields['swap_with_training'].widget = forms.HiddenInput()
    
    return render(request, 'dashboard/request_cover.html', {
        'form': form,
        'training': training,
        'user_profile': user_profile,
    })


@never_cache
@login_required
def request_swap(request, training_id):
    """Request to swap a shift with another person."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    training = get_object_or_404(Training, id=training_id)
    
    if training.instructor != request.user:
        messages.error(request, "You can only request swaps for your own shifts.")
        return redirect('dashboard:my_shifts')
    
    if training.date < timezone.localdate():
        messages.error(request, "Cannot request swap for past shifts.")
        return redirect('dashboard:my_shifts')
    
    if request.method == 'POST':
        form = ShiftRequestForm(request.POST, user=request.user, training=training)
        if form.is_valid():
            shift_request = form.save(commit=False)
            shift_request.training = training
            shift_request.requested_by = request.user
            # If no swap_with_training is selected, it's a cover request
            if not shift_request.swap_with_training:
                shift_request.request_type = 'cover'
                messages.success(request, "Cover request created successfully!")
            else:
                shift_request.request_type = 'swap'
                messages.success(request, "Swap request created successfully!")
            shift_request.save()
            return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    else:
        form = ShiftRequestForm(user=request.user, training=training)
        form.fields['request_type'].initial = 'swap'
        form.fields['swap_with_training'].required = False
    
    return render(request, 'dashboard/request_swap.html', {
        'form': form,
        'training': training,
        'user_profile': user_profile,
    })


@never_cache
@login_required
def offer_cover(request, training_id):
    """Offer to cover or swap someone else's shift."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    training = get_object_or_404(Training, id=training_id)
    
    if training.instructor == request.user:
        messages.error(request, "You cannot offer to cover or swap your own shift.")
        return redirect('dashboard:my_shifts')
    
    if training.date < timezone.localdate():
        messages.error(request, "Cannot offer to cover or swap past shifts.")
        return redirect('dashboard:my_shifts')
    
    # Get user's available shifts for swap option
    today = timezone.localdate()
    my_available_shifts = Training.objects.filter(
        instructor=request.user,
        date__gte=today
    ).exclude(id=training.id).order_by('date', 'start_time')
    
    if request.method == 'POST':
        swap_with_training_id = request.POST.get('swap_with_training', '')
        notes = request.POST.get('notes', '')
        
        try:
            redirect_url = None
            with transaction.atomic():
                if swap_with_training_id:
                    # Offer to swap
                    swap_with_training = get_object_or_404(Training, id=swap_with_training_id)
                    
                    # Verify the swap training belongs to the user
                    if swap_with_training.instructor != request.user:
                        messages.error(request, "You can only offer to swap with your own shifts.")
                        redirect_url = reverse('dashboard:requests') + '?main_tab=shift_requests'
                    else:
                        # Check if there's already a swap request
                        swap_request = ShiftRequest.objects.select_for_update().filter(
                            training=training,
                            request_type='swap',
                            swap_with_training=swap_with_training,
                            status='pending'
                        ).first()
                        
                        if not swap_request:
                            # Create a new swap request
                            swap_request = ShiftRequest.objects.create(
                                training=training,
                                requested_by=training.instructor,
                                request_type='swap',
                                swap_with_training=swap_with_training,
                                offered_by=request.user,
                                status='pending',
                                notes=notes or f"Swap offered by {request.user.get_full_name() or request.user.username}"
                            )
                            messages.success(request, f"You've offered to swap {swap_with_training.title} with {training.instructor.get_full_name() or training.instructor.username}'s shift!")
                        else:
                            # Check if someone else already offered this swap
                            if swap_request.offered_by and swap_request.offered_by != request.user:
                                messages.warning(request, "Someone else has already offered this swap.")
                                redirect_url = reverse('dashboard:requests') + '?main_tab=shift_requests'
                            else:
                                # Update offer
                                swap_request.offered_by = request.user
                                if notes:
                                    swap_request.notes = notes
                                swap_request.save()
                                messages.success(request, f"You've offered to swap {swap_with_training.title} with {training.instructor.get_full_name() or training.instructor.username}'s shift!")
                else:
                    # Offer to cover (no swap selected)
                    cover_request = ShiftRequest.objects.select_for_update().filter(
                        training=training,
                        request_type='cover',
                        status='pending'
                    ).first()
                    
                    if not cover_request:
                        # Create a new cover request and immediately offer
                        cover_request = ShiftRequest.objects.create(
                            training=training,
                            requested_by=training.instructor,
                            request_type='cover',
                            offered_by=request.user,
                            status='pending',
                            notes=notes or f"Offered by {request.user.get_full_name() or request.user.username}"
                        )
                        messages.success(request, f"You've offered to cover {training.instructor.get_full_name() or training.instructor.username}'s shift!")
                    else:
                        # Check if someone else already offered
                        if cover_request.offered_by and cover_request.offered_by != request.user:
                            messages.warning(request, "Someone else has already offered to cover this shift.")
                            redirect_url = reverse('dashboard:requests') + '?main_tab=shift_requests'
                        else:
                            # Offer on existing request
                            cover_request.offered_by = request.user
                            if notes:
                                cover_request.notes = notes
                            cover_request.save()
                            messages.success(request, f"You've offered to cover {training.instructor.get_full_name() or training.instructor.username}'s shift!")
            
            # Redirect after transaction completes
            if redirect_url:
                return redirect(redirect_url)
        
        except Exception as e:
            messages.error(request, "An error occurred while making the offer. Please try again.")
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error offering to cover/swap training {training_id}: {e}", exc_info=True)
        
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    # GET request - show form
    return render(request, 'dashboard/offer_cover.html', {
        'training': training,
        'my_available_shifts': my_available_shifts,
        'user_profile': user_profile,
    })


@never_cache
@login_required
def requests_page(request):
    """Main requests page with tabs for shift requests and time off requests."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    today = timezone.localdate()
    
    # Get main tab (shift_requests or time_off_requests)
    main_tab = request.GET.get('main_tab', 'shift_requests')
    
    # Shift Requests Data
    # Incoming: Requests for your shifts (where you're the instructor)
    # - Cover requests received: training.instructor == you, requested_by != you, offered_by == None
    # - Cover offers received: training.instructor == you, requested_by == you, offered_by != None
    # Exclude cover requests you sent (requested_by == you and request_type == 'cover' and no offer yet)
    incoming_shift_requests_qs = ShiftRequest.objects.filter(
        training__instructor=request.user,
        status='pending'
    ).exclude(
        requested_by=request.user,
        request_type='cover',
        offered_by__isnull=True
    ).select_related('training', 'requested_by', 'offered_by').order_by('-created_at')
    
    # Separate: Cover offers received (where you requested cover and someone offered)
    incoming_cover_offers_qs = ShiftRequest.objects.filter(
        training__instructor=request.user,
        requested_by=request.user,
        offered_by__isnull=False,
        status='pending'
    ).select_related('training', 'offered_by').order_by('-created_at')
    
    # Outgoing: Requests you made (where you're the requester)
    # - Cover requests sent: requested_by == you
    outgoing_shift_requests_qs = ShiftRequest.objects.filter(
        requested_by=request.user
    ).select_related('training', 'offered_by').annotate(
        status_priority=Case(
            When(status='pending', then=0),
            When(status='approved', then=1),
            When(status='rejected', then=2),
            When(status='cancelled', then=3),
            default=4,
            output_field=IntegerField(),
        )
    ).order_by('status_priority', '-created_at')
    
    # Cover offers you sent (where you're the offerer)
    # - Cover offers sent: offered_by == you
    # Combine with outgoing requests for "Sent Requests" tab
    outgoing_cover_offers_qs = ShiftRequest.objects.filter(
        offered_by=request.user
    ).select_related('training', 'requested_by').annotate(
        status_priority=Case(
            When(status='pending', then=0),
            When(status='approved', then=1),
            When(status='rejected', then=2),
            When(status='cancelled', then=3),
            default=4,
            output_field=IntegerField(),
        )
    ).order_by('status_priority', '-created_at')
    
    # Time Off Requests Data
    outgoing_time_off_qs = TimeOffRequest.objects.filter(
        user=request.user
    ).select_related('approved_by').order_by('-created_at')
    
    # Incoming time off requests (only for admins - all pending requests from all users)
    incoming_time_off_qs = TimeOffRequest.objects.none()  # Default empty queryset
    if user_profile.role == 'admin':
        incoming_time_off_qs = TimeOffRequest.objects.filter(
            status='pending'
        ).select_related('user', 'approved_by').order_by('-created_at')
    
    # Get user's shifts that can have requests (future shifts) for the "Send Request" tab
    my_available_shifts_qs = Training.objects.filter(
        instructor=request.user,
        date__gte=today
    ).order_by('date', 'start_time')
    
    # Get other trainers' shifts that user can offer to cover
    other_trainers_shifts_qs = Training.objects.filter(
        date__gte=today
    ).exclude(instructor=request.user).select_related('instructor').order_by('date', 'start_time')
    
    # Paginate querysets
    from django.core.paginator import Paginator
    
    # Limit to first 100 items for search functionality
    incoming_shift_requests_list = list(incoming_shift_requests_qs[:100])
    incoming_shift_requests_paginator = Paginator(incoming_shift_requests_list, 5)
    incoming_shift_requests_page = request.GET.get('incoming_shift_page', 1)
    incoming_shift_requests = incoming_shift_requests_paginator.get_page(incoming_shift_requests_page)
    
    # Combine requests you made and offers you made for "Sent Requests" tab
    from django.db.models import Q
    from itertools import chain
    
    # Limit to first 100 items for search functionality
    outgoing_shift_requests_list = list(outgoing_shift_requests_qs[:100])
    outgoing_cover_offers_list = list(outgoing_cover_offers_qs[:100])
    
    # Combine and sort by status priority and created_at
    combined_sent = sorted(
        chain(outgoing_shift_requests_list, outgoing_cover_offers_list),
        key=lambda x: (getattr(x, 'status_priority', 999), -(x.created_at.timestamp() if hasattr(x.created_at, 'timestamp') else 0))
    )[:100]
    
    outgoing_shift_requests_paginator = Paginator(combined_sent, 5)
    outgoing_shift_requests_page = request.GET.get('outgoing_shift_page', 1)
    outgoing_shift_requests = outgoing_shift_requests_paginator.get_page(outgoing_shift_requests_page)
    
    # Keep separate for other uses if needed
    outgoing_cover_offers_paginator = Paginator(outgoing_cover_offers_list, 5)
    outgoing_cover_offers_page = request.GET.get('outgoing_offers_page', 1)
    outgoing_cover_offers = outgoing_cover_offers_paginator.get_page(outgoing_cover_offers_page)
    
    # Limit to first 100 items for search functionality
    outgoing_time_off_list = list(outgoing_time_off_qs[:100])
    outgoing_time_off_paginator = Paginator(outgoing_time_off_list, 5)
    outgoing_time_off_page = request.GET.get('outgoing_time_off_page', 1)
    outgoing_time_off = outgoing_time_off_paginator.get_page(outgoing_time_off_page)
    
    # Paginate incoming time off requests (for admins)
    incoming_time_off_list = list(incoming_time_off_qs[:100])
    incoming_time_off_paginator = Paginator(incoming_time_off_list, 5)
    incoming_time_off_page = request.GET.get('incoming_time_off_page', 1)
    incoming_time_off = incoming_time_off_paginator.get_page(incoming_time_off_page)
    
    # Pagination for Send Request section
    # Limit to first 100 items for search functionality
    my_available_shifts_list = list(my_available_shifts_qs[:100])
    my_available_shifts_paginator = Paginator(my_available_shifts_list, 5)
    my_available_shifts_page = request.GET.get('my_shifts_page', 1)
    my_available_shifts = my_available_shifts_paginator.get_page(my_available_shifts_page)
    
    # Limit to first 100 items for search functionality
    other_trainers_shifts_list = list(other_trainers_shifts_qs[:100])
    other_trainers_shifts_paginator = Paginator(other_trainers_shifts_list, 5)
    other_trainers_shifts_page = request.GET.get('other_shifts_page', 1)
    other_trainers_shifts = other_trainers_shifts_paginator.get_page(other_trainers_shifts_page)
    
    # Get sub-tabs
    shift_sub_tab = request.GET.get('shift_tab', 'incoming')
    # Default to 'incoming' for admins, 'sent' for others
    if user_profile.role == 'admin':
        time_off_sub_tab = request.GET.get('time_off_tab', 'incoming')
    else:
        time_off_sub_tab = request.GET.get('time_off_tab', 'sent')
    
    # Count pending requests for badge
    pending_count = incoming_shift_requests_qs.count()
    if user_profile.role == 'admin':
        pending_count += incoming_time_off_qs.count()
    
    # Handle time off form submission
    form = None
    if main_tab == 'time_off_requests' and time_off_sub_tab == 'send' and request.method == 'POST':
        form = TimeOffRequestForm(request.POST)
        if form.is_valid():
            time_off = form.save(commit=False)
            time_off.user = request.user
            time_off.save()
            messages.success(request, "Time-off request submitted successfully!")
            return redirect(reverse('dashboard:requests') + '?main_tab=time_off_requests&time_off_tab=sent')
    elif main_tab == 'time_off_requests' and time_off_sub_tab == 'send':
        form = TimeOffRequestForm()
    
    return render(request, 'dashboard/requests_page.html', {
        'user_profile': user_profile,
        'incoming_shift_requests': incoming_shift_requests,
        'outgoing_shift_requests': outgoing_shift_requests,
        'outgoing_cover_offers': outgoing_cover_offers,
        'outgoing_time_off': outgoing_time_off,
        'incoming_time_off': incoming_time_off,
        'my_available_shifts': my_available_shifts,
        'other_trainers_shifts': other_trainers_shifts,
        'pending_count': pending_count,
        'main_tab': main_tab,
        'shift_sub_tab': shift_sub_tab,
        'time_off_sub_tab': time_off_sub_tab,
        'form': form,
    })


@never_cache
@login_required
def approve_shift_request(request, request_id):
    """Approve a shift request."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    shift_request = get_object_or_404(ShiftRequest, id=request_id)
    
    # Check if user can approve (must be the instructor of the shift)
    if shift_request.training.instructor != request.user:
        messages.error(request, "You can only approve requests for your own shifts.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    if shift_request.status != 'pending':
        messages.error(request, "This request has already been processed.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    if shift_request.request_type == 'cover' and not shift_request.offered_by:
        messages.error(request, "Cannot approve cover request without an offer.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    # Use transaction to ensure atomicity
    try:
        # Store values before transaction for calendar sync
        old_instructor = None
        new_instructor = None
        training1 = None
        training2 = None
        instructor1 = None
        instructor2 = None
        
        # Store original instructors BEFORE swapping (for calendar sync)
        if shift_request.request_type == 'cover':
            old_instructor = shift_request.training.instructor
            new_instructor = shift_request.offered_by
            
        elif shift_request.request_type == 'swap':
            if not shift_request.swap_with_training:
                raise ValidationError("Cannot approve swap request: no swap training specified.")
            
            training1 = shift_request.training
            training2 = shift_request.swap_with_training
            
            if not training2:
                raise ValidationError("Cannot approve: swap training no longer exists.")
            
            if not shift_request.offered_by:
                raise ValidationError("Cannot approve swap request: no offer has been made.")
            
            if training2.instructor != shift_request.offered_by:
                raise ValidationError("Invalid swap request: the swap training must belong to the person who offered.")
            
            # Verify training1 still belongs to the approver
            if training1.instructor != request.user:
                raise ValidationError("Cannot approve: you are no longer the instructor of this shift.")
            
            # Store original instructors BEFORE swapping
            instructor1 = training1.instructor
            instructor2 = training2.instructor
        
        # Delete old calendar events BEFORE swapping (so we have correct instructor info)
        if shift_request.request_type == 'cover' and old_instructor and new_instructor:
            remove_google_calendar_event(old_instructor, shift_request.training)
            
        elif shift_request.request_type == 'swap' and training1 and training2 and instructor1 and instructor2:
            remove_google_calendar_event(instructor1, training1)
            remove_google_calendar_event(instructor2, training2)
        
        with transaction.atomic():
            # Approve the request
            shift_request.status = 'approved'
            shift_request.approved_by = request.user
            shift_request.approved_at = timezone.now()
            shift_request.save()
            
            # Transfer the shift
            if shift_request.request_type == 'cover':
                # Verify new_instructor is still valid
                if not new_instructor:
                    raise ValidationError("Cannot approve: offer has been withdrawn.")
                
                shift_request.training.instructor = new_instructor
                shift_request.training.save()
                
            elif shift_request.request_type == 'swap':
                # Swap the instructors
                training1.instructor = instructor2
                training1.save()
                training2.instructor = instructor1
                training2.save()
        
        # Create new calendar events AFTER swapping (outside transaction)
        # Calendar sync failures are logged but don't affect the database transaction
        if shift_request.request_type == 'cover' and old_instructor and new_instructor:
            # Refresh training object to ensure we have the latest instructor
            shift_request.training.refresh_from_db()
            # Clear the old event ID since we're creating a new event in a different calendar
            shift_request.training.google_event_id = None
            shift_request.training.save(update_fields=['google_event_id'])
            # Create new event in new instructor's calendar
            create_google_calendar_event(new_instructor, shift_request.training)
            
        elif shift_request.request_type == 'swap' and training1 and training2 and instructor1 and instructor2:
            create_google_calendar_event(instructor2, training1)
            create_google_calendar_event(instructor1, training2)
        
        messages.success(request, "Request approved successfully!")
        
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, "An error occurred while approving the request. Please try again.")
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error approving shift request {request_id}: {e}", exc_info=True)
    
    return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')


@never_cache
@login_required
def reject_shift_request(request, request_id):
    """Reject a shift request."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    shift_request = get_object_or_404(ShiftRequest, id=request_id)
    
    if shift_request.training.instructor != request.user:
        messages.error(request, "You can only reject requests for your own shifts.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        shift_request.status = 'rejected'
        shift_request.approved_by = request.user
        shift_request.approved_at = timezone.now()
        shift_request.rejection_reason = rejection_reason
        shift_request.save()
        messages.success(request, "Request rejected.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    return render(request, 'dashboard/reject_request.html', {
        'shift_request': shift_request,
        'user_profile': user_profile,
    })


@never_cache
@login_required
def cancel_shift_request(request, request_id):
    """Cancel own shift request."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    shift_request = get_object_or_404(ShiftRequest, id=request_id)
    
    if shift_request.requested_by != request.user:
        messages.error(request, "You can only cancel your own requests.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    if shift_request.status != 'pending':
        messages.error(request, "Cannot cancel a request that has already been processed.")
        return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')
    
    shift_request.status = 'cancelled'
    shift_request.save()
    messages.success(request, "Request cancelled.")
    return redirect(reverse('dashboard:requests') + '?main_tab=shift_requests')


@never_cache
@login_required
def request_time_off(request):
    """Request time off - redirects to requests page."""
    return redirect(reverse('dashboard:requests') + '?main_tab=time_off_requests&time_off_tab=send')


@never_cache
@login_required
def approve_time_off(request, request_id):
    """Approve a time-off request. Only admins can approve."""
    user_profile = request.user.userprofile
    if user_profile.role != 'admin':
        return HttpResponseForbidden("You do not have permission to access this page. Only admins can approve time-off requests.")
    
    time_off = get_object_or_404(TimeOffRequest, id=request_id)
    
    if time_off.status != 'pending':
        messages.error(request, "This request has already been processed.")
        return redirect(reverse('dashboard:requests') + '?main_tab=time_off_requests')
    
    time_off.status = 'approved'
    time_off.approved_by = request.user
    time_off.approved_at = timezone.now()
    time_off.save()
    
    messages.success(request, "Time-off request approved.")
    return redirect(reverse('dashboard:requests') + '?main_tab=time_off_requests')


@never_cache
@login_required
def reject_time_off(request, request_id):
    """Reject a time-off request. Only admins can reject."""
    user_profile = request.user.userprofile
    if user_profile.role != 'admin':
        return HttpResponseForbidden("You do not have permission to access this page. Only admins can reject time-off requests.")
    
    time_off = get_object_or_404(TimeOffRequest, id=request_id)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        time_off.status = 'rejected'
        time_off.approved_by = request.user
        time_off.approved_at = timezone.now()
        time_off.rejection_reason = rejection_reason
        time_off.save()
        messages.success(request, "Time-off request rejected.")
        return redirect(reverse('dashboard:requests') + '?main_tab=time_off_requests')
    
    return render(request, 'dashboard/reject_time_off.html', {
        'time_off': time_off,
        'user_profile': user_profile,
    })
    
@never_cache
@login_required
def manage_availability(request):
    """Manage recurring (weekly) and one-time availability patterns."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Fetch both recurring and one-time availabilities, sorted by type/date
    availabilities = Availability.objects.filter(user=request.user).order_by(
        'specific_date', 'day_of_week', 'start_time'
    )

    if request.method == 'POST':
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            try:
                availability = form.save(commit=False)
                availability.user = request.user
                availability.save()
                messages.success(request, "Availability added successfully.")
                return redirect('dashboard:manage_availability')
            except ValidationError as e:
                messages.error(request, f"Error saving availability: {e}")
            except Exception as e:
                # Handle potential duplicates or DB constraint issues
                if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                    messages.error(
                        request,
                        "This availability pattern already exists. Please adjust your selection."
                    )
                else:
                    messages.error(request, "An unexpected error occurred while saving availability.")
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error saving availability: {e}", exc_info=True)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AvailabilityForm()

    return render(request, 'dashboard/manage_availability.html', {
        'form': form,
        'availabilities': availabilities,
        'user_profile': user_profile,
    })

@never_cache
@login_required
def delete_availability(request, availability_id):
    """Delete an availability pattern."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    availability = get_object_or_404(Availability, id=availability_id, user=request.user)
    availability.delete()
    messages.success(request, "Availability pattern deleted.")
    return redirect('dashboard:my_shifts')

@never_cache
@login_required
def my_shifts(request):
    """Staff view: shows staff member's upcoming shifts and all trainers' shifts."""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    today = timezone.localdate()
    next_week = today + timedelta(days=7)
    now = timezone.now()
    
    # Get staff member's own upcoming shifts (next week)
    my_shifts_qs = Training.objects.filter(
        instructor=request.user,
        date__gte=today,
        date__lte=next_week
    ).order_by('date', 'start_time')
    
    # Get all trainers' upcoming shifts (next week)
    all_trainers_shifts_qs = Training.objects.filter(
        date__gte=today,
        date__lte=next_week
    ).select_related('instructor').prefetch_related('participants').order_by('date', 'start_time')
    
    # Get view mode from query params (list or calendar)
    view_mode = request.GET.get('view', 'list')
    
    # Get filter mode from query params (my_shifts or all_trainers)
    filter_mode = request.GET.get('filter', 'my_shifts')
    
    # For calendar view, we need all shifts in JSON format
    import json
    my_shifts_json = json.dumps([
        {
            "id": training.id,
            "title": training.title,
            "date": training.date.isoformat(),
            "start_time": training.start_time.strftime("%H:%M:%S"),
            "end_time": training.end_time.strftime("%H:%M:%S"),
            "capacity": training.capacity,
            "participants_count": training.participants.count(),
            "instructor": training.instructor.get_full_name() or training.instructor.username,
        }
        for training in my_shifts_qs
    ])
    
    all_trainers_shifts_json = json.dumps([
        {
            "id": training.id,
            "title": training.title,
            "date": training.date.isoformat(),
            "start_time": training.start_time.strftime("%H:%M:%S"),
            "end_time": training.end_time.strftime("%H:%M:%S"),
            "capacity": training.capacity,
            "participants_count": training.participants.count(),
            "instructor": training.instructor.get_full_name() or training.instructor.username,
            "is_my_shift": training.instructor == request.user,
        }
        for training in all_trainers_shifts_qs
    ])
    
    # For list view, paginate the shifts (5 per page)
    my_shifts_paginator = None
    all_trainers_shifts_paginator = None
    my_shifts_page = None
    all_trainers_shifts_page = None
    
    if view_mode == 'list':
        # Paginate my shifts
        my_shifts_paginator = Paginator(my_shifts_qs, 5)
        my_shifts_page_num = request.GET.get('my_shifts_page', 1)
        my_shifts_page = my_shifts_paginator.get_page(my_shifts_page_num)
        
        # Paginate all trainers shifts
        all_trainers_shifts_paginator = Paginator(all_trainers_shifts_qs, 5)
        all_trainers_shifts_page_num = request.GET.get('all_trainers_page', 1)
        all_trainers_shifts_page = all_trainers_shifts_paginator.get_page(all_trainers_shifts_page_num)
        
        # Convert paginated querysets to lists for template
        my_shifts_list = [
            {
                "id": training.id,
                "title": training.title,
                "date": training.date,
                "start_time": training.start_time,
                "end_time": training.end_time,
                "capacity": training.capacity,
                "participants_count": training.participants.count(),
                "instructor": training.instructor.get_full_name() or training.instructor.username,
            }
            for training in my_shifts_page
        ]
        
        all_trainers_shifts_list = [
            {
                "id": training.id,
                "title": training.title,
                "date": training.date,
                "start_time": training.start_time,
                "end_time": training.end_time,
                "capacity": training.capacity,
                "participants_count": training.participants.count(),
                "instructor": training.instructor.get_full_name() or training.instructor.username,
                "is_my_shift": training.instructor == request.user,
            }
            for training in all_trainers_shifts_page
        ]
    else:
        # For calendar view, use empty lists (calendar uses JSON)
        my_shifts_list = []
        all_trainers_shifts_list = []
    
    # Get all staff members' availability
    from django.contrib.auth import get_user_model
    User = get_user_model()
    from apps.profiles.models import UserProfile
    staff_users = User.objects.filter(userprofile__role='staff').select_related('userprofile')
    
    # Get availability for all staff members
    all_availability = Availability.objects.filter(
        user__in=staff_users
    ).select_related('user').order_by('user__username', 'day_of_week', 'start_time')
    
    # Get approved time off requests for all staff members
    today = timezone.localdate()
    approved_time_off = TimeOffRequest.objects.filter(
        user__in=staff_users,
        status='approved',
        end_date__gte=today  # Only show future or current time off
    ).select_related('user').order_by('user__username', 'start_date')
    
    # Organize availability by user (includes recurring and one-time)
    availability_by_user = {}
    for avail in all_availability:
        username = avail.user.get_full_name() or avail.user.username
        if username not in availability_by_user:
            availability_by_user[username] = {
                'recurring': [],
                'time_off': []
            }
        
        # Prefer date display if specific_date exists
        if avail.specific_date:
            day_display = avail.specific_date.strftime("%b %d, %Y")
        else:
            day_display = avail.get_day_of_week_display() or "—"

        availability_by_user[username]['recurring'].append({
            'day': day_display,
            'day_num': avail.day_of_week,
            'specific_date': avail.specific_date,
            'start_time': avail.start_time.strftime("%H:%M"),
            'end_time': avail.end_time.strftime("%H:%M"),
            'is_available': avail.is_available,
            'type': 'recurring' if not avail.specific_date else 'one_time'
        })

    
    # Add time off requests to availability
    for time_off in approved_time_off:
        username = time_off.user.get_full_name() or time_off.user.username
        if username not in availability_by_user:
            availability_by_user[username] = {
                'recurring': [],
                'time_off': []
            }
        
        # Format time off display
        time_off_display = {
            'start_date': time_off.start_date,
            'end_date': time_off.end_date,
            'start_time': time_off.start_time.strftime("%H:%M") if time_off.start_time else None,
            'end_time': time_off.end_time.strftime("%H:%M") if time_off.end_time else None,
            'reason': time_off.reason,
            'type': 'time_off'
        }
        availability_by_user[username]['time_off'].append(time_off_display)
    
    # Get current user's availability
    my_availability = Availability.objects.filter(user=request.user).order_by('day_of_week', 'start_time')
    
    # Get current user's approved time off
    my_time_off = TimeOffRequest.objects.filter(
        user=request.user,
        status='approved',
        end_date__gte=today
    ).order_by('start_date')
    
    return render(request, "dashboard/my_shifts.html", {
        "user_profile": user_profile,
        "my_shifts": my_shifts_list,
        "all_trainers_shifts": all_trainers_shifts_list,
        "my_shifts_page": my_shifts_page,
        "all_trainers_shifts_page": all_trainers_shifts_page,
        "view_mode": view_mode,
        "filter_mode": filter_mode,
        "my_shifts_json": my_shifts_json,
        "all_trainers_shifts_json": all_trainers_shifts_json,
        "availability_by_user": availability_by_user,
        "my_availability": my_availability,
        "my_time_off": my_time_off,
    })
    

@never_cache
@login_required
def collaborator_requests(request):
    """Staff/admin view to approve or decline collaborator workspace reservations."""

    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page.")

    status_filter = (request.GET.get('status') or 'pending').lower()
    if status_filter not in ['pending', 'approved', 'rejected', 'all']:
        status_filter = 'pending'

    search_query = (request.GET.get('q') or "").strip()
    reservations = WorkspaceReservation.objects.select_related('user', 'approved_by').order_by('date', 'start_time', '-created_at')

    if status_filter != 'all':
        reservations = reservations.filter(status=status_filter)

    if search_query:
        reservations = reservations.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(purpose__icontains=search_query)
        )

    status_counts = {
        "pending": WorkspaceReservation.objects.filter(status='pending').count(),
        "approved": WorkspaceReservation.objects.filter(status='approved').count(),
        "rejected": WorkspaceReservation.objects.filter(status='rejected').count(),
    }

    upcoming_pending = WorkspaceReservation.objects.filter(
        status='pending',
        date__gte=timezone.localdate()
    ).order_by('date', 'start_time')[:3]

    return render(request, "dashboard/collaborator_requests.html", {
        "user_profile": user_profile,
        "reservations": reservations,
        "status_filter": status_filter,
        "search_query": search_query,
        "status_counts": status_counts,
        "upcoming_pending": upcoming_pending,
        "next_url": request.get_full_path(),
    })


@never_cache
@login_required
def workspace_reserve(request):
    """Collaborator page for reserving workspaces."""
    user_profile = request.user.userprofile
    if user_profile.role != 'collaborator':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    if request.method == 'POST':
        form = WorkspaceReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.user = request.user
            reservation.status = 'pending'
            reservation.save()
            messages.success(request, "Reservation request submitted successfully! It will be reviewed by staff.")
            return redirect('dashboard:my_reservations')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = WorkspaceReservationForm()
    
    return render(request, 'dashboard/workspace_reserve.html', {
        "user_profile": user_profile,
        "form": form
    })

@never_cache
@login_required
def my_reservations(request):
    """Collaborator page for viewing their workspace reservations."""
    user_profile = request.user.userprofile
    if user_profile.role != 'collaborator':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    reservations = WorkspaceReservation.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter in ['pending', 'approved', 'rejected']:
        reservations = reservations.filter(status=status_filter)
    
    return render(request, 'dashboard/my_reservations.html', {
        "user_profile": user_profile,
        "reservations": reservations,
        "status_filter": status_filter
    })


@never_cache
@login_required
def edit_workspace_reservation(request, reservation_id):
    """Edit workspace reservation - different behavior based on status."""
    user_profile = request.user.userprofile
    if user_profile.role != 'collaborator':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    reservation = get_object_or_404(WorkspaceReservation, id=reservation_id, user=request.user)
    
    # Rejected reservations cannot be edited
    if reservation.status == 'rejected':
        messages.error(request, "Rejected reservations cannot be edited.")
        return redirect('dashboard:my_reservations')
    
    # Approved reservations: create a new pending edit request
    if reservation.status == 'approved':
        if request.method == 'POST':
            form = WorkspaceReservationForm(request.POST)
            if form.is_valid():
                # Create a new reservation with the edited data
                new_reservation = form.save(commit=False)
                new_reservation.user = request.user
                new_reservation.status = 'pending'
                new_reservation.save()
                messages.success(request, "Edit request submitted! It will be reviewed by staff.")
                return redirect('dashboard:my_reservations')
        else:
            # Pre-fill form with existing reservation data
            form = WorkspaceReservationForm(instance=reservation)
        
        return render(request, 'dashboard/edit_workspace_reservation.html', {
            'form': form,
            'reservation': reservation,
            'user_profile': user_profile,
            'is_edit_request': True
        })
    
    # Pending reservations: direct edit
    if reservation.status == 'pending':
        if request.method == 'POST':
            form = WorkspaceReservationForm(request.POST, instance=reservation)
            if form.is_valid():
                form.save()
                messages.success(request, "Reservation updated successfully.")
                return redirect('dashboard:my_reservations')
        else:
            form = WorkspaceReservationForm(instance=reservation)
        
        return render(request, 'dashboard/edit_workspace_reservation.html', {
            'form': form,
            'reservation': reservation,
            'user_profile': user_profile,
            'is_edit_request': False
        })
    
    return redirect('dashboard:my_reservations')


@never_cache
@login_required
def delete_workspace_reservation(request, reservation_id):
    """Delete workspace reservation - allowed at any status."""
    user_profile = request.user.userprofile
    if user_profile.role != 'collaborator':
        return HttpResponseForbidden("You do not have permission to access this page.")
    
    reservation = get_object_or_404(WorkspaceReservation, id=reservation_id, user=request.user)
    
    if request.method == 'POST':
        reservation.delete()
        messages.success(request, "Reservation deleted successfully.")
        return redirect('dashboard:my_reservations')
    
    return render(request, 'dashboard/delete_workspace_reservation.html', {
        'reservation': reservation,
        'user_profile': user_profile
    })


@never_cache
@login_required
def approve_workspace_reservation(request, reservation_id):
    """Approve a workspace reservation. Only staff/admin can approve."""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page. Only staff/admin can approve reservations.")
    
    reservation = get_object_or_404(WorkspaceReservation, id=reservation_id)
    
    if reservation.status != 'pending':
        messages.error(request, "This reservation has already been processed.")
        return redirect(_get_safe_next_url(request, 'dashboard:collaborator_requests'))
    
    reservation.status = 'approved'
    reservation.approved_by = request.user
    reservation.approved_at = timezone.now()
    reservation.save()
    
    messages.success(request, "Reservation approved.")
    return redirect(_get_safe_next_url(request, 'dashboard:collaborator_requests'))


@never_cache
@login_required
def reject_workspace_reservation(request, reservation_id):
    """Reject a workspace reservation. Only staff/admin can reject."""
    user_profile = request.user.userprofile
    if user_profile.role not in ['staff', 'admin']:
        return HttpResponseForbidden("You do not have permission to access this page. Only staff/admin can reject reservations.")
    
    reservation = get_object_or_404(WorkspaceReservation, id=reservation_id)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        reservation.status = 'rejected'
        reservation.approved_by = request.user
        reservation.approved_at = timezone.now()
        reservation.rejection_reason = rejection_reason
        reservation.save()
        messages.success(request, "Reservation rejected.")
        return redirect(_get_safe_next_url(request, 'dashboard:collaborator_requests'))
    
    return render(request, 'dashboard/reject_workspace_reservation.html', {
        'reservation': reservation,
        'user_profile': user_profile,
        'next_url': _get_safe_next_url(request, 'dashboard:collaborator_requests'),
    })
