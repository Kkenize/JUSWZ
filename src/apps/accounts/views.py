from django.shortcuts import render

# Create your views here.

def home_view(request):
    """Landing page with login button"""
    return render(request, 'accounts/home.html')

def login_view(request):
    """Login page"""
    return render(request, 'accounts/login.html')
