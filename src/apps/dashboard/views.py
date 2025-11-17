import json
from datetime import datetime, time as time_cls, timedelta

from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.forms import modelformset_factory
from django.utils import timezone
from django.db.models import Count
from apps.profiles.models import UserProfile
from django.http import HttpResponseForbidden, JsonResponse
from .models import Training, create_google_calendar_event, remove_google_calendar_event
from .forms import TrainingSessionForm
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
def staff_dashboard(request):
    """Staff-only dashboard"""
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    return render(request, 'dashboard/staff_dashboard.html', {
        "user_profile": user_profile
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

@never_cache
@login_required
def my_trainings(request):
    """Student view: allows students to browse and reserve training sessions."""
    user_profile = request.user.userprofile

    # Only students should access this view
    if user_profile.role != 'student':
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
    if user_profile.role != 'student':
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
