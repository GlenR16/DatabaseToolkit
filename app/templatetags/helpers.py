from django import template
from django.template.defaultfilters import stringfilter
import base64

register = template.Library()

@register.filter
def get_fields(obj):
    return [(field.name, field.value_to_string(obj)) for field in obj._meta.fields]

@register.filter
@stringfilter
def readable_name(obj:str) -> str:
    return obj.replace("."," - ").replace("_", " ").title()

@register.filter
def b64encode(value:bytes) -> str:
    return base64.b64encode(value).decode("utf-8")

@register.filter
def split(value:str , key:str = "\n"):
    return value.split(key)
