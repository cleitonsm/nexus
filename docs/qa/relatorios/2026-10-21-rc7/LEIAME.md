# Campanha — candidato `validacao-final-rc7` (2026-10-21): interrompida na V2

Commit `c81309d`. V1 OK (imagem reconstruída com a SPEC-009 D6). V2: 681 testes, 1 falha.

**Causa (teste instável de ferramenta, não do produto):** `test_perf_tools.CorpusTestCase.test_generation_is_deterministic_and_files_differ`
gera o mesmo DOCX duas vezes e compara os bytes; as entradas do ZIP levavam o horário da geração, e as duas gerações
caíram em segundos diferentes. Nas rodadas anteriores passou por coincidência.

**Correção (`1e8fecd`):** `scripts/perf/corpus.py` grava as entradas com data fixa (1980-01-01); o teste passou 3 vezes
seguidas e a geração com 2 s de intervalo ficou idêntica.
