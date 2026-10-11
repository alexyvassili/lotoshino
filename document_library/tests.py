import struct
from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from site_settings.models import SiteSettings

from .forms import DocumentForm
from .models import Document


def package(parts):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return output.getvalue()


def docx_parts():
    return {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/></w:body></w:document>',
    }


def odt_parts():
    return {
        "mimetype": "application/vnd.oasis.opendocument.text",
        "content.xml": '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"><office:body><office:text/></office:body></office:document-content>',
        "META-INF/manifest.xml": '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>',
    }


def ole_document(stream_name="WordDocument", flags=0):
    """Minimal compound file with a Word FIB and table stream, without mini-FAT."""
    free, end = 0xFFFFFFFF, 0xFFFFFFFE
    header = bytearray(512)
    header[:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<HHHHH", header, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIIII", header, 40, 0, 1, 0, 0, 4096, end, 0, end, 0)
    struct.pack_into("<109I", header, 76, 1, *([free] * 108))

    def directory_entry(name, kind, start, size, child=free, right=free):
        entry = bytearray(128)
        encoded = (name + "\0").encode("utf-16le")
        entry[: len(encoded)] = encoded
        struct.pack_into(
            "<HBBIII", entry, 64, len(encoded), kind, 1, free, right, child
        )
        struct.pack_into("<IQ", entry, 116, start, size)
        return entry

    directory = (
        directory_entry("Root Entry", 5, end, 0, child=1)
        + directory_entry(stream_name, 2, 2, 4096, right=2)
        + directory_entry("1Table" if flags & 0x200 else "0Table", 2, 10, 4096)
        + bytes(128)
    )
    fat = [free] * 128
    fat[0], fat[1] = end, 0xFFFFFFFD
    for first in (2, 10):
        for sector in range(first, first + 7):
            fat[sector] = sector + 1
        fat[first + 7] = end
    word = bytearray(4096)
    struct.pack_into("<HH", word, 0, 0xA5EC, 0xC1)
    struct.pack_into("<H", word, 10, flags)
    return bytes(header + directory + struct.pack("<128I", *fat) + word + bytes(4096))


def supported_documents():
    return {
        "doc": ole_document(),
        "docx": package(docx_parts()),
        "odt": package(odt_parts()),
        "pdf": b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n",
        "rtf": rb"{\rtf1\ansi Example document}",
    }


class DocumentLibraryTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)
        user = get_user_model().objects.create_superuser(
            username="documents-admin", password=None
        )
        self.client.force_login(user)
        self.add_url = reverse("admin:document_library_document_add")

    def upload(self, name, content):
        return self.client.post(
            self.add_url,
            {
                "title": "Документ",
                "file": SimpleUploadedFile(name, content, "application/octet-stream"),
            },
        )

    def test_all_formats_upload_and_download_unchanged(self):
        self.assertContains(
            self.client.get(reverse("admin:index")), "Библиотека документов"
        )
        for extension, content in supported_documents().items():
            with self.subTest(extension=extension):
                response = self.upload(f"sample.{extension.upper()}", content)
                self.assertEqual(response.status_code, 302)
                document = Document.objects.first()
                self.assertEqual(document.file_format, extension.upper())
                self.assertTrue(document.file.name.endswith(f".{extension}"))
                self.client.logout()
                response = self.client.get(document.get_absolute_url())
                self.assertEqual(b"".join(response.streaming_content), content)
                self.assertIn("attachment;", response["Content-Disposition"])
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.client.force_login(
                    get_user_model().objects.get(username="documents-admin")
                )

    def test_disabled_formats_rejected_and_existing_metadata_editable(self):
        for extension, content in supported_documents().items():
            with self.subTest(extension=extension):
                form = DocumentForm(
                    data={"title": "Existing"},
                    files={"file": SimpleUploadedFile(f"sample.{extension}", content)},
                )
                self.assertTrue(form.is_valid(), form.errors)
                document = form.save()
                settings = SiteSettings.load()
                setattr(settings, f"allow_file_{extension}", False)
                settings.save()
                response = self.upload(f"new.{extension}", content)
                self.assertContains(response, "отключена в настройках сайта")
                count = Document.objects.count()
                response = self.client.post(
                    reverse(
                        "admin:document_library_document_change", args=[document.pk]
                    ),
                    {"title": "Renamed"},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Document.objects.count(), count)

    def test_disguised_files_and_broken_signatures_are_rejected(self):
        bad_files = [
            ("renamed.pdf", supported_documents()["rtf"]),
            ("renamed.doc", ole_document("Workbook")),
            ("encrypted.doc", ole_document(flags=0x100)),
            ("header.doc", ole_document()[:512]),
            ("fake.docx", package({"test.txt": "Not a document"})),
            ("fake.pdf", b"%PDF-1.7\ntruncated"),
            ("fake.rtf", rb"{\rtf1\ansi truncated"),
            ("fake.pdf", b"<html>Not PDF</html>"),
            ("executable.pdf", b"MZ" + bytes(2048)),
            ("executable.doc", b"MZ" + bytes(2048)),
            ("executable.docx", b"MZ" + bytes(2048)),
            ("executable.odt", b"MZ" + bytes(2048)),
            ("executable.rtf", b"MZ" + bytes(2048)),
            ("image.pdf", b"\x89PNG\r\n\x1a\n"),
            ("document.exe", supported_documents()["pdf"]),
            ("odt.docx", supported_documents()["odt"]),
        ]
        for name, content in bad_files:
            with self.subTest(name=name):
                response = self.upload(name, content)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors.get("file"))
        self.assertFalse(Document.objects.exists())

    def test_container_type_xml_and_limits_are_checked(self):
        invalid_packages = []
        compressed = BytesIO()
        with ZipFile(compressed, "w", compression=ZIP_DEFLATED) as archive:
            for name, content in docx_parts().items():
                archive.writestr(name, content)
        corrupt = bytearray(compressed.getvalue())
        first_payload = 30 + len("[Content_Types].xml")
        corrupt[first_payload] = 0x07  # Reserved DEFLATE block type.
        invalid_packages.append(("broken-compression.docx", bytes(corrupt)))
        parts = docx_parts()
        parts["word/document.xml"] = "<fake/>"
        invalid_packages.append(("fake.docx", package(parts)))
        parts = docx_parts()
        parts["word/document.xml"] = (
            '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
        )
        invalid_packages.append(("entities.docx", package(parts)))
        parts = docx_parts()
        parts["word/vbaProject.bin"] = b"macro"
        invalid_packages.append(("macro.docx", package(parts)))
        parts = odt_parts()
        parts["mimetype"] = "application/vnd.oasis.opendocument.spreadsheet"
        invalid_packages.append(("spreadsheet.odt", package(parts)))
        parts = odt_parts()
        parts["content.xml"] = parts["content.xml"].replace(
            "office:text", "office:spreadsheet"
        )
        invalid_packages.append(("wrong-body.odt", package(parts)))
        for name, content in invalid_packages:
            with self.subTest(name=name):
                form = DocumentForm(
                    data={"title": "Invalid"},
                    files={"file": SimpleUploadedFile(name, content)},
                )
                self.assertFalse(form.is_valid())
                self.assertIn("file", form.errors)

    def test_size_limit_and_permissions(self):
        settings = SiteSettings.load()
        settings.max_upload_size_mb = 1
        settings.save()
        response = self.upload(
            "large.pdf", b"%PDF-1.7\n" + bytes(1024 * 1024) + b"%%EOF"
        )
        self.assertEqual(response.status_code, 413)
        self.assertFalse(Document.objects.exists())
        staff = get_user_model().objects.create_user(
            username="no-documents", is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        self.assertEqual(
            self.upload("test.rtf", supported_documents()["rtf"]).status_code, 403
        )
