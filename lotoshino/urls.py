from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from article_collections.views import detail as collection_detail
from document_library.views import download
from document_library.views import view as document_view
from media_library.serving import image_file

from .views import favicon, index

urlpatterns = [
    path(
        f"{settings.MEDIA_URL.lstrip('/')}images/<path:filename>",
        image_file,
        name="image_file",
    ),
    path("documents/<int:pk>/download/", download, name="document_download"),
    path("documents/<int:pk>/view/", document_view, name="document_view"),
    path("", index, name="index"),
    path("favicon.ico", favicon, name="favicon"),
    path("articles/", include("articles.urls")),
    path("admin/", admin.site.urls),
]

# Only development settings install the toolbar. Its callback also checks DEBUG.
if "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [path("<slug:slug>/", collection_detail, name="article_collection")]
