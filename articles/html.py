import re

import nh3
from django.conf import settings

IMAGE_CLASSES = {
    "image",
    "image_resized",
    "image-style-align-left",
    "image-style-align-right",
    "image-style-align-center",
}


def filter_attribute(tag, name, value):
    if name == "class":
        return " ".join(part for part in value.split() if part in IMAGE_CLASSES) or None
    if name == "style":
        match = re.fullmatch(r"\s*width\s*:\s*(\d+(?:\.\d+)?)%\s*;?\s*", value)
        if match and 1 <= float(match[1]) <= 100:
            return f"width:{match[1]}%;"
        return None
    if tag == "img" and name == "src":
        # The editor only inserts images uploaded to our own library.
        prefix = re.escape(settings.MEDIA_URL.rstrip("/") + "/images/")
        return (
            value
            if re.fullmatch(prefix + r"[a-f0-9]{32}\.(?:jpg|png|webp)", value)
            else None
        )
    if name in {"width", "height"}:
        return value if value.isdigit() and 0 < int(value) <= 25000 else None
    return value


def clean_article_html(value):
    return nh3.clean(
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
            "a": {"href", "title"},
            "figure": {"class", "style"},
            "img": {"src", "alt", "width", "height"},
        },
        attribute_filter=filter_attribute,
        url_schemes={"http", "https", "mailto", "tel"},
    )
