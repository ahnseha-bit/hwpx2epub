#!/usr/bin/env python3
"""Standalone HWPX -> TXT + EPUB conversion engine."""

import argparse
import html
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from ebooklib import epub
from txt_to_epub.core import (
    _create_epub_book,
    _extract_copyright_metadata,
    _write_epub_file,
    txt_to_epub,
)
from txt_to_epub.css import add_css_style
from txt_to_epub.html_generator import create_chapter, create_serial_episode
from txt_to_epub.parser_config import ParserConfig


def _section_number(filename: str) -> int:
    try:
        return int(Path(filename).stem.replace("section", ""))
    except ValueError:
        return 999999


def _extract_paragraphs(xml_data: bytes) -> list[str]:
    root = ET.fromstring(xml_data)
    paragraphs: list[str] = []
    for element in root.iter():
        if not element.tag.endswith("}p"):
            continue
        parts = [child.text for child in element.iter() if child.tag.endswith("}t") and child.text]
        paragraphs.append("".join(parts))
    return paragraphs


def hwpx_to_txt(hwpx_path: Path, txt_path: Path) -> None:
    if hwpx_path.suffix.lower() != ".hwpx":
        raise ValueError("HWPX 파일을 선택해 주세요.")

    with zipfile.ZipFile(hwpx_path, "r") as archive:
        sections = [
            name for name in archive.namelist()
            if name.startswith("Contents/section") and name.endswith(".xml")
        ]
        if not sections:
            raise ValueError("HWPX 내부에서 본문 XML을 찾지 못했습니다.")
        sections.sort(key=_section_number)
        paragraphs: list[str] = []
        for section in sections:
            paragraphs.extend(_extract_paragraphs(archive.read(section)))

    text = "\n".join(paragraphs)
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    with txt_path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(text)


def apply_copyright_form(text: str, values: dict[str, str], fallback_title: str) -> str:
    """Replace or append a copyright block when the user entered form values."""
    if not any(value.strip() for value in values.values()):
        return text

    existing: dict[str, str] = {}
    block = re.search(r'(?:^|\n)\s*판권\s*\n(?P<body>[\s\S]*?)\s*$', text)
    if block:
        for line in block.group('body').splitlines():
            field = re.match(r'^\s*([^:：]+)\s*[:：]\s*(.*?)\s*$', line)
            if field:
                existing[field.group(1).strip()] = field.group(2).strip()
        text = text[:block.start()].rstrip()

    labels = [
        ('제목', 'title'),
        ('지은이', 'author'),
        ('발행처', 'publisher'),
        ('발행일', 'date'),
        ('UCI', 'uci'),
        ('투고메일', 'submission_email'),
        ('저작권 문구', 'rights'),
    ]
    fallbacks = {
        'title': existing.get('제목', fallback_title),
        'author': existing.get('지은이', existing.get('저자', '')),
        'publisher': existing.get('발행처', ''),
        'date': existing.get('발행일', ''),
        'uci': existing.get('UCI', ''),
        'submission_email': existing.get('투고메일', ''),
        'rights': existing.get('저작권 문구', ''),
    }
    lines = ['판권']
    for label, key in labels:
        value = values.get(key, '').strip() or fallbacks[key]
        lines.append(f'{label}: {value}')
    return f"{text}\n\n" + "\n".join(lines) + "\n"


def build_book_epub(txt_path: Path, cover_path: Path, epub_path: Path) -> None:
    config = ParserConfig(
        custom_chapter_patterns=[
            r"^\d+\s*장\s+[^\r\n]+",
            r"^판권$",
        ],
        ignore_patterns=[
            r"^\s*\*\s*\*\s*\*\s*$",
            r"^\s*목차\s*$",
        ],
        min_chapter_length=0,
        enable_chapter_validation=False,
        enable_watermark=False,
        watermark_text="",
    )
    txt_to_epub(
        txt_file=str(txt_path),
        epub_file=str(epub_path),
        title=txt_path.stem,
        author="",
        cover_image=str(cover_path),
        config=config,
        metadata_overrides={"language": "ko"},
        show_progress=False,
    )


def _copyright_content(metadata: dict[str, str]) -> str:
    fields = [
        ('제목', metadata.get('title', '')),
        ('지은이', metadata.get('author', '')),
        ('발행처', metadata.get('publisher', '')),
        ('발행일', metadata.get('date', '')),
        ('UCI', metadata.get('identifier', '')),
        ('투고메일', metadata.get('submission_email', '')),
        ('저작권 문구', metadata.get('rights', '')),
    ]
    return '\n\n'.join(f'{label}: {value}' for label, value in fields)


