from pathlib import Path

DEFAULT_TEMPLATE = "article_collections/detail.html"
LAYOUT_DIRECTORY = (
    Path(__file__).resolve().parent / "templates/article_collections/layouts"
)


def collection_template_choices():
    """Only expose collection layouts, never arbitrary project templates."""
    choices = [(DEFAULT_TEMPLATE, "Стандартный — изображение и аннотация")]
    for path in sorted(LAYOUT_DIRECTORY.glob("*.html")):
        label = {
            "compact": "Компактный — текстовый список",
            "history": "История благочиния — карточки как во Flask",
        }.get(path.stem, path.stem)
        choices.append((f"article_collections/layouts/{path.name}", label))
    return choices
