# ADR 0009: Ingestão Assíncrona com Fila em PostgreSQL

## Status

Aceita em 2026-10-08, com a aprovação da SPEC-005 (decisões no
[plano de implementação](../../especificacao/specs/SPEC-005-plano-de-implementacao.md)).
Implementada; ainda não executada no ambiente Docker.

## Contexto

A ingestão é executada dentro da requisição de upload. Com embeddings reais, vetores esparsos e
OCR, o tempo de processamento ultrapassa o aceitável para uma requisição HTTP. Não há estados de
documento, novas tentativas, exclusão, substituição nem armazenamento do arquivo original.

O projeto adota monólito modular e evita novos serviços de infraestrutura sem necessidade.

## Decisão

1. Processar a ingestão em segundo plano, em um serviço `worker` que usa a mesma imagem e o mesmo
   código do backend.
2. Implementar a fila sobre o PostgreSQL existente (tabela `ingestion_jobs`, reserva com
   `FOR UPDATE SKIP LOCKED`), atrás da porta `IngestionJobQueue`.
3. Controlar o ciclo de vida do documento pelos estados pendente, processando, indexado e falhou,
   com até três tentativas.
4. Armazenar o arquivo original em volume local, atrás da porta `DocumentFileStorage`.
5. Tornar o processamento idempotente: identificadores de ponto determinísticos e remoção dos
   pontos do documento antes de regravar.
6. Executar OCR localmente, no worker, com Tesseract e Poppler instalados na imagem e chamados
   por processo (D2), sem dependência Python nova.

## Consequências

- O upload passa a responder imediatamente com o documento no estado pendente.
- A mudança de estado e a conclusão do job ocorrem na mesma transação do banco, sem coordenação
  entre sistemas diferentes.
- O ambiente ganha um container, mas nenhum serviço de infraestrutura novo.
- A reindexação (ADR 0006) passa a dispensar novo upload.
- Em volumes muito altos, a fila em PostgreSQL pode se tornar gargalo; a porta permite trocar a
  implementação sem alterar os casos de uso.
- Falhas parciais podem deixar PostgreSQL e Qdrant divergentes; é necessária uma rotina de conferência.

## Alternativas Consideradas

- **Broker dedicado com biblioteca de tarefas:** mais recursos, porém acrescenta um serviço e
  outro ponto de falha, sem necessidade no volume previsto.
- **Tarefas em segundo plano do próprio processo da API:** descartadas porque se perdem quando o
  processo reinicia.
- **Armazenamento de objetos para os originais:** adiado; a porta permite adotá-lo depois.
