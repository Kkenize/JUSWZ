from django.shortcuts import render, redirect

def landing_page(request):
    return render(request, 'dashboard/landing.html')

def dashboard_redirect(request):
    """
    Redirects user to their specific dashboard based on their role.
    Placeholder: Add logic to check user's role (e.g., from a profile model).
    """
    return redirect('dashboard:student') # Defaulting to student for now

def student_dashboard(request):
    return render(request, 'dashboard/student_dashboard.html')

def staff_dashboard(request):
    return render(request, 'dashboard/staff_dashboard.html')

def admin_dashboard(request):
    return render(request, 'dashboard/admin_dashboard.html')
