"""Trava unica do processo para carregar modelos locais (embedding e reranker).

O carregamento do ``transformers`` cria os pesos no dispositivo ``meta`` trocando, por
um instante, funcoes globais do torch. Dois carregamentos ao mesmo tempo (as primeiras
perguntas simultaneas depois de o backend subir) corrompem esse estado e o processo
passa a falhar em toda pergunta com ``Cannot copy out of meta tensor`` (ensaio do
RNF-01, 2026-10-24: 93 de 100 perguntas com 502 ate reiniciar o backend). A trava e a
mesma para todos os modelos, porque o estado trocado e global.
"""

from __future__ import annotations

import threading

MODEL_LOAD_LOCK = threading.Lock()
