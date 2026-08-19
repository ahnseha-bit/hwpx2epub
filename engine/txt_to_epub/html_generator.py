import html
import re
from ebooklib import epub
from typing import Any, Optional


def _normalize_epub_language(language: str) -> str:
    """Return a supported EPUB language code."""
    return language if language in {"ko", "zh", "en"} else "en"


def _render_toc_entries(entries: list[Any]) -> str:
    """Render EbookLib's nested TOC structure as linked HTML lists."""
    items = []
    for entry in entries:
        children = []
        link = entry
        if isinstance(entry, tuple):
            link, children = entry

        href = _escape_text(getattr(link, "href", ""), quote=True)
        title = _escape_text(getattr(link, "title", ""))
        if not href or not title:
            continue
        if title.strip() == "판권":
            continue

        child_html = _render_toc_entries(list(children)) if children else ""
        nested = f'<ol class="toc-sublist">{child_html}</ol>' if child_html else ""
        items.append(f'<li><a href="{href}">{title}</a>{nested}</li>')
    return "\n".join(items)


def create_toc_page(entries: list[Any], language: str = "en") -> epub.EpubHtml:
    """Create a visible, styled table-of-contents page."""
    language = _normalize_epub_language(language)
    labels = {"ko": "목차", "zh": "目录", "en": "Contents"}
    title = labels[language]
    toc_page = epub.EpubHtml(title=title, file_name="contents.xhtml", lang=language)
    toc_page.content = f'''<!DOCTYPE html>
    <html lang="{language}">
    <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>{title}</title>
        <link rel="stylesheet" type="text/css" href="style/nav.css"/>
    </head>
    <body class="toc-page">
        <h1 class="toc-title">{title}</h1>
        <nav aria-label="{title}">
            <ol class="toc-list">{_render_toc_entries(entries)}</ol>
        </nav>
    </body>
    </html>'''
    toc_page.add_link(href="style/nav.css", rel="stylesheet", type="text/css")
    return toc_page


def _escape_text(text: Optional[str], *, quote: bool = False) -> str:
    """Normalize existing entities, then escape plain text for HTML insertion."""
    normalized = html.unescape(text or "")
    return html.escape(normalized, quote=quote)


def _render_text_blocks(content: str) -> str:
    """
    Render plain text content as standard paragraph HTML.

    The previous implementation wrapped whole chapters in one large <pre>,
    which is prone to rendering differences across EPUB readers.
    """
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    paragraphs = []
    blocks = re.split(r"\n\s*\n+", normalized)
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        regular_lines = []

        def flush_regular_lines() -> None:
            if regular_lines:
                paragraphs.append(f"<p>{'<br/>'.join(regular_lines)}</p>")
                regular_lines.clear()

        for line in lines:
            if re.fullmatch(r"\*\s+\*\s+\*", line):
                flush_regular_lines()
                paragraphs.append('<p class="scene-break">* * *</p>')
            else:
                regular_lines.append(_escape_text(line))
        flush_regular_lines()
    return "\n".join(paragraphs)


def _get_chapter_heading_html(title: str, css_class: str = "chapter-title") -> str:
    """Render visible chapter heading unless the title is only for navigation."""
    if (title or "").strip() == "판권":
        return ""
    safe_title = _escape_text(title)
    return f'<h1 class="{css_class}">{safe_title}</h1>'


def _get_illustration_blocks(
    illustration_href: Optional[str],
    illustration_caption: Optional[str],
    illustration_position: str = "head"
) -> tuple[str, str]:
    """
    Generate illustration HTML blocks for chapter pages.

    :return: (head_block, tail_block)
    """
    if not illustration_href:
        return "", ""

    safe_caption = _escape_text(illustration_caption) if illustration_caption else ""
    caption_html = f'<p class="duokan-note">{safe_caption}</p>' if safe_caption else ""
    safe_alt = _escape_text(illustration_caption or "chapter illustration", quote=True)
    safe_href = _escape_text(illustration_href, quote=True)
    block = (
        f'<div class="duokan-image-single">'
        f'<img class="duokan-image" src="{safe_href}" alt="{safe_alt}"/>'
        f'{caption_html}'
        f'</div>'
    )
    normalized_pos = (illustration_position or "head").strip().lower()
    if normalized_pos not in {"head", "tail"}:
        normalized_pos = "head"
    if normalized_pos == "tail":
        return "", block
    return block, ""


