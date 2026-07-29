"""Unit tests for EPUB parser."""

from __future__ import annotations

import io
import zipfile

import pytest
from app.modules.imports.epub import parse_epub


def _minimal_epub(*, title: str = "Demo Book", author: str = "A. Writer") -> bytes:
    """Build a tiny valid EPUB with one chapter."""
    container = (
        '<?xml version="1.0"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        "<rootfiles>"
        '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>"
    )
    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
  </spine>
</package>
"""
    chapter = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter One</title></head>
<body><p>Once upon a time.</p><p>The end.</p></body></html>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/ch1.xhtml", chapter)
    return buf.getvalue()


@pytest.mark.unit
def test_parse_epub_extracts_metadata_and_chapters() -> None:
    parsed = parse_epub(_minimal_epub())
    assert parsed.title == "Demo Book"
    assert parsed.author == "A. Writer"
    assert len(parsed.chapters) == 1
    assert "Once upon a time" in parsed.chapters[0].text


@pytest.mark.unit
def test_parse_epub_rejects_non_zip() -> None:
    with pytest.raises(ValueError, match="not a ZIP"):
        parse_epub(b"not-an-epub")
