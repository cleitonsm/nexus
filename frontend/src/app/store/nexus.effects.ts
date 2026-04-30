import { inject } from "@angular/core";
import { Actions, createEffect, ofType } from "@ngrx/effects";
import { catchError, map, of, switchMap } from "rxjs";

import { NexusApiService } from "../core/services/nexus-api.service";
import { nexusActions } from "./nexus.actions";

function resolveError(error: unknown): string {
  if (typeof error === "object" && error !== null && "error" in error) {
    const wrappedError = error as { error?: { detail?: string } };
    return wrappedError.error?.detail ?? "Falha inesperada ao processar a requisição.";
  }
  return "Falha inesperada ao processar a requisição.";
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
      switchMap(({ name, description }) =>
        api.createAssistant({ name, description }).pipe(
          map((assistant) => nexusActions.createAssistantSuccess({ assistant })),
          catchError((error) =>
            of(nexusActions.createAssistantFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const createConversationEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.createConversation),
      switchMap(({ assistantId }) =>
        api.createConversation({ assistant_id: assistantId }).pipe(
          map((conversation) =>
            nexusActions.createConversationSuccess({
              assistantId,
              conversationId: conversation.id
            })
          ),
          catchError((error) =>
            of(nexusActions.createConversationFailure({ error: resolveError(error) }))
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

export const uploadDocumentEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(nexusActions.uploadDocument),
      switchMap(({ assistantId, file, metadata }) =>
        api.uploadDocument(assistantId, file, metadata).pipe(
          map((document) => nexusActions.uploadDocumentSuccess({ document })),
          catchError((error) =>
            of(nexusActions.uploadDocumentFailure({ error: resolveError(error) }))
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
      switchMap(({ conversationId, question, topK }) =>
        api.sendChatMessage(conversationId, { question, top_k: topK }).pipe(
          map((response) =>
            nexusActions.sendChatQuestionSuccess({
              conversationId: response.conversation_id,
              userMessage: response.user_message,
              assistantMessage: response.assistant_message
            })
          ),
          catchError((error) =>
            of(nexusActions.sendChatQuestionFailure({ error: resolveError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const nexusEffects = {
  loadAssistantsEffect,
  createAssistantEffect,
  createConversationEffect,
  loadConversationEffect,
  uploadDocumentEffect,
  sendChatQuestionEffect
};
