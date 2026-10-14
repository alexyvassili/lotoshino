import re

import nh3
from django.conf import settings

from .illustrations import strip_external_illustrations

IMAGE_CLASSES = {
    "image",
    "image_resized",
    "image-style-align-left",
    "image-style-align-right",
    "image-style-align-center",
}


def filter_attribute(tag, name, value):
    if tag == "a" and name == "data-document-format":
        return value if value in {"PDF", "DOC", "DOCX", "ODT", "RTF"} else None
    if tag == "a" and name == "target":
        return value if value == "_blank" else None
    if name == "id":
        return value if re.fullmatch(r"drupal-[A-Za-z0-9_-]{1,100}", value) else None
    if name in {"colspan", "rowspan"}:
        return value if value.isdigit() and 1 <= int(value) <= 100 else None
    if tag == "a" and name == "data-illustration":
        return "true" if value == "true" else None
    if name == "class":
        if tag == "a":
            return "document-link" if "document-link" in value.split() else None
        if tag == "figure" and value == "table":
            return value
        if tag == "p":
            return (
                "article-annotation" if "article-annotation" in value.split() else None
            )
        return " ".join(part for part in value.split() if part in IMAGE_CLASSES) or None
    if name == "style":
        if tag in {"table", "td", "th"}:
            declarations = []
            for declaration in value.split(";"):
                property_name, _, property_value = declaration.partition(":")
                property_name, property_value = (
                    property_name.strip().lower(),
                    property_value.strip().lower(),
                )
                if property_name == "border" and re.fullmatch(
                    r"(?:0|[1-9]|10)px (?:none|solid|dashed|dotted|double) #[0-9a-f]{3}(?:[0-9a-f]{3})?",
                    property_value,
                ):
                    declarations.append(f"border:{property_value}")
                elif (
                    (
                        property_name == "border-style"
                        and property_value
                        in {"none", "solid", "dashed", "dotted", "double"}
                    )
                    or (
                        property_name == "border-color"
                        and re.fullmatch(
                            r"#[0-9a-f]{3}(?:[0-9a-f]{3})?", property_value
                        )
                    )
                    or (
                        property_name == "border-width"
                        and re.fullmatch(r"(?:0|[1-9]|10)(?:px)?", property_value)
                    )
                ):
                    declarations.append(f"{property_name}:{property_value}")
            return ";".join(declarations) + ";" if declarations else None
        match = re.fullmatch(r"\s*width\s*:\s*(\d+(?:\.\d+)?)%\s*;?\s*", value)
        if match and 1 <= float(match[1]) <= 100:
            return f"width:{match[1]}%;"
        return None
    if tag == "img" and name == "data-viewer":
        return value if value in {"true", "false"} else None
    if tag == "img" and name in {"src", "data-full-size"}:
        # The editor only inserts images uploaded to our own library.
        prefix = re.escape(settings.MEDIA_URL.rstrip("/") + "/images/")
        return (
            value
            if re.fullmatch(
                prefix
                + r"(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})"
                + r"(?:_[A-Za-z0-9]{7})?(?:_[1-9]\d{0,4}x[1-9]\d{0,4}(?:_[A-Za-z0-9]{7})?)?\.(?:jpg|png|webp)",
                value,
            )
            else None
        )
    if name in {"width", "height"}:
        return value if value.isdigit() and 0 < int(value) <= 25000 else None
    return value


def clean_article_html(value):
    cleaned = nh3.clean(
        value,
        tags={
            "p",
            "br",
            "h2",
            "h3",
            "h4",
            "strong",
            "em",
            "ul",
            "ol",
            "li",
            "blockquote",
            "a",
            "figure",
            "figcaption",
            "img",
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "td",
            "th",
        },
        attributes={
            "p": {"class", "id"},
            "h2": {"id"},
            "h3": {"id"},
            "h4": {"id"},
            "table": {"style"},
            "td": {"colspan", "rowspan", "style"},
            "th": {"colspan", "rowspan", "style"},
            "a": {
                "href",
                "title",
                "data-illustration",
                "class",
                "data-document-format",
                "target",
            },
            "figure": {"class", "style"},
            "img": {"src", "alt", "width", "height", "data-viewer", "data-full-size"},
        },
        attribute_filter=filter_attribute,
        url_schemes={"http", "https", "mailto", "tel"},
    )
    return strip_external_illustrations(cleaned)
