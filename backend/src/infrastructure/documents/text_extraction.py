from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

_SUPPORTED_CONTENT_TYPES_BY_SUFFIX = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".markdown": {"text/markdown", "text/plain"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".doc": {"application/msword"},
}
_SUPPORTED_SUFFIXES = set(_SUPPORTED_CONTENT_TYPES_BY_SUFFIX.keys())


def extract_supported_text(
    *,
    filename: str | None,
    content_type: str | None,
    raw_content: bytes,
) -> str:
    document_type = resolve_document_type(filename, content_type)
    if document_type is None:
        raise ValueError(
            "unsupported file format. Supported formats: "
            ".txt, .md, .markdown, .pdf, .doc, .docx"
        )
    if not raw_content:
        raise ValueError("uploaded file is empty.")

    extractor = _EXTRACTORS[document_type]
    text = extractor(raw_content)
    normalized = text.strip()
    if not normalized:
        raise ValueError("uploaded file does not contain text content.")
    return normalized


def resolve_document_type(
    filename: str | None,
    content_type: str | None,
) -> str | None:
    suffix = Path(filename or "").suffix.lower()
    normalized_content_type = (
        (content_type or "").lower().split(";")[0].strip()
    )

    if suffix:
        if suffix not in _SUPPORTED_SUFFIXES:
            return None
        if not normalized_content_type:
            return suffix
        expected_content_types = _SUPPORTED_CONTENT_TYPES_BY_SUFFIX[suffix]
        if normalized_content_type in expected_content_types:
            return suffix
        if normalized_content_type in {
            "application/octet-stream",
            "binary/octet-stream",
        }:
            return suffix
        return suffix

    if not normalized_content_type:
        return None

    for (
        candidate_suffix,
        allowed_types,
    ) in _SUPPORTED_CONTENT_TYPES_BY_SUFFIX.items():
        if normalized_content_type in allowed_types:
            return candidate_suffix
    return None


def _extract_plain_text(raw_content: bytes) -> str:
    try:
        return raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("text files must be UTF-8 encoded.") from exc


def _extract_pdf_text(raw_content: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdf dependency is required to process PDF files."
        ) from exc

    reader = PdfReader(io.BytesIO(raw_content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx_text(raw_content: bytes) -> str:
    try:
        from docx import Document as DocxDocument  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "python-docx dependency is required to process DOCX files."
        ) from exc

    document = DocxDocument(io.BytesIO(raw_content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_doc_text(raw_content: bytes) -> str:
    with tempfile.TemporaryDirectory(prefix="nexus-doc-extract-") as temp_dir:
        temp_path = Path(temp_dir)
        source_file = temp_path / "upload.doc"
        source_file.write_bytes(raw_content)

        for extractor in (
            _run_antiword,
            _run_catdoc,
            _run_libreoffice_convert,
        ):
            extracted = extractor(source_file, temp_path)
            if extracted and extracted.strip():
                return extracted
    raise RuntimeError(
        "unable to extract .doc content. "
        "Install antiword/catdoc or LibreOffice in the runtime environment."
    )


def _run_antiword(source_file: Path, _: Path) -> str | None:
    if shutil.which("antiword") is None:
        return None
    completed = subprocess.run(
        ["antiword", str(source_file)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _run_catdoc(source_file: Path, _: Path) -> str | None:
    if shutil.which("catdoc") is None:
        return None
    completed = subprocess.run(
        ["catdoc", str(source_file)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _run_libreoffice_convert(source_file: Path, temp_dir: Path) -> str | None:
    libreoffice_cmd = shutil.which("soffice") or shutil.which("libreoffice")
    if libreoffice_cmd is None:
        return None
    completed = subprocess.run(
        [
            libreoffice_cmd,
            "--headless",
            "--convert-to",
            "txt:Text",
            "--outdir",
            str(temp_dir),
            str(source_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    converted_file = temp_dir / f"{source_file.stem}.txt"
    if not converted_file.exists():
        return None
    try:
        return converted_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return converted_file.read_text(encoding="latin-1", errors="ignore")


_EXTRACTORS: dict[str, Callable[[bytes], str]] = {
    ".txt": _extract_plain_text,
    ".md": _extract_plain_text,
    ".markdown": _extract_plain_text,
    ".pdf": _extract_pdf_text,
    ".docx": _extract_docx_text,
    ".doc": _extract_doc_text,
}
