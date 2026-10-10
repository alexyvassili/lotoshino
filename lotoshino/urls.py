from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import favicon, index

urlpatterns = [
    path("", index, name="index"),
    path("favicon.ico", favicon, name="favicon"),
    path("articles/", include("articles.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
