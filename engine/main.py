#!/usr/bin/env python3
"""Standalone HWPX -> TXT + EPUB conversion engine."""

import argparse
import html
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Optional

from ebooklib import epub
from PIL import Image
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
        ('투고문의', 'submission_email'),
        ('저작권 문구', 'rights'),
    ]
    fallbacks = {
        'title': existing.get('제목', fallback_title),
        'author': existing.get('지은이', existing.get('저자', '')),
        'publisher': existing.get('발행처', ''),
        'date': existing.get('발행일', ''),
        'uci': existing.get('UCI', ''),
        'submission_email': existing.get('투고문의', existing.get('투고메일', '')),
        'rights': existing.get('저작권 문구', ''),
    }
    fields = []
    for label, key in labels:
        value = values.get(key, '').strip() or fallbacks[key]
        fields.append(f'{label}: {value}')
    # Keep copyright fields as separate paragraphs. This makes book EPUBs use
    # the same one-blank-line spacing as the dedicated serial copyright page.
    return f"{text}\n\n판권\n" + "\n\n".join(fields) + "\n"


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
        ('투고문의', metadata.get('submission_email', '')),
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


def detect_episode_number(text: str) -> Optional[int]:
    """Read an episode number such as 1화, 01화, 001화 or 제1화 from the first line."""
    heading = detect_first_heading(text, '')
    match = re.search(r'(?:제\s*)?0*(\d{1,4})\s*화(?:\s|$)', heading)
    return int(match.group(1)) if match else None


def optimize_cover(source: Path, destination: Path, platform: str) -> None:
    """Create a compact sRGB JPEG cover suitable for the selected storefront."""
    target_width = 1080 if platform == 'kakao' else 1120
    max_bytes = 500 * 1024 if platform == 'kakao' else 450 * 1024
    with Image.open(source) as opened:
        image = opened.convert('RGBA')
        background = Image.new('RGB', image.size, 'white')
        background.paste(image, mask=image.getchannel('A'))
        height = max(1, round(background.height * target_width / background.width))
        background = background.resize((target_width, height), Image.Resampling.LANCZOS)
        for quality in range(90, 39, -5):
            buffer = BytesIO()
            background.save(buffer, format='JPEG', quality=quality, optimize=True, progressive=False, dpi=(72, 72))
            if buffer.tell() <= max_bytes or quality == 40:
                destination.write_bytes(buffer.getvalue())
                return


