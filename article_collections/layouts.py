from pathlib import Path

DEFAULT_TEMPLATE = "article_collections/detail.html"
TEXT_TEMPLATE = "article_collections/layouts/azbuka-pravoslaviya.html"
LAYOUT_DIRECTORY = (
    Path(__file__).resolve().parent / "templates/article_collections/layouts"
)


def collection_template_choices():
    """Only expose collection layouts, never arbitrary project templates."""
    choices = [(DEFAULT_TEMPLATE, "Стандартный — изображение и аннотация")]
    for path in sorted(LAYOUT_DIRECTORY.glob("*.html")):
        label = {
            "azbuka-pravoslaviya": "Азбука Православия — текстовая страница",
            "compact": "Компактный — текстовый список",
            "history": "История благочиния — карточки как во Flask",
            "novomucheniki-lotoshinskogo-okruga": "Новомученики Лотошинского округа",
        }.get(path.stem, path.stem)
        choices.append((f"article_collections/layouts/{path.name}", label))
    return choices
