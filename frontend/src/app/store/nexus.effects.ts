import { inject } from "@angular/core";
import { Actions, createEffect, ofType } from "@ngrx/effects";
import { Action, Store } from "@ngrx/store";
import {
  catchError,
  concat,
  filter,
  map,
  mergeMap,
  of,
  scan,
  switchMap,
  takeUntil,
  timer,
  withLatestFrom
} from "rxjs";

import { NexusApiService } from "../core/services/nexus-api.service";
import {
  DOCUMENT_POLL_INTERVAL_MS,
  describeApiError,
  hasDocumentsInProgress
} from "../shared/documents/document-lifecycle";
import { describeChatError } from "../shared/chat/chat-stream";
import { INDEX_POLL_INTERVAL_MS, isReindexRunning } from "../shared/documents/index-status";
import { ChatStreamEvent } from "../shared/models/nexus.models";
import { nexusActions } from "./nexus.actions";
import { selectActiveAssistantId } from "./nexus.selectors";

function resolveError(error: unknown): string {
  return describeApiError(error);
}

export const loadAssistantsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadAssistants),
      switchMap(() =>
        api.listAssistants().pipe(
          map((assistants) => nexusActions.loadAssistantsSuccess({ assistants })),
          catchError((error) =>
            of(nexusActions.loadAssistantsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const createAssistantEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.createAssistant),
      switchMap(({ name, description, initialPrompt, documentFiles, documentMetadata }) =>
        api.createAssistant({ name, description, initial_prompt: initialPrompt }).pipe(
          mergeMap((assistant) =>
            of(
              nexusActions.createAssistantSuccess({ assistant }),
              ...documentFiles.map((file) =>
                nexusActions.uploadDocument({
                  assistantId: assistant.id,
                  file,
                  metadata: documentMetadata
                })
              )
            )
          ),
          catchError((error) =>
            of(nexusActions.createAssistantFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const deleteAssistantEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.deleteAssistant),
      switchMap(({ assistantId }) =>
        api.deleteAssistant(assistantId).pipe(
          map(() => nexusActions.deleteAssistantSuccess({ assistantId })),
          catchError((error) =>
            of(nexusActions.deleteAssistantFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const selectCreatedAssistantEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(nexusActions.createAssistantSuccess),
      map(({ assistant }) => nexusActions.selectAssistant({ assistantId: assistant.id }))
    ),
  { functional: true }
);

export const createConversationEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.createConversation),
      switchMap(({ assistantId }) =>
        api.createConversation({ assistant_id: assistantId }).pipe(
          map((conversation) => nexusActions.createConversationSuccess({ assistantId, conversation })),
          catchError((error) =>
            of(nexusActions.createConversationFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const selectAssistantEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(nexusActions.selectAssistant),
      map(({ assistantId }) => nexusActions.loadAssistantConversations({ assistantId }))
    ),
  { functional: true }
);

export const loadAssistantConversationsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadAssistantConversations),
      switchMap(({ assistantId }) =>
        api.listAssistantConversations(assistantId).pipe(
          map((conversations) =>
            nexusActions.loadAssistantConversationsSuccess({ assistantId, conversations })
          ),
          catchError((error) =>
            of(nexusActions.loadAssistantConversationsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const deleteConversationEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.deleteConversation),
      switchMap(({ assistantId, conversationId }) =>
        api.deleteConversation(conversationId).pipe(
          map(() => nexusActions.deleteConversationSuccess({ assistantId, conversationId })),
          catchError((error) =>
            of(nexusActions.deleteConversationFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadConversationEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadConversation),
      switchMap(({ conversationId }) =>
        api.getConversation(conversationId).pipe(
          map((detail) =>
            nexusActions.loadConversationSuccess({
              conversationId,
              messages: detail.messages
            })
          ),
          catchError((error) =>
            of(nexusActions.loadConversationFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

/** ``mergeMap``: varios arquivos selecionados de uma vez sao todos enviados. */
export const uploadDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.uploadDocument),
      mergeMap(({ assistantId, file, metadata, groups }) =>
        api.uploadDocument(assistantId, file, metadata, groups ?? []).pipe(
          map((document) => nexusActions.uploadDocumentSuccess({ document })),
          catchError((error) =>
            of(nexusActions.uploadDocumentFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const inferAssistantAndSendEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.inferAssistantAndSend),
      switchMap(({ question, topK }) =>
        api.inferAssistant(question).pipe(
          mergeMap(({ assistant_id: assistantId }) => {
            if (!assistantId) {
              return of(
                nexusActions.inferAssistantAndSendFailure({
                  error: "Nao foi possivel inferir um assistente para esta pergunta."
                })
              );
            }
            return of(
              nexusActions.inferAssistantAndSendSuccess({
                assistantId,
                question,
                topK
              }),
              nexusActions.selectAssistant({ assistantId }),
              nexusActions.sendChatQuestion({
                assistantId,
                conversationId: null,
                question,
                topK
              })
            );
          }),
          catchError((error) =>
            of(nexusActions.inferAssistantAndSendFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const sendChatQuestionEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.sendChatQuestion),
      switchMap(({ assistantId, conversationId, question, topK }) => {
        // RF-58: a pergunta aparece ja; a resposta chega em partes.
        const started = of(nexusActions.chatStreamStarted({ conversationId, question }));
        const stream = (targetConversationId: string, onDone: Action[] = []) =>
          api
            .streamChatMessage(targetConversationId, { question, top_k: topK })
            .pipe(mergeMap((event) => chatStreamActions(event, onDone)));
        const answer = conversationId
          ? stream(conversationId)
          : api.createConversation({ assistant_id: assistantId }).pipe(
              // A conversa nova so vira a atual com a resposta pronta, para
              // que a recarga das mensagens nao duplique a pergunta exibida.
              mergeMap((conversation) =>
                stream(conversation.id, [
                  nexusActions.createConversationSuccess({ assistantId, conversation })
                ])
              )
            );
        return concat(started, answer).pipe(
          catchError((error) =>
            of(nexusActions.sendChatQuestionFailure({ error: describeChatError(error) }))
          )
        );
      })
    ),
  { functional: true }
);

/** Acoes de cada evento do streaming; ``onDone`` vai antes do resultado. */
export function chatStreamActions(event: ChatStreamEvent, onDone: Action[] = []): Action[] {
  switch (event.kind) {
    case "delta":
      return [nexusActions.chatStreamDelta({ text: event.text })];
    case "replace":
      return [nexusActions.chatStreamReplace({ text: event.text })];
    case "done":
      return [
        ...onDone,
        nexusActions.sendChatQuestionSuccess({
          conversationId: event.response.conversation_id,
          userMessage: event.response.user_message,
          assistantMessage: event.response.assistant_message
        })
      ];
    case "error":
      return [nexusActions.sendChatQuestionFailure({ error: event.detail })];
  }
}

export const submitFeedbackEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.submitFeedback),
      mergeMap(({ messageId, rating, comment }) =>
        api.submitFeedback(messageId, rating, comment).pipe(
          map((feedback) => nexusActions.submitFeedbackSuccess({ feedback })),
          catchError((error) =>
            of(nexusActions.submitFeedbackFailure({ messageId, error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadCuratorFeedbackEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadCuratorFeedback),
      switchMap(({ status, assistantId }) =>
        api.listFeedback(status, assistantId).pipe(
          map((items) => nexusActions.loadCuratorFeedbackSuccess({ items })),
          catchError((error) =>
            of(nexusActions.loadCuratorFeedbackFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const reviewFeedbackEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.reviewFeedback),
      mergeMap(({ feedbackId, review }) =>
        api.reviewFeedback(feedbackId, review).pipe(
          map((feedback) => nexusActions.reviewFeedbackSuccess({ feedback })),
          catchError((error) =>
            of(nexusActions.reviewFeedbackFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

/** Baixa o JSONL dos itens validados; o arquivo vai para o conjunto de referencia. */
export const exportFeedbackEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.exportFeedback),
      switchMap(({ assistantId }) =>
        api.exportFeedback(assistantId).pipe(
          map((blob) => {
            saveBlob(blob, `feedback-${assistantId}.jsonl`);
            return nexusActions.exportFeedbackSuccess();
          }),
          catchError((error) =>
            of(nexusActions.exportFeedbackFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

export const loadUsageReportEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadUsageReport),
      switchMap(({ from, to }) =>
        api.getUsageReport(from, to).pipe(
          map((report) => nexusActions.loadUsageReportSuccess({ report })),
          catchError((error) =>
            of(nexusActions.loadUsageReportFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadUsageLimitsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadUsageLimits),
      switchMap(() =>
        api.getUsageLimits().pipe(
          map((limits) => nexusActions.loadUsageLimitsSuccess({ limits })),
          catchError((error) =>
            of(nexusActions.loadUsageLimitsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const saveUsageLimitsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.saveUsageLimits),
      switchMap(({ limits }) =>
        api.saveUsageLimits(limits).pipe(
          map((saved) => nexusActions.saveUsageLimitsSuccess({ limits: saved })),
          catchError((error) =>
            of(nexusActions.saveUsageLimitsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadApiKeyStatusEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadApiKeyStatus),
      switchMap(() =>
        api.getApiKeyStatus().pipe(
          map((status) => nexusActions.loadApiKeyStatusSuccess({ status })),
          catchError((error) =>
            of(nexusActions.loadApiKeyStatusFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const saveApiKeyEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.saveApiKey),
      switchMap(({ apiKey }) =>
        api.saveApiKey({ api_key: apiKey }).pipe(
          mergeMap((status) =>
            of(
              nexusActions.saveApiKeySuccess({ status }),
              nexusActions.loadApiKeyStatusSuccess({ status })
            )
          ),
          catchError((error) =>
            of(nexusActions.saveApiKeyFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const testApiKeyEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.testApiKey),
      switchMap(() =>
        api.testApiKey().pipe(
          map((result) => nexusActions.testApiKeySuccess({ result })),
          catchError((error) =>
            of(nexusActions.testApiKeyFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const setAssistantGroupsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.setAssistantGroups),
      switchMap(({ assistantId, groups }) =>
        api.setAssistantGroups(assistantId, groups).pipe(
          map((result) =>
            nexusActions.setAssistantGroupsSuccess({ assistantId, groups: result.groups })
          ),
          catchError((error) =>
            of(nexusActions.setAssistantGroupsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadDocumentAccessEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadDocumentAccess),
      switchMap(({ assistantId }) =>
        api.listDocuments(assistantId).pipe(
          map((documents) =>
            nexusActions.loadDocumentAccessSuccess({ assistantId, documents })
          ),
          catchError((error) =>
            of(nexusActions.loadDocumentAccessFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

/** Depois de enviar, substituir ou reprocessar, a lista e lida de novo. */
export const refreshDocumentAccessEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(
        nexusActions.uploadDocumentSuccess,
        nexusActions.replaceDocumentSuccess,
        nexusActions.reprocessDocumentSuccess
      ),
      map(({ document }) =>
        nexusActions.loadDocumentAccess({ assistantId: document.assistant_id })
      )
    ),
  { functional: true }
);

/**
 * RNF-33, D4: enquanto houver documento pendente ou processando, a lista e
 * consultada de novo a cada 3 s. Para quando tudo terminou, quando outro
 * assistente e selecionado ou quando a tela de documentos e fechada.
 */
export const pollDocumentStatusEffect = createEffect(
  (actions$ = inject(Actions), store = inject(Store)) =>
    actions$.pipe(
      ofType(nexusActions.loadDocumentAccessSuccess),
      switchMap(({ assistantId, documents }) =>
        hasDocumentsInProgress(documents)
          ? timer(DOCUMENT_POLL_INTERVAL_MS).pipe(
              takeUntil(
                actions$.pipe(
                  ofType(nexusActions.stopDocumentPolling, nexusActions.loadDocumentAccess)
                )
              ),
              withLatestFrom(store.select(selectActiveAssistantId)),
              filter(([, activeAssistantId]) => activeAssistantId === assistantId),
              map(() => nexusActions.loadDocumentAccess({ assistantId, background: true }))
            )
          : of()
      )
    ),
  { functional: true }
);

export const loadIndexStatusEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadIndexStatus),
      switchMap(({ assistantId }) =>
        api.getIndexStatus(assistantId).pipe(
          map((status) => nexusActions.loadIndexStatusSuccess({ status })),
          catchError((error) =>
            of(nexusActions.loadIndexStatusFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const startReindexEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.startReindex),
      mergeMap(({ assistantId }) =>
        api.startReindex(assistantId).pipe(
          map((job) => nexusActions.startReindexSuccess({ job })),
          catchError((error) =>
            of(nexusActions.startReindexFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

/** Acompanha a reindexacao sem recarregar a pagina; para ao sair da tela. */
export const pollIndexStatusEffect = createEffect(
  (actions$ = inject(Actions), store = inject(Store)) =>
    actions$.pipe(
      ofType(nexusActions.loadIndexStatusSuccess, nexusActions.startReindexSuccess),
      map((action) =>
        "job" in action
          ? { assistantId: action.job.assistant_id, running: action.job.status === "running" }
          : { assistantId: action.status.assistant_id, running: isReindexRunning(action.status) }
      ),
      switchMap(({ assistantId, running }) =>
        running
          ? timer(INDEX_POLL_INTERVAL_MS).pipe(
              takeUntil(
                actions$.pipe(ofType(nexusActions.stopDocumentPolling, nexusActions.loadIndexStatus))
              ),
              withLatestFrom(store.select(selectActiveAssistantId)),
              filter(([, activeAssistantId]) => activeAssistantId === assistantId),
              map(() => nexusActions.loadIndexStatus({ assistantId, background: true }))
            )
          : of()
      )
    ),
  { functional: true }
);

/** Ao terminar a reindexacao, a lista de documentos reflete a nova base. */
export const reloadDocumentsAfterReindexEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(nexusActions.loadIndexStatusSuccess),
      filter(({ status }) => status.last_reindex !== null),
      map(({ status }) => ({
        assistantId: status.assistant_id,
        jobId: status.last_reindex!.id,
        running: isReindexRunning(status)
      })),
      // So a transicao de "em andamento" para concluida ou falha dispara a recarga.
      scan(
        (previous, current) => ({
          ...current,
          finished: previous.jobId === current.jobId && previous.running && !current.running
        }),
        { assistantId: "", jobId: "", running: false, finished: false }
      ),
      filter(({ finished }) => finished),
      map(({ assistantId }) => nexusActions.loadDocumentAccess({ assistantId, background: true }))
    ),
  { functional: true }
);

export const loadArchivedConversationsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadArchivedConversations),
      switchMap(() =>
        api.listArchivedConversations().pipe(
          map((conversations) =>
            nexusActions.loadArchivedConversationsSuccess({ conversations })
          ),
          catchError((error) =>
            of(nexusActions.loadArchivedConversationsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const openArchivedConversationEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.openArchivedConversation),
      switchMap(({ conversationId }) =>
        api.getArchivedConversation(conversationId).pipe(
          map((conversation) => nexusActions.openArchivedConversationSuccess({ conversation })),
          catchError((error) =>
            of(nexusActions.openArchivedConversationFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const deleteArchivedConversationEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.deleteArchivedConversation),
      mergeMap(({ conversationId }) =>
        api.deleteArchivedConversation(conversationId).pipe(
          map(() => nexusActions.deleteArchivedConversationSuccess({ conversationId })),
          catchError((error) =>
            of(nexusActions.deleteArchivedConversationFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const deleteDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.deleteDocument),
      mergeMap(({ assistantId, documentId }) =>
        api.deleteDocument(documentId).pipe(
          map(() => nexusActions.deleteDocumentSuccess({ assistantId, documentId })),
          catchError((error) =>
            of(nexusActions.deleteDocumentFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const replaceDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.replaceDocument),
      mergeMap(({ documentId, file }) =>
        api.replaceDocument(documentId, file).pipe(
          map((document) => nexusActions.replaceDocumentSuccess({ document })),
          catchError((error) =>
            of(nexusActions.replaceDocumentFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const reprocessDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.reprocessDocument),
      mergeMap(({ documentId }) =>
        api.reprocessDocument(documentId).pipe(
          map((document) => nexusActions.reprocessDocumentSuccess({ document })),
          catchError((error) =>
            of(nexusActions.reprocessDocumentFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const setDocumentGroupsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.setDocumentGroups),
      mergeMap(({ documentId, groups }) =>
        api.setDocumentGroups(documentId, groups).pipe(
          map((document) => nexusActions.setDocumentGroupsSuccess({ document })),
          catchError((error) =>
            of(nexusActions.setDocumentGroupsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadAuditEventsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.loadAuditEvents),
      switchMap(({ filters }) =>
        api.listAuditEvents(filters).pipe(
          map((events) => nexusActions.loadAuditEventsSuccess({ events })),
          catchError((error) =>
            of(nexusActions.loadAuditEventsFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const nexusEffects = {
  loadAssistantsEffect,
  createAssistantEffect,
  deleteAssistantEffect,
  selectCreatedAssistantEffect,
  selectAssistantEffect,
  createConversationEffect,
  loadAssistantConversationsEffect,
  deleteConversationEffect,
  loadConversationEffect,
  uploadDocumentEffect,
  inferAssistantAndSendEffect,
  sendChatQuestionEffect,
  loadApiKeyStatusEffect,
  saveApiKeyEffect,
  testApiKeyEffect,
  setAssistantGroupsEffect,
  loadDocumentAccessEffect,
  refreshDocumentAccessEffect,
  pollDocumentStatusEffect,
  loadIndexStatusEffect,
  startReindexEffect,
  pollIndexStatusEffect,
  reloadDocumentsAfterReindexEffect,
  loadArchivedConversationsEffect,
  openArchivedConversationEffect,
  deleteArchivedConversationEffect,
  deleteDocumentEffect,
  replaceDocumentEffect,
  reprocessDocumentEffect,
  setDocumentGroupsEffect,
  loadAuditEventsEffect,
  submitFeedbackEffect,
  loadCuratorFeedbackEffect,
  reviewFeedbackEffect,
  exportFeedbackEffect,
  loadUsageReportEffect,
  loadUsageLimitsEffect,
  saveUsageLimitsEffect
};
