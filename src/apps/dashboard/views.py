from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.forms import modelformset_factory
from django.utils import timezone
from django.db.models import Count
from apps.profiles.models import UserProfile
from django.http import HttpResponseForbidden, JsonResponse
from .models import Training, create_google_calendar_event
from .forms import TrainingSessionForm


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
        "user_profile": user_profile
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
    trainings_qs = Training.objects.all().order_by('-date', '-start_time')
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

    trainings_qs = Training.objects.all().order_by('-date', '-start_time')
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
