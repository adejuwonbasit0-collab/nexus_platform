from django import template
from builtins import getattr as builtins_getattr

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """{{ my_dict|get_item:"key" }}"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}


@register.filter
def split(value, delimiter=','):
    """{{ "a,b,c"|split:"," }} → ['a','b','c']"""
    return [x.strip() for x in str(value).split(delimiter)]


@register.filter
def getattr(obj, attr_name):
    """{{ some_obj|getattr:"is_active" }} — safe attribute lookup for use
    alongside get_item, where the attribute name is only known at runtime."""
    return builtins_getattr(obj, attr_name, None) if obj else None


@register.filter
def display_name(obj):
    """Safely get a human-readable name from heterogeneous objects
    (Content/Movie/Track/Post/Image/Series have `title`, Artist has `name`,
    User has `username`) without crashing on missing attributes."""
    return getattr(obj, 'title', None) or getattr(obj, 'name', None) or getattr(obj, 'username', '') or ''