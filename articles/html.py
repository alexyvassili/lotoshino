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
    if tag == "a" and name == "data-illustration":
        return "true" if value == "true" else None
    if name == "class":
        if tag == "p":
            return (
                "article-annotation" if "article-annotation" in value.split() else None
            )
        return " ".join(part for part in value.split() if part in IMAGE_CLASSES) or None
    if name == "style":
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
        },
        attributes={
            "p": {"class"},
            "a": {"href", "title", "data-illustration"},
            "figure": {"class", "style"},
            "img": {"src", "alt", "width", "height", "data-viewer", "data-full-size"},
        },
        attribute_filter=filter_attribute,
        url_schemes={"http", "https", "mailto", "tel"},
    )
    return strip_external_illustrations(cleaned)
