from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard 
    path('', views.landing_page, name='landing'),
    path('redirect/', views.dashboard_redirect, name='home'),
    path('student/', views.student_dashboard, name='student'),
    path('staff/', views.staff_dashboard, name='staff'),
    path('admin/', views.admin_dashboard, name='admin'),

    # Training Management
    path('training-management/', views.training_management, name='training_management'),
    path('training-management/all/', views.training_list, name='training_list'),
    path('training-management/past/', views.training_past, name='training_past'),
    path('training-management/bulk-edit/', views.training_bulk_edit, name='training_bulk_edit'),
    path('training-management/bulk-remove/', views.training_bulk_remove, name='training_bulk_remove'),

    # Calendar pages (under Training Management)
    path('training-management/calendar/add/', views.calendar_add, name='calendar_add'),
    path('training-management/calendar/edit/', views.calendar_edit, name='calendar_edit'),
    path('training-management/calendar/remove/', views.calendar_remove, name='calendar_remove'),
    # API for calendar events (minimal JSON list)
    path('training-management/calendar/events/', views.training_list_api, name='training_list_api'),
]
