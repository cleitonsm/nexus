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
      switchMap(({ assistantId, conversationId, question, topK }) => {
        // #region agent log
        fetch("http://127.0.0.1:7657/ingest/1e04e285-e754-4529-87f1-5953edf93f4e", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Debug-Session-Id": "a1f259"
          },
          body: JSON.stringify({
            sessionId: "a1f259",
            runId: "manual-send-flow-fix",
            hypothesisId: "H5,H6",
            location: "frontend/src/app/store/nexus.effects.ts:sendChatQuestionEffect:start",
            message: "starting send chat question flow",
            data: {
              assistantId,
              hasConversation: Boolean(conversationId),
              questionLength: question.trim().length
            },
            timestamp: Date.now()
          })
        }).catch(() => {});
        // #endregion
        const sendWithConversation = (targetConversationId: string) =>
          api.sendChatMessage(targetConversationId, { question, top_k: topK }).pipe(
            map((response) =>
              nexusActions.sendChatQuestionSuccess({
                conversationId: response.conversation_id,
                userMessage: response.user_message,
                assistantMessage: response.assistant_message
              })
            )
          );
        if (conversationId) {
          return sendWithConversation(conversationId).pipe(
            catchError((error) =>
              of(nexusActions.sendChatQuestionFailure({ error: resolveError(error) }))
            )
          );
        }
        return api.createConversation({ assistant_id: assistantId }).pipe(
          mergeMap((conversation) =>
            sendWithConversation(conversation.id).pipe(
              mergeMap((sendSuccessAction) =>
                of(
                  nexusActions.createConversationSuccess({ assistantId, conversation }),
                  sendSuccessAction
                )
              )
            )
          ),
          catchError((error) =>
            of(nexusActions.sendChatQuestionFailure({ error: resolveError(error) }))
          )
        );
      })
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
  sendChatQuestionEffect,
  loadApiKeyStatusEffect,
  saveApiKeyEffect,
  testApiKeyEffect
};