def _parse_serial_source(source: str, fallback_title: str) -> tuple[str, str, str, str]:
    """Return (series title, index title, subtitle, body) from the opening lines."""
    copyright_match = re.search(r'(?:^|\n)\s*판권\s*\n[\s\S]*?\s*$', source)
    body_without_copyright = source[:copyright_match.start()].strip() if copyright_match else source.strip()
    lines = body_without_copyright.splitlines()
    nonempty_indexes = [index for index, line in enumerate(lines) if line.strip()]
    if not nonempty_indexes:
        return fallback_title, fallback_title, '본문', ''

    heading_index = nonempty_indexes[0]
    heading = lines[heading_index].strip()
    series_title = re.sub(r'\s+\d{1,4}\s*화\s*$', '', heading).strip() or fallback_title

    if len(nonempty_indexes) >= 2:
        subtitle_index = nonempty_indexes[1]
        subtitle = lines[subtitle_index].strip()
        body_lines = lines[subtitle_index + 1:]
    else:
        subtitle = re.search(r'(\d{1,4}\s*화)\s*$', heading)
        subtitle = subtitle.group(1) if subtitle else '본문'
        body_lines = lines[heading_index + 1:]
    return series_title, heading, subtitle, '\n'.join(body_lines).strip()


def _safe_output_stem(value: str, fallback: str) -> str:
    """Return a filename-safe title while preserving Korean and spaces."""
    cleaned = re.sub(r'[/:\\?*"<>|\x00-\x1f]', '_', value).strip().rstrip('.')
    return cleaned or fallback


def detect_serial_heading(text: str, fallback_title: str) -> str:
    """Extract the first-line serial index title for output naming."""
    normalized = unicodedata.normalize('NFC', text)
    _, heading, _, _ = _parse_serial_source(normalized, fallback_title)
    return heading


def detect_first_heading(text: str, fallback_title: str) -> str:
    """Return the first non-empty manuscript line for book output naming."""
    normalized = unicodedata.normalize('NFC', text)
    for line in normalized.splitlines():
        heading = line.strip()
        if heading:
            return heading
    return fallback_title


def build_serial_epub(txt_path: Path, cover_path: Path, epub_path: Path) -> None:
    """Create a lightweight serial EPUB: cover -> one episode -> copyright."""
    source = unicodedata.normalize('NFC', txt_path.read_text(encoding='utf-8-sig'))
    metadata = _extract_copyright_metadata(source)
    detected_title, index_title, subtitle, episode_body = _parse_serial_source(source, txt_path.stem)
    # In serial manuscripts the first non-empty line is authoritative for the
    # work title; the trailing episode number is removed for EPUB metadata.
    title = detected_title
    author = metadata.get('author', '')

    extra_metadata = {
        'publisher': metadata.get('publisher', ''),
        'date': metadata.get('date', ''),
        'rights': metadata.get('rights', ''),
        'identifier': metadata.get('identifier', ''),
        'submission_email': metadata.get('submission_email', ''),
    }
    book = _create_epub_book(
        title=title,
        author=author,
        cover_image=str(cover_path),
        language='ko',
        metadata=extra_metadata,
    )
    cover_page = book.get_item_with_id('cover')
    episode_page = create_serial_episode(index_title, subtitle, episode_body, 'episode.xhtml', language='ko')
    copyright_page = create_chapter('판권', _copyright_content(metadata), 'copyright.xhtml', language='ko')
    book.add_item(episode_page)
    book.add_item(copyright_page)
    book.toc = [
        epub.Link(cover_page.file_name, '표지', 'cover-link'),
        epub.Link(episode_page.file_name, index_title, 'episode-link'),
        epub.Link(copyright_page.file_name, '판권', 'copyright-link'),
    ]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    add_css_style(book)
    book.spine = [cover_page, episode_page, copyright_page]
    _write_epub_file(str(epub_path), book)


