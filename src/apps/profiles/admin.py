from django.contrib import admin
from .models import Profile, UserProfile

# Register your models here.

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'phone_number', 'website')
    list_filter = ('location',)
    search_fields = ('user__username', 'user__email', 'location')
    raw_id_fields = ('user',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)
