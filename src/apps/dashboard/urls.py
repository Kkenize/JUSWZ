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
    
    # My Trainings (student)
    path('training-list/student/', views.training_list_student, name='training_list_student'),
    
    # My Trainings (student view)
    path("my-trainings/", views.my_trainings, name="my_trainings"),
    
    # Training Reserve (under My Trainings)
    path("training-reserve/", views.training_reserve, name="training_reserve"),

    # Calendar pages (under Training Management)
    path('training-management/calendar/add/', views.calendar_add, name='calendar_add'),
    path('training-management/calendar/edit/', views.calendar_edit, name='calendar_edit'),
    path('training-management/calendar/remove/', views.calendar_remove, name='calendar_remove'),
    # API for calendar events (minimal JSON list)
    path('training-management/calendar/events/', views.training_list_api, name='training_list_api'),
    # API for My Shifts calendar events
    path('my-shifts/events/', views.my_shifts_api, name='my_shifts_api'),

    # Help & Support
    path('help/', views.help_support, name='help'),
    
    # My Shifts (staff)
    path('my-shifts/', views.my_shifts, name='my_shifts'),
    
    # Shift Requests & Availability
    path('my-shifts/shift/<int:training_id>/details/', views.shift_detail_api, name='shift_detail_api'),
    path('my-shifts/request-cover/<int:training_id>/', views.request_cover, name='request_cover'),
    path('my-shifts/request-swap/<int:training_id>/', views.request_swap, name='request_swap'),
    path('my-shifts/offer-cover/<int:training_id>/', views.offer_cover, name='offer_cover'),
    
    # Requests Page
    path('requests/', views.requests_page, name='requests'),
    
    # Shift Request Actions
    path('requests/shift/<int:request_id>/approve/', views.approve_shift_request, name='approve_shift_request'),
    path('requests/shift/<int:request_id>/reject/', views.reject_shift_request, name='reject_shift_request'),
    path('requests/shift/<int:request_id>/cancel/', views.cancel_shift_request, name='cancel_shift_request'),
    
    # Time Off Actions
    path('requests/time-off/<int:request_id>/approve/', views.approve_time_off, name='approve_time_off'),
    path('requests/time-off/<int:request_id>/reject/', views.reject_time_off, name='reject_time_off'),
    
    # Availability
    path('requests/availability/', views.manage_availability, name='manage_availability'),
    path('requests/availability/<int:availability_id>/delete/', views.delete_availability, name='delete_availability'),
]