def _get_watermark_html(watermark_text: str) -> str:
    """
    Generate watermark HTML.

    :param watermark_text: Watermark text content
    :return: HTML string for watermark
    """
    if not watermark_text:
        return ""

    safe_watermark = _escape_text(watermark_text)
    return f'''
        <div style="position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%); width: 100%;">
            <p style="color: #95a5a6; font-size: 0.8em; text-align: center;">
                {safe_watermark}
            </p>
        </div>'''


def create_volume_page(volume_title: str, file_name: str, chapter_count: int,
                      watermark_text: Optional[str] = None, language: str = "en") -> epub.EpubHtml:
    """
    Create volume/part/book page with modern design.

    :param volume_title: Volume title
    :param file_name: File name
    :param chapter_count: Chapter count
    :param watermark_text: Watermark text (None to disable watermark)
    :return: EpubHtml object
    """
    language = _normalize_epub_language(language)
    volume_page = epub.EpubHtml(title=volume_title, file_name=file_name, lang=language)
    safe_volume_title = _escape_text(volume_title)

    # Determine decorative icon
    if "卷" in volume_title:
        icon = "📖"
    elif "部" in volume_title:
        icon = "📚"
    elif "篇" in volume_title:
        icon = "📜"
    else:
        icon = "📖"

    # Generate watermark HTML
    watermark_html = _get_watermark_html(watermark_text) if watermark_text else ""

    # Create concise volume page content
    volume_page.content = f'''
    <!DOCTYPE html>
    <html lang="{language}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{safe_volume_title}</title>
        <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        <style>
            body {{
                height: 100vh;
                margin: 0;
                padding: 2rem;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                page-break-after: always;
                box-sizing: border-box;
            }}
            .volume-content {{
                text-align: center;
                max-width: 80%;
            }}
        </style>
    </head>
    <body class="chinese-text">
        <div class="volume-content">
            <h1 class="volume-title">{safe_volume_title}</h1>
            <div style="margin-top: 2rem;">
                <div style="font-size: 3em; margin-bottom: 1.5rem;">{icon}</div>
                <p style="color: #2c3e50; font-size: 1.3em; font-weight: 500; margin-bottom: 2rem;">
                </p>
            </div>
        </div>{watermark_html}
    </body>
    </html>
    '''
    
    return volume_page



def create_chapter_page(chapter_title: str, chapter_content: str, file_name: str, section_count: int,
                       watermark_text: Optional[str] = None, illustration_href: Optional[str] = None,
                       illustration_caption: Optional[str] = None,
                       illustration_position: str = "head", language: str = "en") -> epub.EpubHtml:
    """
    Create chapter page (for chapters with sections) with modern design.

    :param chapter_title: Chapter title
    :param chapter_content: Chapter content (usually empty, as content is in sections)
    :param file_name: File name
    :param section_count: Section count
    :param watermark_text: Watermark text (None to disable watermark)
    :return: EpubHtml object
    """
    language = _normalize_epub_language(language)
    chapter_page = epub.EpubHtml(title=chapter_title, file_name=file_name, lang=language)
    safe_chapter_title = _escape_text(chapter_title)
    chapter_heading_html = _get_chapter_heading_html(chapter_title)
    rendered_chapter_content = _render_text_blocks(chapter_content)

    # Generate watermark HTML
    watermark_html = _get_watermark_html(watermark_text) if watermark_text else ""
    illustration_head, illustration_tail = _get_illustration_blocks(
        illustration_href=illustration_href,
        illustration_caption=illustration_caption,
        illustration_position=illustration_position
    )

    # Create elegant chapter page content
    if rendered_chapter_content:
        chapter_page.content = f'''
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_chapter_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            <style>
                body {{
                    height: 100vh;
                    margin: 0;
                    padding: 2rem;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    page-break-after: always;
                    box-sizing: border-box;
                }}
                .chapter-content {{
                    text-align: center;
                    max-width: 80%;
                    margin: 0 auto;
                }}
            </style>
        </head>
        <body class="chinese-text">
            <div class="chapter-content">
                {chapter_heading_html}
                {illustration_head}
                <div style="margin-top: 1.5rem; margin-bottom: 2rem;">
                    {rendered_chapter_content}
                </div>
                {illustration_tail}
                <div style="margin-top: 2rem;">
                    <div style="font-size: 3em; margin-bottom: 1.5rem;">📚</div>
                    <p style="color: #2c3e50; font-size: 1.3em; font-weight: 500;">
                    </p>
                </div>
            </div>{watermark_html}
        </body>
        </html>
        '''
    else:
        chapter_page.content = f'''
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_chapter_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            <style>
                body {{
                    height: 100vh;
                    margin: 0;
                    padding: 2rem;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    page-break-after: always;
                    box-sizing: border-box;
                }}
                .chapter-content {{
                    text-align: center;
                    max-width: 80%;
                }}
            </style>
        </head>
        <body class="chinese-text">
            <div class="chapter-content">
                {chapter_heading_html}
                {illustration_head}
                {illustration_tail}
                <div style="margin-top: 2rem;">
                    <div style="font-size: 3em; margin-bottom: 1.5rem;">📚</div>
                    <p style="color: #2c3e50; font-size: 1.3em; font-weight: 500;">
                    </p>
                </div>
            </div>{watermark_html}
        </body>
        </html>
        '''
    
    return chapter_page



