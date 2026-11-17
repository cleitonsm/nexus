"""SPEC-018: job de resumo hierarquico do documento pessoal (RF-116, RF-117).

Roda no worker depois da indexacao (D21). Mini-resumos ja gravados nao sao
refeitos numa nova tentativa: o andamento sobrevive a falhas e ao limite de
tempo do job (T9). No fim, grava o consolidado e posta a mensagem na conversa
(D31, T4). Falha esgotada derruba so o resumo; as perguntas seguem (RN-64).

D44: as chamadas de um nivel rodam em paralelo (no maximo
``SUMMARY_PARALLEL_CALLS``). So a chamada ao LLM vai para outra thread; gravar,
atualizar o andamento e renovar o job continuam na thread do job.
"""

from __future__ import annotations

import contextvars
import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from uuid import uuid4

from src.application.services import (
    WORKER_USER,
    AccessControl,
    AssistantRuntimeResolver,
    DocumentIndexer,
    IngestionSettings,
    SummaryCompletion,
    UsageGovernance,
    complete_summary,
    sections_as_context,
)
from src.application.services.document_summary_prompts import (
    CONSOLIDATION_INSTRUCTION,
    GROUP_INSTRUCTION,
    MINI_SUMMARY_INSTRUCTION,
    SUMMARY_PROMPT_VERSION,
    consolidation_prompt,
    group_prompt,
    mini_summary_prompt,
)
from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    SUMMARY_FAILED,
    SUMMARY_PARALLEL_CALLS,
    USAGE_OPERATION_DOCUMENT_SUMMARY,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    ChatMessage,
    ContextChunk,
    ConversationRepository,
    Document,
    DocumentFileStorage,
    DocumentSummarySection,
    DocumentSummaryRepository,
    IngestionJob,
    IngestionJobQueue,
    JobOwnershipLostError,
    LLMGateway,
    MessageId,
    MessageRole,
    SummaryBatch,
    SummaryStage,
    SummarySectionSplitter,
    TokenCounter,
    TokenUsage,
    detect_prompt_injection,
    plan_consolidation_groups,
    plan_summary_batches,
    target_summary_words,
)

from .process_ingestion import ProcessingOutcome

logger = logging.getLogger(__name__)

