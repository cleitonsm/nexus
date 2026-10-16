"""Mede a nota que o reranker atribui a pares pergunta/trecho (diagnostico).

Usa o mesmo modelo e a mesma sigmoide do sistema, sem subir a pilha. Serve para
comparar a nota de um trecho esperado com ``RELEVANCE_MIN_SCORE``.

Uso (na imagem do backend, com o cache do modelo):
    python /app/scripts/diagnostico_reranker.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app")

from src.infrastructure.reranking.cross_encoder_reranker import _load_model  # noqa: E402

MODEL = os.getenv(
    "RERANKER_MODEL_NAME", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
)
MIN_SCORE = float(os.getenv("RELEVANCE_MIN_SCORE", "0.5"))

CHUNK = (
    "Politica de reembolso de despesas de viagem A aprovação do gestor é "
    "obrigatória antes da viagem. A prestação de contas ocorre em até cinco "
    "dias úteis.\n\nDespesas sem comprovação fiscal não serão reembolsadas."
)
TEXTS = {
    "trecho inteiro (como indexado)": CHUNK,
    "so a frase da prestacao de contas": "A prestação de contas ocorre em até cinco dias úteis.",
    "controle irrelevante": "O refeitório funciona das 11h às 14h e serve almoço executivo.",
}
QUERIES = [
    "Qual o prazo da prestação de contas?",
    "Qual o prazo para a prestação de contas das despesas de viagem?",
    "prazo prestação de contas",
]


def main() -> None:
    model, activation = _load_model(MODEL)
    print(f"modelo: {MODEL} | RELEVANCE_MIN_SCORE={MIN_SCORE}\n")
    for query in QUERIES:
        print(f"pergunta: {query}")
        pairs = [(query, text) for text in TEXTS.values()]
        scores = model.predict(
            pairs, activation_fct=activation, show_progress_bar=False
        )
        for label, score in zip(TEXTS, scores):
            verdict = "passa" if float(score) >= MIN_SCORE else "NAO passa"
            print(f"  {float(score):.4f}  {verdict:9}  {label}")
        print()


if __name__ == "__main__":
    main()
