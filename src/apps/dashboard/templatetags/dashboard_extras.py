from django import template


register = template.Library()


@register.filter(name="dict_get")
def dict_get(mapping, key):
    """Safely fetch ``mapping[key]`` in templates."""

    if isinstance(mapping, dict):
        return mapping.get(key)
    return None