def _rewrite_epub_for_distribution(epub_path: Path, platform: str) -> None:
    """Convert EbookLib's package to a conservative EPUB 2 layout and storefront names."""
    replacement_names = {}
    if platform == 'ridi':
        replacement_names = {
            'EPUB/cover.xhtml': 'EPUB/cover.html',
            'EPUB/copyright.xhtml': 'EPUB/copyright.html',
        }

    with zipfile.ZipFile(epub_path, 'r') as source:
        entries = [(item, source.read(item.filename)) for item in source.infolist()]

    temporary = epub_path.with_suffix('.rewrite.tmp')
    with zipfile.ZipFile(temporary, 'w') as target:
        target.writestr('mimetype', b'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        for item, data in entries:
            name = item.filename
            if name == 'mimetype' or name == 'EPUB/nav.xhtml':
                continue
            new_name = replacement_names.get(name, name)
            if name.endswith(('.opf', '.ncx', '.xhtml', '.html')):
                text = data.decode('utf-8')
                for old, new in replacement_names.items():
                    text = text.replace(Path(old).name, Path(new).name)
                if name.endswith('.opf'):
                    text = re.sub(r' version="3\.0"', ' version="2.0"', text, count=1)
                    text = re.sub(r' prefix="[^"]*"', '', text, count=1)
                    text = re.sub(r'\s*<meta property="dcterms:modified">.*?</meta>', '', text)
                    text = re.sub(r'\s*<item[^>]+(?:id="nav"|properties="nav")[^>]*/>', '', text)
                    text = re.sub(r' properties="[^"]*"', '', text)
                elif name.endswith(('.xhtml', '.html')):
                    text = text.replace('<!DOCTYPE html>', '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">')
                    text = re.sub(r' xmlns:epub="[^"]*"', '', text)
                    text = re.sub(r' epub:prefix="[^"]*"', '', text)
                    text = re.sub(r' epub:type="[^"]*"', '', text)
                    text = re.sub(r' role="[^"]*"', '', text)
                    text = re.sub(r' aria-label="[^"]*"', '', text)
                    text = re.sub(r'<nav([^>]*)>', r'<div\1>', text)
                    text = text.replace('</nav>', '</div>')
                data = text.encode('utf-8')
            target.writestr(new_name, data, compress_type=zipfile.ZIP_DEFLATED)
    temporary.replace(epub_path)


def validate_distribution_epub(epub_path: Path, platform: str) -> None:
    """Validate package structure and storefront size/image recommendations."""
    if platform == 'ridi' and epub_path.stat().st_size > 1024 * 1024:
        raise ValueError(f'리디북스 EPUB 전체 용량이 1MB를 초과합니다: {epub_path.stat().st_size / 1024:.0f}KB')
    with zipfile.ZipFile(epub_path) as archive:
        items = archive.infolist()
        names = archive.namelist()
        if not items or items[0].filename != 'mimetype':
            raise ValueError('EPUB 형식 오류: mimetype 파일이 첫 번째 항목이 아닙니다.')
        mimetype = archive.read('mimetype') if 'mimetype' in names else b''
        if mimetype != b'application/epub+zip' or archive.getinfo('mimetype').compress_type != zipfile.ZIP_STORED:
            raise ValueError('EPUB 형식 오류: mimetype 파일의 내용 또는 압축 방식이 올바르지 않습니다.')
        if len(names) != len(set(names)):
            raise ValueError('EPUB 형식 오류: ZIP 패키지에 중복 파일명이 있습니다.')

        container_name = 'META-INF/container.xml'
        if container_name not in names:
            raise ValueError('EPUB 형식 오류: META-INF/container.xml이 없습니다.')
        container = ET.fromstring(archive.read(container_name))
        rootfile = next((node for node in container.iter() if node.tag.endswith('}rootfile')), None)
        opf_name = rootfile.get('full-path', '') if rootfile is not None else ''
        if not opf_name or opf_name not in names:
            raise ValueError('EPUB 형식 오류: container.xml이 가리키는 OPF 파일이 없습니다.')

        opf = ET.fromstring(archive.read(opf_name))
        if opf.get('version') != '2.0':
            raise ValueError(f'리디·카카오 호환 EPUB 2.0이 아닙니다: OPF version={opf.get("version", "없음")}')
        opf_ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
        manifest = {
            node.get('id', ''): node.get('href', '')
            for node in opf.findall('.//opf:manifest/opf:item', opf_ns)
        }
        opf_dir = PurePosixPath(opf_name).parent
        for href in manifest.values():
            target = str(opf_dir / href.split('#', 1)[0])
            if href and target not in names:
                raise ValueError(f'EPUB 형식 오류: OPF manifest 파일이 없습니다: {target}')
        spine_refs = [node.get('idref', '') for node in opf.findall('.//opf:spine/opf:itemref', opf_ns)]
        missing_refs = [ref for ref in spine_refs if ref not in manifest]
        if missing_refs:
            raise ValueError('EPUB 형식 오류: spine이 없는 manifest ID를 참조합니다: ' + ', '.join(missing_refs))
        if platform == 'ridi' and len(spine_refs) > 250:
            print(f'WARNING=리디북스 권장 spine HTML 개수 250개를 초과합니다: {len(spine_refs)}개', flush=True)
        for field in ('title', 'identifier', 'language'):
            if opf.find(f'.//dc:{field}', opf_ns) is None:
                raise ValueError(f'EPUB 형식 오류: 필수 메타데이터 dc:{field}가 없습니다.')

        for item in archive.infolist():
            if item.filename.endswith(('.xml', '.opf', '.ncx', '.xhtml', '.html')):
                try:
                    ET.fromstring(archive.read(item.filename))
                except ET.ParseError as error:
                    raise ValueError(f'EPUB XML 형식 오류: {item.filename}: {error}') from error
            if item.filename.endswith(('.xhtml', '.html')):
                if item.file_size > 300 * 1024:
                    raise ValueError(f'{platform} HTML 최대 용량 300KB를 초과합니다: {item.filename}')
                if platform == 'ridi' and item.file_size > 150 * 1024:
                    print(f'WARNING=리디북스 권장 HTML 용량 150KB를 초과합니다: {item.filename}', flush=True)
            if platform == 'kakao' and item.filename.lower().endswith(('.jpg', '.jpeg', '.png')) and item.file_size > 500 * 1024:
                raise ValueError(f'카카오페이지 이미지 용량이 500KB를 초과합니다: {item.filename}')
            if item.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                if not re.fullmatch(r'[A-Za-z0-9._-]+', PurePosixPath(item.filename).name):
                    raise ValueError(f'EPUB 이미지 파일명은 영문·숫자를 사용해야 합니다: {item.filename}')
                with Image.open(BytesIO(archive.read(item.filename))) as image:
                    if image.mode not in {'RGB', 'RGBA'}:
                        raise ValueError(f'EPUB 이미지는 RGB 계열이어야 합니다: {item.filename} ({image.mode})')
                    if platform == 'ridi' and image.width < 1080:
                        print(f'WARNING=리디북스 권장 이미지 폭 1080px보다 작습니다: {item.filename} ({image.width}px)', flush=True)
                    if 'cover' in PurePosixPath(item.filename).stem.lower():
                        ratio = image.height / image.width
                        if abs(ratio - 1.45) > 0.08:
                            print(f'WARNING=표지 비율이 리디 권장 1:1.45와 다릅니다: 1:{ratio:.2f}', flush=True)

        for ncx_name in (name for name in names if name.endswith('.ncx')):
            ncx = ET.fromstring(archive.read(ncx_name))
            ncx_dir = PurePosixPath(ncx_name).parent
            for content in (node for node in ncx.iter() if node.tag.endswith('}content')):
                src = content.get('src', '').split('#', 1)[0]
                if src and str(ncx_dir / src) not in names:
                    raise ValueError(f'EPUB NCX 목차가 없는 파일을 참조합니다: {src}')


def build_serial_epub(
    txt_path: Path,
    cover_path: Optional[Path],
    epub_path: Path,
    include_cover_page: bool = True,
    include_copyright: bool = True,
) -> None:
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
        cover_image=str(cover_path) if cover_path else None,
        language='ko',
        metadata=extra_metadata,
    )
    cover_page = book.get_item_with_id('cover') if cover_path else None
    episode_page = create_serial_episode(index_title, subtitle, episode_body, 'episode.xhtml', language='ko')
    book.add_item(episode_page)
    copyright_page = None
    if include_copyright:
        copyright_page = create_chapter('판권', _copyright_content(metadata), 'copyright.xhtml', language='ko')
        book.add_item(copyright_page)
    book.toc = []
    if cover_page and include_cover_page:
        book.toc.append(epub.Link(cover_page.file_name, '표지', 'cover-link'))
    book.toc.append(epub.Link(episode_page.file_name, index_title, 'episode-link'))
    if copyright_page:
        book.toc.append(epub.Link(copyright_page.file_name, '판권', 'copyright-link'))
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    add_css_style(book)
    book.spine = ([cover_page] if cover_page and include_cover_page else []) + [episode_page] + ([copyright_page] if copyright_page else [])
    _write_epub_file(str(epub_path), book)


