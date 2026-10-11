import re
import struct
import zlib
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

import olefile
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring
from django.core.exceptions import ValidationError

from site_settings.formats import DOCUMENT_FORMATS, validate_format
from site_settings.uploads import validate_upload_size

ODT_MIME = b"application/vnd.oasis.opendocument.text"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
WORD_NAMESPACES = (
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
)
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def read_xml(archive, name):
    if archive.getinfo(name).file_size > 8 * 1024 * 1024:
        raise ValidationError("XML внутри документа превышает допустимый размер 8 МБ.")
    return fromstring(archive.read(name), forbid_dtd=True)


def check_package(upload, extension):
    with ZipFile(upload) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (
            len(entries) > 4096
            or len(set(names)) != len(names)
            or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024
            or any(entry.flag_bits & 1 for entry in entries)
        ):
            raise ValidationError(
                "Документ зашифрован или превышает допустимый размер распаковки."
            )
        if extension == ".odt":
            if archive.read("mimetype") != ODT_MIME:
                raise ValueError("Not an ODT package")
            root = read_xml(archive, "content.xml")
            manifest = read_xml(archive, "META-INF/manifest.xml")
            manifest_ns = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
            if (
                root.tag != f"{{{OFFICE_NS}}}document-content"
                or root.find(f"{{{OFFICE_NS}}}body/{{{OFFICE_NS}}}text") is None
                or manifest.tag != f"{{{manifest_ns}}}manifest"
                or manifest.find(f".//{{{manifest_ns}}}encryption-data") is not None
            ):
                raise ValueError("Not a readable ODT text document")
            return "ODT"
        content_types = read_xml(archive, "[Content_Types].xml")
        ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        if content_types.tag != f"{{{ct_ns}}}Types" or not any(
            item.get("PartName") == "/word/document.xml"
            and item.get("ContentType") == DOCX_CONTENT_TYPE
            for item in content_types.findall(f"{{{ct_ns}}}Override")
        ):
            raise ValueError("Not a DOCX package")
        relationships = read_xml(archive, "_rels/.rels")
        rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        if not any(
            item.get("Type")
            in (
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
                "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
            )
            and item.get("Target", "").lstrip("/") == "word/document.xml"
            and item.get("TargetMode", "Internal") == "Internal"
            for item in relationships.findall(f"{{{rel_ns}}}Relationship")
        ):
            raise ValueError("Missing Word document relationship")
        root = read_xml(archive, "word/document.xml")
        if not any(
            root.tag == f"{{{ns}}}document" and root.find(f"{{{ns}}}body") is not None
            for ns in WORD_NAMESPACES
        ):
            raise ValueError("Invalid Word document XML")
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise ValueError("Macro-enabled files are not DOCX")
        return "DOCX"


def detect_document(upload):
    upload.seek(0)
    header = upload.read(16)
    extension = Path(upload.name).suffix.lower()
    upload.seek(0)
    if header.startswith(olefile.MAGIC):
        with olefile.OleFileIO(
            upload, raise_defects=olefile.DEFECT_INCORRECT
        ) as document:
            fib = document.openstream("WordDocument").read(32)
            if len(fib) != 32 or fib[:2] != b"\xec\xa5":
                raise ValueError("Missing Word FIB")
            flags = struct.unpack_from("<H", fib, 10)[0]
            if flags & 0x8100:
                raise ValidationError("Зашифрованные документы DOC не поддерживаются.")
            table = "1Table" if flags & 0x0200 else "0Table"
            if document.get_type(table) != olefile.STGTY_STREAM:
                raise ValueError("Missing Word table stream")
        return "DOC"
    if header.startswith(b"PK\x03\x04") and extension in {".docx", ".odt"}:
        return check_package(upload, extension)
    if re.match(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n\t ]", header):
        upload.seek(max(0, upload.size - 4096))
        if not upload.read().rstrip().endswith(b"%%EOF"):
            raise ValueError("Missing PDF end marker")
        return "PDF"
    if re.match(rb"\{\\rtf1(?:\\|\s)", header):
        upload.seek(max(0, upload.size - 4096))
        if not upload.read().rstrip().endswith(b"}"):
            raise ValueError("Truncated RTF")
        return "RTF"
    raise ValueError("Unknown document signature")


def validate_document(upload):
    validate_upload_size(upload)
    try:
        detected = detect_document(upload)
        validate_format(upload.name, detected, DOCUMENT_FORMATS)
        return detected
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        struct.error,
        BadZipFile,
        zlib.error,
        RuntimeError,
        NotImplementedError,
        ParseError,
        DefusedXmlException,
    ) as exc:
        raise ValidationError(
            "Содержимое файла не соответствует формату документа или файл повреждён."
        ) from exc
    finally:
        upload.seek(0)
