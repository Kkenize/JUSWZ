from django import template
from apps.dashboard.models import ShiftRequest, TimeOffRequest


register = template.Library()


@register.filter(name="dict_get")
def dict_get(mapping, key):
    """Safely fetch ``mapping[key]`` in templates."""

    if isinstance(mapping, dict):
        return mapping.get(key)
    return None


@register.simple_tag
def get_pending_shift_requests_count(user):
    """Get count of pending shift requests for a user."""
    return ShiftRequest.objects.filter(
        training__instructor=user,
        status='pending'
    ).count()
