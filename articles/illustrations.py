import re
from html.parser import HTMLParser
from urllib.parse import unquote

ILLUSTRATION_ERROR = (
    "Для иллюстрации укажите относительный адрес на этом сайте. Адрес должен начинаться символом /. "
    "Ссылки на внешние сайты использовать нельзя."
)


def is_local_illustration_url(value):
    value = unquote(value or "")
    return bool(re.fullmatch(r"/(?!/)[^\s\\]*", value))


class IllustrationLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.invalid = False
        self.invalid_tags = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (
            tag == "a"
            and attrs.get("data-illustration") == "true"
            and not is_local_illustration_url(attrs.get("href"))
        ):
            self.invalid = True
            self.invalid_tags.append((self.getpos(), self.get_starttag_text()))


def has_invalid_illustrations(content):
    parser = IllustrationLinks()
    parser.feed(content)
    return parser.invalid


def strip_external_illustrations(content):
    # Called after HTML sanitization: attributes are quoted and normalized.
    parser = IllustrationLinks()
    parser.feed(content)
    offsets = [0]
    for line in content.split("\n"):
        offsets.append(offsets[-1] + len(line) + 1)
    for (line, column), tag in reversed(parser.invalid_tags):
        start = offsets[line - 1] + column
        cleaned = tag.replace(' data-illustration="true"', "")
        content = content[:start] + cleaned + content[start + len(tag) :]
    return content
