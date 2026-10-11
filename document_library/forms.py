from django import forms
from django.core.files.uploadedfile import UploadedFile

from site_settings.formats import DOCUMENT_FORMATS, allowed_extensions

from .models import Document
from .validation import validate_document


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ("title", "file")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["accept"] = ",".join(
            allowed_extensions(DOCUMENT_FORMATS)
        )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if isinstance(upload, UploadedFile):
            self.instance.file_format = validate_document(upload)
            self.instance.original_name = upload.name
        return upload
