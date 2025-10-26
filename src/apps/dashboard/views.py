from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.profiles.models import UserProfile
from django.http import HttpResponseForbidden


def landing_page(request):
    return render(request, 'dashboard/landing.html')


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

@login_required
def student_dashboard(request):
    user_profile = request.user.userprofile
    if user_profile.role != 'user':
        return HttpResponseForbidden("You do not have permission to access this page.")
    return render(request, 'dashboard/student_dashboard.html', {
        "user_profile": user_profile
    })


@login_required
def staff_dashboard(request):
    user_profile = request.user.userprofile
    if user_profile.role != 'staff':
        return HttpResponseForbidden("You do not have permission to access this page.")
    return render(request, 'dashboard/staff_dashboard.html', {
        "user_profile": user_profile
    })


@login_required
def admin_dashboard(request):
    user_profile = request.user.userprofile
    if user_profile.role != 'admin':
        return HttpResponseForbidden("You do not have permission to access this page.")
    return render(request, 'dashboard/admin_dashboard.html', {
        "user_profile": user_profile
    })
