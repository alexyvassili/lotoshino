from django.core.exceptions import ValidationError
from django.core.files.uploadhandler import FileUploadHandler, StopUpload

from .models import SiteSettings


def upload_limit_message(limit_mb):
    return f"Максимальный размер файла для загрузки — {limit_mb} МБ. Выберите файл меньшего размера."


def validate_upload_size(upload):
    settings = SiteSettings.load()
    if upload.size > settings.max_upload_size_bytes:
        raise ValidationError(upload_limit_message(settings.max_upload_size_mb))


class FileSizeLimitUploadHandler(FileUploadHandler):
    """Count each file before chunks reach Django's memory/disk handlers."""

    def __init__(self, request, max_bytes=None):
        super().__init__(request)
        self.max_bytes = max_bytes
        self.limit_mb = None
        self.exceeded = False

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        # Ordinary forms without files don't need a settings query.
        if self.max_bytes is None:
            settings = SiteSettings.load()
            self.max_bytes = settings.max_upload_size_bytes
            self.limit_mb = settings.max_upload_size_mb

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > self.max_bytes:
            self.exceeded = True
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None
