from django.http import JsonResponse
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

from .uploads import FileSizeLimitUploadHandler, upload_limit_message


class UploadLimitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method != "POST" or request.content_type != "multipart/form-data":
            return None
        handler = FileSizeLimitUploadHandler(request)
        request.upload_handlers.insert(0, handler)
        # Parse before CSRF or a view can use a partially accepted upload.
        files = request.FILES
        if not handler.exceeded:
            return None
        for _, uploads in files.lists():
            for upload in uploads:
                upload.close()
        message = upload_limit_message(handler.limit_mb)
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({"error": {"message": message}}, status=413)
        return render(
            request,
            "site_settings/upload_too_large.html",
            {
                "title": "Файл слишком большой",
                "message": message,
                "return_url": request.get_full_path(),
            },
            status=413,
        )
