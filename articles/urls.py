from django.urls import path

from .views import detail

app_name = "articles"

urlpatterns = [path("<str:slug>/", detail, name="detail")]
