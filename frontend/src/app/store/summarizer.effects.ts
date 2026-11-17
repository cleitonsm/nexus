import { HttpErrorResponse } from "@angular/common/http";
import { inject } from "@angular/core";
import { Actions, createEffect, ofType } from "@ngrx/effects";
import { Store } from "@ngrx/store";
import {
  catchError,
  concat,
  exhaustMap,
  filter,
  map,
  mergeMap,
  of,
  switchMap,
  timer,
  withLatestFrom
} from "rxjs";

import { NexusApiService } from "../core/services/nexus-api.service";
import { describeApiError } from "../shared/documents/document-lifecycle";
import {
  SUMMARY_POLL_INTERVAL_MS,
  describeSummarizerError,
  isFinalStage
} from "../shared/summarizer/summarizer";
import { nexusActions } from "./nexus.actions";
import { summarizerActions } from "./summarizer.actions";
import { selectSummaryDocuments } from "./summarizer.selectors";

export const loadSummarizerInfoEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(summarizerActions.loadInfo),
      exhaustMap(() =>
        api.getSummarizer().pipe(
          map((info) => summarizerActions.loadInfoSuccess({ info })),
          catchError((error) =>
            of(summarizerActions.loadInfoFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

/** D7: sem conversa, cria a do resumidor e so entao envia o arquivo. */
export const uploadSummaryDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(summarizerActions.uploadDocument),
      exhaustMap(({ conversationId, assistantId, file }) => {
        const upload = (targetId: string) =>
          api.uploadConversationDocument(targetId, file).pipe(
            map((document) => summarizerActions.uploadDocumentSuccess({ document }))
          );
        const flow = conversationId
          ? upload(conversationId)
          : api.createConversation({ assistant_id: assistantId }).pipe(
              mergeMap((conversation) =>
                concat(
                  of(nexusActions.createConversationSuccess({ assistantId, conversation })),
                  upload(conversation.id)
                )
              )
            );
        return flow.pipe(
          catchError((error) =>
            of(summarizerActions.uploadDocumentFailure({ error: describeSummarizerError(error) }))
          )
        );
      })
    ),
  { functional: true }
);

export const loadSummaryDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService), store = inject(Store)) =>
    actions$.pipe(
      ofType(summarizerActions.loadDocument),
      withLatestFrom(store.select(selectSummaryDocuments)),
      switchMap(([{ conversationId }, documents]) => {
        const previousStage = documents[conversationId]?.stage ?? null;
        return api.getConversationDocument(conversationId).pipe(
          map((document) =>
            summarizerActions.loadDocumentSuccess({ conversationId, document, previousStage })
          ),
          catchError((error) =>
            // 404: a conversa ainda nao tem documento (D38 mostra as boas-vindas).
            error instanceof HttpErrorResponse && error.status === 404
              ? of(
                  summarizerActions.loadDocumentSuccess({
                    conversationId,
                    document: null,
                    previousStage
                  })
                )
              : of(
                  summarizerActions.loadDocumentFailure({
                    conversationId,
                    error: describeApiError(error)
                  })
                )
          )
        );
      })
    ),
  { functional: true }
);

/** RF-115: consulta a cada 3 s ate a etapa final (D36). */
export const pollSummaryDocumentEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(
        summarizerActions.uploadDocumentSuccess,
        summarizerActions.loadDocumentSuccess,
        summarizerActions.retrySummarySuccess
      ),
      map(({ document }) => document),
      filter((document) => document !== null && !isFinalStage(document.stage)),
      switchMap((document) =>
        timer(SUMMARY_POLL_INTERVAL_MS).pipe(
          map(() => summarizerActions.loadDocument({ conversationId: document!.conversation_id }))
        )
      )
    ),
  { functional: true }
);

/** D31 e T4: o resumo postado pelo worker aparece sem recarregar a tela. */
export const reloadMessagesWhenSummaryReadyEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(summarizerActions.loadDocumentSuccess),
      filter(
        ({ document, previousStage }) =>
          document?.stage === "pronto" && previousStage !== null && previousStage !== "pronto"
      ),
      map(({ conversationId }) => nexusActions.loadConversation({ conversationId }))
    ),
  { functional: true }
);

export const retrySummaryEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(summarizerActions.retrySummary),
      exhaustMap(({ conversationId }) =>
        api.retrySummary(conversationId).pipe(
          map((document) => summarizerActions.retrySummarySuccess({ document })),
          catchError((error) =>
            of(summarizerActions.retrySummaryFailure({ error: describeSummarizerError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const summarizerEffects = {
  loadSummarizerInfoEffect,
  uploadSummaryDocumentEffect,
  loadSummaryDocumentEffect,
  pollSummaryDocumentEffect,
  reloadMessagesWhenSummaryReadyEffect,
  retrySummaryEffect
};
