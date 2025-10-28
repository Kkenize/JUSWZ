from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from apps.profiles.models import UserProfile
from django.http import HttpResponseForbidden


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
