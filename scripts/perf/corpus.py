"""Corpus sintetico deterministico para as medicoes (semente fixa).

Gera arquivos diferentes entre si (para nao cair na duplicidade por hash, D9):
PDF com texto, DOCX e, se o Pillow estiver instalado, PDF digitalizado. Os
trechos do corpus de busca (ate 100.000) saem como JSONL.

Uso: ``python corpus.py --out DIR --upload-25mb --index-10mb --chunks 100000``
"""

from __future__ import annotations

import argparse
import io
import json
import random
import zipfile
from pathlib import Path

SEED = 20261014
MB = 1024 * 1024
WORDS = (
    "politica ferias beneficio reembolso contrato prazo acesso sistema "
    "relatorio cliente fornecedor auditoria seguranca treinamento projeto "
    "orcamento equipe processo norma revisao aprovacao pagamento nota fiscal "
    "viagem despesa home office jornada banco horas saude plano seguro"
).split()


def sentence(rng: random.Random, words: int = 14) -> str:
    # O sufixo hexadecimal aleatorio garante conteudo que o ZIP/PDF nao comprime
    # a quase nada, aproximando o tamanho em disco do tamanho pedido.
    body = " ".join(rng.choice(WORDS) for _ in range(words))
    return f"{body} {rng.getrandbits(48):012x}."


def paragraphs(seed: int, target_chars: int) -> list[str]:
    rng = random.Random(seed)
    out, size = [], 0
    while size < target_chars:
        text = " ".join(sentence(rng) for _ in range(4))
        out.append(text)
        size += len(text) + 1
    return out


def _entry(name: str) -> zipfile.ZipInfo:
    """Entrada do ZIP com data fixa: sem ela o DOCX carrega o horario da geracao e a
    mesma semente gera bytes diferentes (teste instavel na V2 da rc7, 2026-10-21)."""
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def make_docx(path: Path, target_bytes: int, seed: int) -> Path:
    """DOCX minimo valido; cresce em lotes ate o tamanho pedido."""
    chars = max(1000, target_bytes)
    while True:
        body = "".join(
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs(seed, chars)
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                _entry("[Content_Types].xml"),
                '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
            )
            archive.writestr(
                _entry("_rels/.rels"),
                '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
            )
            archive.writestr(
                _entry("word/document.xml"),
                '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                + body
                + "</w:body></w:document>",
            )
        if buffer.tell() >= target_bytes:
            break
        chars = int(chars * max(1.1, target_bytes / max(buffer.tell(), 1)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.getvalue())
    return path


def make_text_pdf(path: Path, target_bytes: int, seed: int) -> Path:
    """PDF com texto (fonte padrao Helvetica), sem compressao, no tamanho pedido."""
    lines = [
        text[i : i + 100]
        for text in paragraphs(seed, target_bytes)
        for i in range(0, len(text), 100)
    ]
    per_page = 45
    objects: list[bytes] = []
    page_ids = []
    font_id = 3
    next_id = 4
    chunks = [lines[i : i + per_page] for i in range(0, len(lines), per_page)]
    for page_lines in chunks:
        stream = "BT /F1 9 Tf 40 800 Td 12 TL\n" + "".join(
            f"({line.replace(chr(92), '').replace('(', '').replace(')', '')}) '\n"
            for line in page_lines
        ) + "ET"
        content_id, page_id = next_id, next_id + 1
        next_id += 2
        data = stream.encode("latin-1", "replace")
        objects.append(
            f"{content_id} 0 obj\n<< /Length {len(data)} >>\nstream\n".encode()
            + data
            + b"\nendstream\nendobj\n"
        )
        objects.append(
            f"{page_id} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>\nendobj\n".encode()
        )
        page_ids.append(page_id)
    head = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(page_ids)} >>\nendobj\n".encode(),
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for obj in head + objects:
        offsets.append(len(body))
        body += obj
    xref = len(body)
    body += f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    body += f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def make_fitting(maker, path: Path, ceiling_bytes: int, seed: int) -> Path:
    """Gera com ``maker`` um arquivo entre 95% e 100% de ``ceiling_bytes``.

    ``make_text_pdf`` e ``make_docx`` passam do tamanho pedido (o envelope do
    formato soma ao texto); aqui o alvo e recalibrado pelo tamanho obtido, para
    quem precisa de um arquivo proximo do limite sem ultrapassa-lo.
    """
    target = int(ceiling_bytes * 0.9)  # o envelope costuma somar cerca de 10%
    for _ in range(8):
        maker(path, target, seed)
        size = path.stat().st_size
        if 0.95 * ceiling_bytes <= size <= ceiling_bytes:
            return path
        target = max(1000, int(target * 0.975 * ceiling_bytes / size))
    raise RuntimeError(f"nao foi possivel ajustar {path.name} abaixo de {ceiling_bytes} bytes")


def make_scanned_pdf(path: Path, pages: int, seed: int) -> Path:
    """PDF so de imagem (exige Pillow); simula documento digitalizado."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise SystemExit("Pillow e necessario para o PDF digitalizado.") from exc
    rng = random.Random(seed)
    images = []
    for _ in range(pages):
        image = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(image)
        for row in range(40):
            draw.text((80, 60 + row * 40), sentence(rng, 10), fill="black")
        images.append(image)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, "PDF", resolution=150, save_all=True, append_images=images[1:])
    return path


def write_chunks(path: Path, count: int, seed: int = SEED) -> Path:
    """Um JSON por linha: ``{"id", "document", "text"}`` (100.000 no maximo)."""
    if not 0 < count <= 100_000:
        raise ValueError("count must be between 1 and 100000.")
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for index in range(count):
            record = {
                "id": f"chunk-{index:06d}",
                "document": f"doc-{index // 50:05d}",
                "text": " ".join(sentence(rng) for _ in range(3)),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--upload-25mb", action="store_true", help="PDF e DOCX de 24 MB")
    parser.add_argument("--index-10mb", action="store_true", help="PDF e DOCX de 10 MB (+ digitalizado)")
    parser.add_argument("--chunks", type=int, default=0)
    parser.add_argument("--count", type=int, default=1, help="arquivos por tipo")
    args = parser.parse_args(argv)
    for n in range(args.count):
        if args.upload_25mb:
            make_text_pdf(args.out / f"upload-{n:02d}.pdf", 24 * MB, SEED + n)
            make_docx(args.out / f"upload-{n:02d}.docx", 24 * MB, SEED + 1000 + n)
        if args.index_10mb:
            make_text_pdf(args.out / f"index-{n:02d}.pdf", 10 * MB, SEED + 2000 + n)
            make_docx(args.out / f"index-{n:02d}.docx", 10 * MB, SEED + 3000 + n)
            make_scanned_pdf(args.out / f"scan-{n:02d}.pdf", 10, SEED + 4000 + n)
    if args.chunks:
        write_chunks(args.out / "chunks.jsonl", args.chunks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