def convert_one(
    hwpx_path: Path,
    cover_path: Path,
    output_dir: Path,
    template: str,
    copyright_values: dict[str, str],
    existing_policy: str,
) -> Optional[tuple[Path, Path]]:
    """Convert one manuscript, or return None when an existing result is skipped."""
    temporary_txt_path = output_dir / f".{hwpx_path.stem}.hwpx-epub-maker.tmp.txt"
    hwpx_to_txt(hwpx_path, temporary_txt_path)
    extracted_text = temporary_txt_path.read_text(encoding='utf-8')
    detected_heading = (
        detect_serial_heading(extracted_text, hwpx_path.stem)
        if template == 'serial'
        else detect_first_heading(extracted_text, hwpx_path.stem)
    )
    output_stem = _safe_output_stem(detected_heading, hwpx_path.stem)
    txt_path = output_dir / f"{output_stem}.txt"
    epub_path = output_dir / f"{output_stem}.epub"
    existing = [path for path in (txt_path, epub_path) if path.exists()]
    if existing and existing_policy == 'skip':
        temporary_txt_path.unlink(missing_ok=True)
        print(f"SKIPPED={hwpx_path.name}", flush=True)
        return None
    if existing and existing_policy == 'error':
        temporary_txt_path.unlink(missing_ok=True)
        raise FileExistsError('이미 존재하는 파일: ' + ', '.join(path.name for path in existing))

    temporary_txt_path.replace(txt_path)
    source_text = txt_path.read_text(encoding='utf-8')
    source_text = apply_copyright_form(source_text, copyright_values, hwpx_path.stem)
    with txt_path.open('w', encoding='utf-8', newline='\n') as output:
        output.write(source_text)
    if template == 'serial':
        build_serial_epub(txt_path, cover_path, epub_path)
    else:
        build_book_epub(txt_path, cover_path, epub_path)
    print(f"TXT={txt_path}", flush=True)
    print(f"EPUB={epub_path}", flush=True)
    return txt_path, epub_path


def main() -> int:
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--hwpx")
    source_group.add_argument("--batch-dir")
    parser.add_argument("--cover", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--publisher", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--uci", default="")
    parser.add_argument("--submission-email", default="")
    parser.add_argument("--rights", default="")
    parser.add_argument("--template", choices=('book', 'serial'), default='book')
    parser.add_argument("--overwrite", action='store_true')
    parser.add_argument("--existing-policy", choices=('error', 'overwrite', 'skip'), default='error')
    args = parser.parse_args()

    cover_path = Path(args.cover).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not cover_path.is_file():
        raise FileNotFoundError(f"표지 파일을 찾을 수 없습니다: {cover_path}")
    if cover_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("표지는 PNG, JPG 또는 WEBP 파일이어야 합니다.")

    output_dir.mkdir(parents=True, exist_ok=True)
    copyright_values = {
        'title': args.title,
        'author': args.author,
        'publisher': args.publisher,
        'date': args.date,
        'uci': args.uci,
        'submission_email': args.submission_email,
        'rights': args.rights,
    }
    policy = 'overwrite' if args.overwrite else args.existing_policy

    if args.batch_dir:
        batch_dir = Path(args.batch_dir).expanduser().resolve()
        if not batch_dir.is_dir():
            raise FileNotFoundError(f"원고 폴더를 찾을 수 없습니다: {batch_dir}")
        manuscripts = sorted(
            (path for path in batch_dir.iterdir() if path.is_file() and path.suffix.lower() == '.hwpx'),
            key=lambda path: unicodedata.normalize('NFC', path.name),
        )
        if not manuscripts:
            raise ValueError("선택한 폴더에 HWPX 파일이 없습니다.")
        completed = skipped = 0
        failures: list[str] = []
        for index, hwpx_path in enumerate(manuscripts, 1):
            print(f"PROGRESS={index}/{len(manuscripts)}|{hwpx_path.name}", flush=True)
            try:
                result = convert_one(hwpx_path, cover_path, output_dir, args.template, copyright_values, policy)
                if result is None:
                    skipped += 1
                else:
                    completed += 1
            except Exception as error:
                failures.append(f"{hwpx_path.name}: {error}")
                print(f"FAILED={hwpx_path.name}|{error}", file=sys.stderr, flush=True)
        print(f"SUMMARY={completed}|{skipped}|{len(failures)}", flush=True)
        if failures:
            raise RuntimeError(f"{len(failures)}개 파일 변환 실패:\n" + '\n'.join(failures))
        return 0

    hwpx_path = Path(args.hwpx).expanduser().resolve()
    if not hwpx_path.is_file():
        raise FileNotFoundError(f"HWPX 파일을 찾을 수 없습니다: {hwpx_path}")
    print("HWPX에서 TXT를 추출하고 있습니다…", flush=True)
    convert_one(hwpx_path, cover_path, output_dir, args.template, copyright_values, policy)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR={error}", file=sys.stderr, flush=True)
        sys.exit(1)
