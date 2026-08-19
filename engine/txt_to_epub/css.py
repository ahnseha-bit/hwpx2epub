from ebooklib import epub


def add_css_style(book: epub.EpubBook) -> None:
    """Add a conservative stylesheet shared by KakaoPage and RIDI exports."""
    style = """
    html, body {
        margin: 0em;
        padding: 0em;
    }

    body {
        font-size: 1em;
        line-height: 1.8em;
    }

    p {
        margin: 1em 0em;
        padding: 0em;
        font-size: 1em;
        line-height: 1.8em;
        text-align: justify;
    }

    p.scene-break {
        text-align: center;
        text-indent: 0em;
    }

    .chapter-title {
        margin: 2em 0em;
        padding: 0em;
        font-size: 1.5em;
        font-weight: 700;
        text-align: left;
    }

    .toc-title {
        margin: 0em 0em 2em 0em;
        font-size: 1.5em;
        font-weight: 700;
    }

    .toc-list, .toc-sublist {
        margin: 0em;
        padding: 0em;
        list-style: none;
    }

    .toc-list li {
        margin: 1em 0em;
    }

    .toc-sublist {
        margin-left: 1.5em;
    }

    .toc-list a {
        color: inherit;
        text-decoration: none;
    }

    .duokan-image-single {
        width: 100%;
        margin: 1em 0em;
        text-align: center;
    }

    img.duokan-image {
        width: 100%;
        height: auto;
        margin: 0em;
    }

    .duokan-note {
        margin: 0.5em 0em 1em 0em;
        text-indent: 0em;
        text-align: center;
    }
    """
    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style.encode("utf-8"),
    )
    book.add_item(nav_css)
