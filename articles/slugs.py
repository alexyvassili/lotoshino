from django.utils.text import slugify

RUSSIAN_TRANSLITERATION = str.maketrans(
    dict(
        zip(
            "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
            (
                "a",
                "b",
                "v",
                "g",
                "d",
                "e",
                "yo",
                "zh",
                "z",
                "i",
                "y",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "r",
                "s",
                "t",
                "u",
                "f",
                "h",
                "ts",
                "ch",
                "sh",
                "shch",
                "",
                "y",
                "",
                "e",
                "yu",
                "ya",
            ),
            strict=True,
        )
    )
)


def article_slug_base(title):
    return slugify(title.lower().translate(RUSSIAN_TRANSLITERATION)) or "article"


def available_slug(base, articles, max_length):
    slug = base[:max_length].rstrip("-_")
    number = 2
    while articles.filter(slug=slug).exists():
        suffix = f"-{number}"
        slug = base[: max_length - len(suffix)].rstrip("-_") + suffix
        number += 1
    return slug
