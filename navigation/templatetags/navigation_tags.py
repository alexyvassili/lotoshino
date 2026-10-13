from django import template

from navigation.models import MenuItem

register = template.Library()


@register.simple_tag(takes_context=True)
def site_menus(context):
    result = {"main": [], "top": []}
    request = context.get("request")
    path = request.path if request else ""
    items = MenuItem.objects.filter(is_visible=True).select_related(
        "home_page", "article", "collection"
    )
    for item in items:
        if destination := item.get_destination():
            result[item.menu_id].append(
                {
                    "title": item.title,
                    "url": destination,
                    "is_current": item.is_current(path, destination),
                }
            )
    return result
