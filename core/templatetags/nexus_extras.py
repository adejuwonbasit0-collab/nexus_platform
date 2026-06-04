from django import template

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