# Tamanho de cada mini-resumo: proporcional ao lote, entre 150 e 500 palavras.
_MINI_WORDS_MIN = 150
_MINI_WORDS_MAX = 500
_MINI_TOKENS_PER_WORD = 15


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _mini_words(batch: SummaryBatch) -> int:
    return max(_MINI_WORDS_MIN, min(_MINI_WORDS_MAX, batch.tokens // _MINI_TOKENS_PER_WORD))


class SummarizeDocumentUseCase:
    def __init__(
        self,
        *,
        job_queue: IngestionJobQueue,
        summaries: DocumentSummaryRepository,
        conversations: ConversationRepository,
        assistants: AssistantRepository,
        runtime_resolver: AssistantRuntimeResolver,
        document_indexer: DocumentIndexer,
        splitter: SummarySectionSplitter,
        file_storage: DocumentFileStorage,
        token_counter: TokenCounter,
        access_control: AccessControl,
        usage_governance: UsageGovernance | None = None,
        settings: IngestionSettings | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._queue = job_queue
        self._summaries = summaries
        self._conversations = conversations
        self._assistants = assistants
        self._runtime_resolver = runtime_resolver
        self._indexer = document_indexer
        self._splitter = splitter
        self._storage = file_storage
        self._counter = token_counter
        self._access = access_control
        self._usage = usage_governance
        self._settings = settings or IngestionSettings()
        self._clock = clock

    def __call__(self, job: IngestionJob, document: Document) -> ProcessingOutcome | None:
        return self.execute(job, document)

    def execute(self, job: IngestionJob, document: Document) -> ProcessingOutcome | None:
        started_at = time.perf_counter()
        usage = TokenUsage()
        model = ""
        try:
            assistant = self._assistants.get_by_id(SUMMARIZER_ASSISTANT_ID)
            if assistant is None:
                raise RuntimeError("the summarizer assistant is missing.")
            runtime = self._runtime_resolver(assistant)
            model = runtime.usage_model
            content, citations, usage, flags, batches = self._summarize(
                job, document, runtime.llm_gateway
            )
        except JobOwnershipLostError:
            logger.warning("summary.job.ownership_lost", extra={"job_id": job.id})
            return None
        except Exception as exc:  # noqa: BLE001 - toda falha vira estado
            self._record_usage(document, usage, model, runtime_pricing=None, failed=True)
            return self._handle_failure(job, document, exc)
        self._summaries.complete(
            document.id,
            content=content,
            citations=citations,
            prompt_version=SUMMARY_PROMPT_VERSION,
            model=model,
        )
        self._post_message(document, content, citations)
        self._queue.complete(job.complete(), document, None)
        self._record_usage(document, usage, model, runtime_pricing=runtime.usage_pricing)
        self._audit(document, usage, model, batches, flags, started_at)
        return ProcessingOutcome(
            job_id=job.id,
            document_id=document.id.value,
            status=document.status.value,
            attempts=job.attempts,
            chunk_count=document.chunk_count,
        )

    # -- resumo ------------------------------------------------------------

    def _summarize(self, job: IngestionJob, document: Document, llm: LLMGateway):
        raw_content = self._storage.load(document.storage_key or "")
        extracted = self._indexer.extract(
            source_name=document.source_name, content_type=None, raw_content=raw_content
        )
        sections = self._splitter.split(extracted)
        batches = plan_summary_batches([section.as_tokens() for section in sections])
        by_index = {section.index: section for section in sections}
        done = {item.position for item in self._summaries.list_sections(document.id)}
        usage = TokenUsage()
        flags = 0
        total = len(batches)
        self._summaries.set_stage(
            document.id, SummaryStage.SUMMARIZING, batches_done=len(done), batches_total=total
        )
        calls: list[tuple[int, Callable[[], SummaryCompletion]]] = []
        for position, batch in enumerate(batches):
            if position in done:
                continue
            texts = [by_index[piece.section_index].text_for(piece) for piece in batch.pieces]
            flags += sum(1 for text in texts if detect_prompt_injection(text))
            context = [
                ContextChunk(
                    number=number,
                    text=text,
                    section_path=piece.title,
                    page=piece.page_start,
                )
                for number, (piece, text) in enumerate(zip(batch.pieces, texts), start=1)
            ]
            calls.append(
                (
                    position,
                    _call(llm, context, MINI_SUMMARY_INSTRUCTION, mini_summary_prompt(_mini_words(batch))),
                )
            )

        def save_mini(position: int, result: SummaryCompletion) -> None:
            nonlocal usage
            usage = usage + result.usage
            self._hold(job)
            batch = batches[position]
            self._summaries.save_section(
                DocumentSummarySection(
                    document_id=document.id,
                    position=position,
                    title=_batch_title(batch),
                    input_tokens=batch.tokens,
                    content=result.text,
                    page_start=batch.pieces[0].page_start,
                )
            )
            done.add(position)
            self._summaries.set_stage(
                document.id,
                SummaryStage.SUMMARIZING,
                batches_done=min(len(done), total),
                batches_total=total,
            )

        _in_parallel(calls, save_mini)
        minis = self._summaries.list_sections(document.id)
        context = sections_as_context(document, minis)
        words = target_summary_words(sum(item.input_tokens for item in minis))
        groups = plan_consolidation_groups([self._counter.count(item.content) for item in minis])
        if len(groups) > 1:
            # D23: terceiro nivel; os marcadores apontam para os mini-resumos.
            condensed: dict[int, str] = {}

            def keep_group(position: int, result: SummaryCompletion) -> None:
                nonlocal usage
                usage = usage + result.usage
                condensed[position] = result.text
                self._hold(job)

            group_words = max(150, words // len(groups))
            _in_parallel(
                [
                    (
                        position,
                        _call(
                            llm,
                            [context[index] for index in group],
                            GROUP_INSTRUCTION,
                            group_prompt(group_words),
                        ),
                    )
                    for position, group in enumerate(groups)
                ],
                keep_group,
            )
            # Os textos condensados vao no pedido; os trechos levam so o titulo
            # de cada parte, para o marcador [n] continuar resolvendo a citacao.
            final_context = [
                ContextChunk(
                    number=item.number,
                    text=item.section_path or f"Parte {item.number}",
                    document_id=item.document_id,
                    chunk_id=item.chunk_id,
                    source_name=item.source_name,
                    section_path=item.section_path,
                    page=item.page,
                )
                for item in context
            ]
            prompt = consolidation_prompt(words) + "\n\nTextos condensados:\n\n" + "\n\n".join(
                condensed[position] for position in range(len(groups))
            )
            result = complete_summary(
                llm, final_context, instruction=CONSOLIDATION_INSTRUCTION, prompt=prompt
            )
        else:
            result = complete_summary(
                llm, context, instruction=CONSOLIDATION_INSTRUCTION, prompt=consolidation_prompt(words)
            )
        usage = usage + result.usage
        self._hold(job)
        return result.text, result.citations, usage, flags, total

    def _hold(self, job: IngestionJob) -> None:
        if not self._queue.renew(job, self._clock()):
            raise JobOwnershipLostError(job.id)

    # -- resultado ---------------------------------------------------------

    def _post_message(self, document: Document, content: str, citations) -> None:
        """D31 e T4: o resumo aparece sozinho na conversa."""
        if document.conversation_id is None:
            return  # conversa excluida no meio: nada a postar
        try:
            self._conversations.save_message(
                ChatMessage(
                    id=MessageId(str(uuid4())),
                    conversation_id=document.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=content,
                    citations=citations,
                )
            )
        except Exception:  # noqa: BLE001 - o resumo gravado continua disponivel
            logger.exception(
                "summary.message.post_failed", extra={"document_id": document.id.value}
            )

    def _handle_failure(
        self, job: IngestionJob, document: Document, error: Exception
    ) -> ProcessingOutcome:
        detail = f"{type(error).__name__}: {error}"
        if job.attempts < self._settings.max_attempts:
            when = self._clock() + self._settings.delay_after(job.attempts)
            self._queue.retry(job.retry_at(when, detail), document)
            logger.warning("summary.job.retry", extra={"job_id": job.id, "error": detail})
        else:
            self._queue.fail(job.fail(detail), document)
            self._summaries.fail(document.id, SUMMARY_FAILED)
            logger.error("summary.job.failed", extra={"job_id": job.id, "error": detail})
        return ProcessingOutcome(
            job_id=job.id,
            document_id=document.id.value,
            status=document.status.value,
            attempts=job.attempts,
            chunk_count=document.chunk_count,
        )

    def _record_usage(
        self, document: Document, usage: TokenUsage, model: str, *, runtime_pricing, failed: bool = False
    ) -> None:
        if self._usage is None or document.owner_user_id is None:
            return
        if not usage.total_tokens and not failed:
            return
        try:
            self._usage.record(
                AuthenticatedUser(id=document.owner_user_id),
                conversation_id=document.conversation_id.value if document.conversation_id else None,
                assistant_id=SUMMARIZER_ASSISTANT_ID.value,
                usage=usage,
                failed=failed,
                model=model or None,
                pricing=runtime_pricing,
                operation=USAGE_OPERATION_DOCUMENT_SUMMARY,
            )
        except Exception:  # noqa: BLE001 - consumo nao derruba o resumo
            logger.exception("summary.usage.record_failed")

    def _audit(self, document, usage, model, batches, flags, started_at) -> None:
        self._access.audit(
            WORKER_USER,
            AuditAction.SUMMARY_DOCUMENT_SUMMARIZED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "owner_user_id": document.owner_user_id,
                "batches": batches,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "model": model,
                "prompt_version": SUMMARY_PROMPT_VERSION,
                "injection_flags": flags,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )


def _call(
    llm: LLMGateway, context: list[ContextChunk], instruction: str, prompt: str
) -> Callable[[], SummaryCompletion]:
    return lambda: complete_summary(llm, context, instruction=instruction, prompt=prompt)


def _in_parallel(
    calls: Sequence[tuple[int, Callable[[], SummaryCompletion]]],
    on_result: Callable[[int, SummaryCompletion], None],
) -> None:
    """D44: ate ``SUMMARY_PARALLEL_CALLS`` chamadas ao mesmo tempo.

    ``on_result`` roda na thread que chamou, na ordem em que as respostas
    chegam. Na primeira falha, as chamadas que ainda nao comecaram sao
    canceladas; as que ja estavam em andamento terminam e sao gravadas, e a
    falha sobe depois (a nova tentativa refaz so o que faltou, RN-63).
    """
    if not calls:
        return
    pool = ThreadPoolExecutor(
        max_workers=min(SUMMARY_PARALLEL_CALLS, len(calls)),
        thread_name_prefix="summary-llm",
    )
    failure: BaseException | None = None
    try:
        # Cada chamada leva o contexto atual (span pai do tracing).
        futures: dict[Future[SummaryCompletion], int] = {
            pool.submit(contextvars.copy_context().run, call): position
            for position, call in calls
        }
        for future in as_completed(futures):
            if future.cancelled():
                continue
            error = future.exception()
            if error is not None:
                if failure is None:
                    failure = error
                    for pending in futures:
                        pending.cancel()
                continue
            on_result(futures[future], future.result())
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    if failure is not None:
        raise failure


def _batch_title(batch: SummaryBatch) -> str:
    titles = list(dict.fromkeys(piece.title for piece in batch.pieces))
    if len(titles) == 1:
        return titles[0]
    return f"{titles[0]} … {titles[-1]}"
