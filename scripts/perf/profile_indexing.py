"""V7: tempo de cada etapa da indexacao de um arquivo, sem fila nem banco.

Diagnostico da RNF-02 (ensaio de 2026-10-22: 10 MB em 145 a 330 s). Roda no container
do worker, com os mesmos adaptadores da ingestao (``build_document_indexer``):

  docker compose run --rm -v ./scripts:/app/scripts:ro -v ./docs/qa/relatorios/<pasta>:/app/out \
    worker python /app/scripts/perf/profile_indexing.py /app/out/corpus/index-00.pdf

Mede extracao, fragmentacao, vetor denso e vetor esparso; nao grava no Qdrant.
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from pathlib import Path


def profile(path: Path) -> None:
    from src.infrastructure.composition import build_document_indexer

    indexer = build_document_indexer()
    raw = path.read_bytes()
    marks = [("inicio", time.perf_counter())]
    extracted = indexer._extractor.extract(filename=path.name, content_type=None, raw_content=raw)
    marks.append(("extracao", time.perf_counter()))
    chunks = indexer._chunker.chunk(extracted)
    marks.append(("fragmentacao", time.perf_counter()))
    texts = [chunk.text for chunk in chunks]
    indexer._embedding_gateway.embed_documents(texts)
    marks.append(("vetor denso", time.perf_counter()))
    indexer._sparse_embedding_gateway.embed_documents(texts)
    marks.append(("vetor esparso", time.perf_counter()))
    chars = sum(len(block.text) for block in extracted.blocks)
    print(f"arquivo: {path.name} ({len(raw) / 1024 / 1024:.1f} MB)")
    print(f"texto extraido: {chars} caracteres em {len(extracted.blocks)} blocos")
    print(
        f"trechos: {len(texts)} (media de {statistics.mean(len(t) for t in texts):.0f} caracteres)"
        if texts else "trechos: 0"
    )
    for (_, before), (name, after) in zip(marks, marks[1:]):
        print(f"  {name:<14} {after - before:8.1f} s")
    print(f"  {'total':<14} {marks[-1][1] - marks[0][1]:8.1f} s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args(argv)
    try:
        import torch

        print(f"CPUs: {os.cpu_count()}, threads do torch: {torch.get_num_threads()}")
    except ImportError:  # pragma: no cover
        print(f"CPUs: {os.cpu_count()}")
    for path in args.files:
        profile(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
