from django.urls import path
from . import views

app_name = 'profiles'

urlpatterns = [
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('edit/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('admin/users/', views.admin_user_search, name='admin_user_search'),
    path('admin/profile/<str:username>/', views.admin_profile_management, name='admin_profile_management'),
]
