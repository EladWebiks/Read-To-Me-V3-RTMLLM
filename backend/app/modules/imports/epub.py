"""EPUB parsing — extract metadata, cover, and chapter text from .epub bytes."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

# Cover resize targets (same spirit as v2).
_COVER_MAX_WIDTH = 800
_COVER_MAX_HEIGHT = 1200
_COVER_QUALITY = 85

# OPF / Dublin Core namespaces
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

# Basename stems to skip (front matter, nav, notes)
SKIP_BASENAMES = frozenset(
    {
        "front-cover",
        "title-page",
        "table-of-contents",
        "toc",
        "nav",
        "cover",
        "notes",
        "notes-page",
    }
)


@dataclass
class ParsedChapter:
    title: str
    text: str


@dataclass
class ParsedEpub:
    title: str = ""
    author: str = ""
    language: str = "en"
    cover: bytes = b""
    chapters: list[ParsedChapter] = field(default_factory=list)


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_child(parent: ET.Element, local: str) -> ET.Element | None:
    for child in parent:
        if _strip_ns(child.tag) == local:
            return child
    return None


def _find_children(parent: ET.Element, local: str) -> list[ET.Element]:
    return [c for c in parent if _strip_ns(c.tag) == local]


def _find_desc(parent: ET.Element, local: str) -> ET.Element | None:
    for elem in parent.iter():
        if _strip_ns(elem.tag) == local:
            return elem
    return None


def _normalize_author(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^Author:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _resolve_path(base_dir: str, href: str) -> str:
    """Resolve OPF-relative href to a zip-internal posix path."""
    combined = f"{base_dir}/{href}" if base_dir else href
    parts: list[str] = []
    for part in combined.replace("\\", "/").split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part and part != ".":
            parts.append(part)
    return "/".join(parts)


def _should_skip_basename(href: str) -> bool:
    stem = PurePosixPath(href.split("?")[0]).stem.lower()
    return stem in SKIP_BASENAMES


def _image_to_jpeg_bytes(data: bytes) -> bytes:
    try:
        from PIL import Image
        from PIL.Image import Resampling

        with Image.open(io.BytesIO(data)) as opened:
            rgb = opened.convert("RGB")
        w, h = rgb.size
        if w > _COVER_MAX_WIDTH or h > _COVER_MAX_HEIGHT:
            ratio = min(_COVER_MAX_WIDTH / w, _COVER_MAX_HEIGHT / h)
            rgb = rgb.resize((round(w * ratio), round(h * ratio)), Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=_COVER_QUALITY)
        return buf.getvalue()
    except Exception:
        return b""


def _extract_cover(
    zf: zipfile.ZipFile,
    opf_root: ET.Element,
    manifest: dict[str, dict[str, str]],
    opf_dir: str,
) -> bytes:
    cover_id = None
    metadata = _find_child(opf_root, "metadata")
    if metadata is not None:
        for meta in _find_children(metadata, "meta"):
            if meta.attrib.get("name") == "cover":
                cover_id = meta.attrib.get("content")
                break

    if not cover_id:
        for item_id, info in manifest.items():
            if "cover-image" in info.get("properties", ""):
                cover_id = item_id
                break

    if not cover_id or cover_id not in manifest:
        return b""

    href = manifest[cover_id]["href"]
    path = _resolve_path(opf_dir, href)
    try:
        raw = zf.read(path)
    except KeyError:
        return b""
    return _image_to_jpeg_bytes(raw)


def _parse_ncx_titles(zf: zipfile.ZipFile, ncx_href: str, opf_dir: str) -> dict[str, str]:
    """Map normalized content href -> nav label."""
    path = _resolve_path(opf_dir, ncx_href)
    try:
        raw = zf.read(path)
    except KeyError:
        return {}

    root = ET.fromstring(raw)
    titles: dict[str, str] = {}

    for nav_point in root.iter():
        if _strip_ns(nav_point.tag) != "navPoint":
            continue
        label_el = None
        content_el = None
        for child in nav_point:
            local = _strip_ns(child.tag)
            if local == "navLabel":
                label_el = child
            elif local == "content":
                content_el = child
        if label_el is None or content_el is None:
            continue
        text_el = _find_child(label_el, "text")
        label = (text_el.text or "").strip() if text_el is not None else ""
        if not label:
            continue
        src = content_el.attrib.get("src", "")
        if not src:
            continue
        # Normalize: basename path for lookup
        key = PurePosixPath(src.split("#")[0]).as_posix()
        titles[key] = label
        # Also store full resolved path suffix
        resolved = _resolve_path(opf_dir, src.split("#")[0])
        titles[resolved] = label
        titles[PurePosixPath(resolved).name] = label

    return titles


def _html_to_text(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    for tag in soup.select(".chapter-title, .chapter-title-wrap"):
        tag.decompose()

    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)

    if paragraphs:
        return "\n\n".join(paragraphs)

    body = soup.find("body") or soup
    raw = body.get_text("\n", strip=True)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return "\n\n".join(lines)


def _lookup_title(href: str, path: str, ncx_titles: dict[str, str], fallback_index: int) -> str:
    basename = PurePosixPath(href.split("#")[0]).name
    for key in (path, href.split("#")[0], basename):
        if key in ncx_titles:
            return ncx_titles[key]
    return f"Chapter {fallback_index}"


def parse_epub(data: bytes) -> ParsedEpub:
    """Parse EPUB bytes into metadata and ordered chapter list."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid EPUB file (not a ZIP archive)") from exc

    with zf:
        try:
            container_xml = zf.read("META-INF/container.xml")
        except KeyError as exc:
            raise ValueError("Invalid EPUB: missing META-INF/container.xml") from exc

        container = ET.fromstring(container_xml)
        rootfile = _find_desc(container, "rootfile")
        if rootfile is None:
            raise ValueError("Invalid EPUB: no rootfile in container.xml")

        opf_path = rootfile.attrib.get("full-path", "")
        if not opf_path:
            raise ValueError("Invalid EPUB: empty OPF path")

        opf_dir = str(PurePosixPath(opf_path).parent)
        if opf_dir == ".":
            opf_dir = ""

        try:
            opf_bytes = zf.read(opf_path)
        except KeyError as exc:
            raise ValueError(f"Invalid EPUB: OPF not found at {opf_path}") from exc

        opf_root = ET.fromstring(opf_bytes)

        # Metadata
        result = ParsedEpub()
        metadata = _find_child(opf_root, "metadata")
        if metadata is not None:
            for elem in metadata:
                local = _strip_ns(elem.tag)
                text = (elem.text or "").strip()
                if local == "title" and text:
                    result.title = text
                elif local == "creator" and text and not result.author:
                    result.author = _normalize_author(text)
                elif local == "language" and text:
                    result.language = text

        # Manifest
        manifest: dict[str, dict[str, str]] = {}
        manifest_el = _find_child(opf_root, "manifest")
        if manifest_el is not None:
            for item in _find_children(manifest_el, "item"):
                item_id = item.attrib.get("id", "")
                if item_id:
                    manifest[item_id] = {
                        "href": item.attrib.get("href", ""),
                        "media_type": item.attrib.get("media-type", ""),
                        "properties": item.attrib.get("properties", ""),
                    }

        result.cover = _extract_cover(zf, opf_root, manifest, opf_dir)

        # NCX titles
        spine_el = _find_child(opf_root, "spine")
        ncx_titles: dict[str, str] = {}
        if spine_el is not None:
            toc_id = spine_el.attrib.get("toc")
            if toc_id and toc_id in manifest:
                ncx_href = manifest[toc_id]["href"]
                ncx_titles = _parse_ncx_titles(zf, ncx_href, opf_dir)

        # Spine chapters
        if spine_el is None:
            raise ValueError("Invalid EPUB: missing spine")

        chapter_index = 0
        for itemref in _find_children(spine_el, "itemref"):
            idref = itemref.attrib.get("idref", "")
            linear = itemref.attrib.get("linear", "yes")
            if linear == "no":
                continue
            if idref not in manifest:
                continue

            href = manifest[idref]["href"]
            media_type = manifest[idref]["media_type"]
            if _should_skip_basename(href):
                continue
            if "html" not in media_type and not href.lower().endswith((".html", ".htm", ".xhtml")):
                continue

            path = _resolve_path(opf_dir, href)
            try:
                html_bytes = zf.read(path)
            except KeyError:
                continue

            text = _html_to_text(html_bytes)
            if not text.strip():
                continue

            chapter_index += 1
            soup = BeautifulSoup(html_bytes, "html.parser")
            title_tag = soup.find("title")
            html_title = (title_tag.get_text(strip=True) if title_tag else "") or ""
            title = _lookup_title(href, path, ncx_titles, chapter_index)
            if title.startswith("Chapter ") and html_title and "Chapter" in html_title:
                title = html_title

            result.chapters.append(ParsedChapter(title=title, text=text))

        if not result.chapters:
            raise ValueError("EPUB contains no readable chapters (DRM or unsupported layout?)")

        return result
