from django.contrib import admin
from .models import WorkspaceReservation


@admin.register(WorkspaceReservation)
class WorkspaceReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'workspace', 'date', 'start_time', 'end_time', 'status', 'created_at')
    list_filter = ('status', 'workspace', 'date', 'created_at')
    search_fields = ('user__username', 'user__email', 'purpose', 'workspace')
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Reservation Details', {
            'fields': ('user', 'workspace', 'date', 'start_time', 'end_time', 'purpose', 'estimated_participants')
        }),
        ('Status', {
            'fields': ('status', 'approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