def convert_one(
    hwpx_path: Path,
    cover_path: Path,
    output_dir: Path,
    template: str,
    copyright_values: dict[str, str],
    existing_policy: str,
    platform: str,
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
    optimized_cover = output_dir / f'.{output_stem}.optimized-cover.jpg'
    episode_number = detect_episode_number(source_text) if template == 'serial' else None
    omit_ridi_extras = platform == 'ridi' and template == 'serial' and episode_number is not None and episode_number >= 2
    if not omit_ridi_extras:
        optimize_cover(cover_path, optimized_cover, platform)
    if template == 'serial':
        build_serial_epub(
            txt_path,
            None if omit_ridi_extras else optimized_cover,
            epub_path,
            include_cover_page=not omit_ridi_extras,
            include_copyright=not omit_ridi_extras,
        )
    else:
        build_book_epub(txt_path, optimized_cover, epub_path)
    optimized_cover.unlink(missing_ok=True)
    _rewrite_epub_for_distribution(epub_path, platform)
    validate_distribution_epub(epub_path, platform)
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
    parser.add_argument("--platform", choices=('kakao', 'ridi'), default='kakao')
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
                result = convert_one(hwpx_path, cover_path, output_dir, args.template, copyright_values, policy, args.platform)
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
    convert_one(hwpx_path, cover_path, output_dir, args.template, copyright_values, policy, args.platform)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR={error}", file=sys.stderr, flush=True)
        sys.exit(1)
