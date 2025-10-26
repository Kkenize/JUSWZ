from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('redirect/', views.dashboard_redirect, name='dashboard_home'),
    path('student/', views.student_dashboard, name='dashboard_student'),
    path('staff/', views.staff_dashboard, name='dashboard_staff'),
    path('admin/', views.admin_dashboard, name='dashboard_admin'),
    path('trainer/', views.trainer_dashboard, name='dashboard_trainer'),
]