def create_section_page(section_title: str, section_content: str, file_name: str,
                        language: str = "en") -> epub.EpubHtml:
    """
    Create section page with modern design.

    :param section_title: Section title
    :param section_content: Section content
    :param file_name: File name
    :return: EpubHtml object
    """
    language = _normalize_epub_language(language)
    section_page = epub.EpubHtml(title=section_title, file_name=file_name, lang=language)
    safe_section_title = _escape_text(section_title)
    rendered_section_content = _render_text_blocks(section_content)

    if section_title:
        section_page.content = f'''
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_section_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body class="chinese-text">
            <h2 class="section-title">{safe_section_title}</h2>
            <div style="margin-top: 1rem;">
                {rendered_section_content}
            </div>
        </body>
        </html>
        '''
    else:
        # Untitled section (chapter preface)
        section_page.content = f'''
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Chapter Preface</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body class="chinese-text">
            <div style="margin-top: 1rem;">
                {rendered_section_content}
            </div>
        </body>
        </html>
        '''

    return section_page



def create_chapter(title: str, content: str, file_name: str, illustration_href: Optional[str] = None,
                   illustration_caption: Optional[str] = None,
                   illustration_position: str = "head", language: str = "en") -> epub.EpubHtml:
    """
    Create EPUB chapter with modern design.
    """
    language = _normalize_epub_language(language)
    chapter = epub.EpubHtml(title=title, file_name=file_name, lang=language)
    safe_title = _escape_text(title)
    chapter_heading_html = _get_chapter_heading_html(title)
    rendered_content = _render_text_blocks(content)
    illustration_head, illustration_tail = _get_illustration_blocks(
        illustration_href=illustration_href,
        illustration_caption=illustration_caption,
        illustration_position=illustration_position
    )
    
    if rendered_content:
        chapter.content = f'''
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body class="chinese-text">
            {chapter_heading_html}
            {illustration_head}
            <div style="margin-top: 1.5em;">
                {rendered_content}
            </div>
            {illustration_tail}
        </body>
        </html>
        '''
    else:
        chapter.content = f'''
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body class="chinese-text">
            {chapter_heading_html}
            {illustration_head}
            {illustration_tail}
        </body>
        </html>
        '''
    
    chapter.add_link(href="style/nav.css", rel="stylesheet", type="text/css")
    return chapter


def create_serial_episode(title: str, subtitle: str, content: str,
                          file_name: str = "episode.xhtml",
                          language: str = "ko") -> epub.EpubHtml:
    """Create a single serial episode with a distinct title and subtitle."""
    language = _normalize_epub_language(language)
    page = epub.EpubHtml(title=title, file_name=file_name, lang=language)
    safe_title = _escape_text(title)
    safe_subtitle = _escape_text(subtitle)
    rendered_content = _render_text_blocks(content)
    page.content = f'''<!DOCTYPE html>
    <html lang="{language}">
    <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>{safe_title}</title>
    </head>
    <body class="chinese-text">
        <div style="font-size: 1.7em; font-weight: 700; margin: 0em 0em 1.1em 0em;">{safe_title}</div>
        <div style="font-size: 1.25em; font-weight: 600; margin: 0em 0em 2em 0em;">{safe_subtitle}</div>
        <div style="margin-top: 1.5em;">
            {rendered_content}
        </div>
    </body>
    </html>'''
    page.add_link(href="style/nav.css", rel="stylesheet", type="text/css")
    return page
