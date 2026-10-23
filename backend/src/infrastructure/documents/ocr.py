"""OCR local de paginas de PDF sem camada de texto (RF-53, RNF-26, D2).

Usa os programas ``pdftoppm`` (Poppler) e ``tesseract`` instalados na imagem,
chamados por processo: nenhuma dependencia Python nova e nenhum dado sai do
container.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.domain import TransientServiceError, UnreadableDocumentError

logger = logging.getLogger(__name__)

DEFAULT_OCR_LANGUAGES = "por+eng"
# fix-10: PDF digitalizado grande demais prende o worker por horas.
DEFAULT_OCR_MAX_PAGES = 200
# Resolucao recomendada pela documentacao do Tesseract para texto impresso.
_RENDER_DPI = 300
_LANGUAGES = re.compile(r"^[A-Za-z_]+(?:\+[A-Za-z_]+)*$")


class OcrUnavailableError(ValueError):
    """Pagina sem texto e OCR ausente: o documento nao pode ser indexado."""


class TesseractPdfOcr:
    """Converte uma pagina do PDF em imagem e a reconhece com o Tesseract."""

    def __init__(
        self,
        *,
        languages: str = DEFAULT_OCR_LANGUAGES,
        timeout_seconds: int = 180,
        max_pages: int = DEFAULT_OCR_MAX_PAGES,
    ) -> None:
        if not _LANGUAGES.match(languages):
            raise ValueError(
                "OCR_LANGUAGES must look like 'por+eng' (Tesseract language codes)."
            )
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if max_pages <= 0:
            raise ValueError("max_pages must be positive.")
        self._languages = languages
        self._max_pages = max_pages
        self._timeout = timeout_seconds

    @property
    def max_pages(self) -> int:
        """Maximo de paginas sem texto que o documento pode ter."""
        return self._max_pages

    @property
    def languages(self) -> str:
        return self._languages

    def recognize_page(self, pdf_content: bytes, page_number: int) -> str:
        """Texto da pagina ``page_number`` (a partir de 1)."""
        if page_number < 1:
            raise ValueError("page_number must start at 1.")
        if shutil.which("pdftoppm") is None or shutil.which("tesseract") is None:
            raise OcrUnavailableError(
                "the PDF has pages without text and OCR is not installed."
            )
        with tempfile.TemporaryDirectory(prefix="nexus-ocr-") as directory:
            workdir = Path(directory)
            source = workdir / "source.pdf"
            source.write_bytes(pdf_content)
            image = self._render(source, page_number, workdir / "page")
            return self._recognize(image)

    def _render(self, source: Path, page_number: int, output_base: Path) -> Path:
        self._run(
            [
                "pdftoppm",
                "-r",
                str(_RENDER_DPI),
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-png",
                "-singlefile",
                str(source),
                str(output_base),
            ]
        )
        image = output_base.with_suffix(".png")
        if not image.is_file():
            raise ValueError(f"could not render PDF page {page_number}.")
        return image

    def _recognize(self, image: Path) -> str:
        result = self._run(
            ["tesseract", str(image), "stdout", "-l", self._languages]
        )
        return result.stdout.decode("utf-8", errors="replace")

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            logger.warning(
                "ocr.command_timeout",
                extra={"command": command[0], "timeout": self._timeout},
            )
            # Pagina pesada ou maquina ocupada: uma nova tentativa pode passar.
            raise TransientServiceError(
                f"{command[0]} did not finish within {self._timeout} seconds."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace").strip()
            logger.warning(
                "ocr.command_failed",
                extra={"command": command[0], "stderr": stderr[-500:]},
            )
            # Pagina ilegivel ou idioma ausente: repetir nao resolve (C1).
            raise UnreadableDocumentError(
                f"{command[0]} failed: {stderr[-200:]}"
            ) from exc
