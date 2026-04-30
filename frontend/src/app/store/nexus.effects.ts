import { inject } from "@angular/core";
import { Actions, createEffect, ofType } from "@ngrx/effects";
import { catchError, map, mergeMap, of, switchMap } from "rxjs";

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

export const nexusEffects = {
  loadAssistantsEffect,
  createAssistantEffect,
  selectCreatedAssistantEffect,
  selectAssistantEffect,
  createConversationEffect,
  loadAssistantConversationsEffect,
  loadConversationEffect,
  uploadDocumentEffect,
  sendChatQuestionEffect,
  loadApiKeyStatusEffect,
  saveApiKeyEffect
};
