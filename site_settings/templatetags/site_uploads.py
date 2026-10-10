from django import template

from site_settings.models import SiteSettings

register = template.Library()


@register.simple_tag
def site_upload_limit():
    return SiteSettings.load().max_upload_size_mb
