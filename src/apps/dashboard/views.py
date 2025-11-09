from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from apps.profiles.models import UserProfile
from django.http import HttpResponseForbidden, JsonResponse
from .models import Training
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
def calendar_add(request):
    """Base calendar for adding training sessions"""
    user_profile = request.user.userprofile
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)
            training.instructor = request.user
            training.save()
            return redirect('dashboard:training_management')
    # prefill title if provided in querystring
    pre_title = request.GET.get('title')
    initial = {'title': pre_title} if pre_title else None
    return render(request, 'training/calendar_add.html', {
        "user_profile": user_profile,
        "page_title": "Add Training Calendar",
        "form": TrainingSessionForm(initial=initial) if initial else TrainingSessionForm()
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
    })


@never_cache
@login_required
def calendar_remove(request):
    """Base calendar for removing training sessions"""
    user_profile = request.user.userprofile
    if request.method == 'POST':
        training_id = request.POST.get('id')
        if training_id:
            Training.objects.filter(id=training_id, instructor=request.user).delete()
            return redirect('dashboard:training_management')
            
    return render(request, 'training/calendar_remove.html', {
        "user_profile": user_profile,
        "page_title": "Remove Training Calendar",
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

