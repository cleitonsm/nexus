"""SPEC-018 (T10): documentos ficticios para validar o resumidor (CT-151, CT-152).

Gera, so com conteudo inventado:

- ``contrato-ficticio.docx``: contrato de prestacao de servicos com clausulas, valores e prazos;
- ``relatorio-ficticio.pdf``: relatorio com paginas de texto e uma pagina so em imagem (OCR);
- ``ata-ficticia.txt``: ata de reuniao em texto simples;
- ``extenso-ficticio.pdf``: documento perto do teto (alvo de 38.000 tokens);
- ``acima-do-teto-ficticio.docx``: documento acima do teto (alvo de 46.000 tokens).

A contagem usa o tokenizador local do Nexus (o mesmo do worker, RN-60). Execute dentro do
container do backend, que tem ``python-docx``, ``pypdf``, ``Pillow`` e o modelo:

    docker compose run --rm -v ./scripts:/app/scripts:ro -v ./tmp/resumidor:/out backend \\
        python /app/scripts/gerar_documentos_resumidor.py /out

Nenhum documento real e usado (CLAUDE.md).
"""

from __future__ import annotations

import argparse
import io
import random
import sys
from pathlib import Path

PARTES = ("Alfa Serviços Fictícios Ltda.", "Beta Comércio Imaginário S.A.")
TEMAS = (
    "prazo de entrega",
    "multa por atraso",
    "confidencialidade",
    "reajuste anual",
    "garantia dos serviços",
    "rescisão antecipada",
    "propriedade intelectual",
    "foro de eleição",
)


def _reais(valor: int) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def paragrafo(rng: random.Random, tema: str, numero: int) -> str:
    valor = rng.randint(10, 900) * 1000
    dias = rng.choice((5, 10, 15, 30, 45, 60, 90))
    return (
        f"{numero}. Quanto ao {tema}, a CONTRATADA {PARTES[0]} se obriga a cumprir as condições "
        f"pactuadas com a CONTRATANTE {PARTES[1]}, no prazo de {dias} dias corridos, sob pena de "
        f"multa de {_reais(valor)} por ocorrência, corrigida pelo índice fictício IPX. "
        "As partes reconhecem que este texto é inteiramente inventado e serve apenas para testes "
        "do Resumidor de documentos do Nexus, sem relação com pessoas ou empresas reais."
    )


def secoes(rng: random.Random, quantidade: int, paragrafos: int) -> list[tuple[str, list[str]]]:
    return [
        (
            f"Cláusula {indice + 1} — {TEMAS[indice % len(TEMAS)].capitalize()}",
            [paragrafo(rng, TEMAS[indice % len(TEMAS)], n + 1) for n in range(paragrafos)],
        )
        for indice in range(quantidade)
    ]


def ate_o_alvo(contar, alvo: int, seed: int) -> list[tuple[str, list[str]]]:
    """Aumenta o documento ate ficar logo abaixo do alvo de tokens."""
    rng = random.Random(seed)
    resultado: list[tuple[str, list[str]]] = []
    while True:
        candidata = resultado + secoes(rng, 1, 12)
        texto = "\n\n".join(t + "\n\n" + "\n\n".join(p) for t, p in candidata)
        if contar(texto) > alvo:
            return resultado
        resultado = candidata


def salvar_docx(caminho: Path, titulo: str, partes: list[tuple[str, list[str]]]) -> None:
    from docx import Document

    documento = Document()
    documento.add_heading(titulo, level=0)
    for titulo_secao, paragrafos in partes:
        documento.add_heading(titulo_secao, level=1)
        for texto in paragrafos:
            documento.add_paragraph(texto)
    documento.save(str(caminho))


def _pagina_texto(linhas: list[str]) -> bytes:
    """PDF de uma pagina com Helvetica (Latin-1), sem dependencia nova."""
    from PIL import Image, ImageDraw

    imagem = Image.new("RGB", (1240, 1754), "white")
    desenho = ImageDraw.Draw(imagem)
    y = 80
    for linha in linhas:
        desenho.text((80, y), linha, fill="black")
        y += 22
    saida = io.BytesIO()
    imagem.save(saida, "PDF", resolution=150)
    return saida.getvalue()


def salvar_pdf(caminho: Path, partes: list[tuple[str, list[str]]], *, pagina_imagem: bool) -> None:
    """Texto selecionavel pelo pypdf (pagina por secao) e, opcional, uma pagina so em imagem."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    escritor = PdfWriter()
    fonte = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    for titulo, paragrafos in partes:
        linhas = [titulo, ""] + [
            pedaco
            for texto in paragrafos
            for pedaco in _quebrar(texto, 95) + [""]
        ]
        for inicio in range(0, len(linhas), 52):
            pagina = escritor.add_blank_page(width=595, height=842)
            comandos = ["BT", "/F1 10 Tf", "14 TL", "50 800 Td"]
            for linha in linhas[inicio : inicio + 52]:
                seguro = linha.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                comandos.append(f"({seguro}) Tj T*")
            comandos.append("ET")
            conteudo = DecodedStreamObject()
            conteudo.set_data("\n".join(comandos).encode("cp1252", errors="replace"))
            pagina[NameObject("/Contents")] = escritor._add_object(conteudo)
            pagina[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): fonte})}
            )
    if pagina_imagem:
        imagem = PdfReader(io.BytesIO(_pagina_texto([
            "ANEXO DIGITALIZADO (FICTICIO)",
            "",
            "Prazo final de entrega: 30 de novembro de 2026.",
            "Valor total estimado: R$ 1.250.000,00.",
            "Responsavel ficticio: Setor de Compras Imaginario.",
        ])))
        escritor.add_page(imagem.pages[0])
    with caminho.open("wb") as arquivo:
        escritor.write(arquivo)


def _quebrar(texto: str, largura: int) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        if len(atual) + len(palavra) + 1 > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    return linhas + ([atual] if atual else [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("saida", type=Path)
    parser.add_argument("--sem-contagem", action="store_true", help="estima 1 token por palavra")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    if args.sem_contagem:
        contar = lambda texto: len(texto.split())  # noqa: E731
    else:
        sys.path.insert(0, "/app")
        from src.infrastructure.composition import build_token_counter

        contar = build_token_counter().count

    rng = random.Random(18)
    salvar_docx(args.saida / "contrato-ficticio.docx", "Contrato fictício de prestação de serviços",
                secoes(rng, 8, 4))
    salvar_pdf(args.saida / "relatorio-ficticio.pdf", secoes(rng, 4, 5), pagina_imagem=True)
    ata = "\n\n".join(
        f"{titulo}\n\n" + "\n\n".join(paragrafos)
        for titulo, paragrafos in [("ATA DE REUNIÃO FICTÍCIA", ["Presentes: equipe imaginária."])]
        + secoes(rng, 5, 3)
    )
    (args.saida / "ata-ficticia.txt").write_text(ata, encoding="utf-8")
    salvar_pdf(args.saida / "extenso-ficticio.pdf", ate_o_alvo(contar, 38_000, 1), pagina_imagem=False)
    salvar_docx(args.saida / "acima-do-teto-ficticio.docx", "Documento fictício acima do teto",
                ate_o_alvo(contar, 46_000, 2))
    for arquivo in sorted(args.saida.iterdir()):
        print(f"{arquivo.name}: {arquivo.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
