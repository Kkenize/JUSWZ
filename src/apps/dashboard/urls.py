from django.urls import path
from . import views

app_name = 'dashboard'  # Add this line to define the app namespace

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('redirect/', views.dashboard_redirect, name='home'),
    path('student/', views.student_dashboard, name='student'),
    path('staff/', views.staff_dashboard, name='staff'),
    path('admin/', views.admin_dashboard, name='admin'),
]