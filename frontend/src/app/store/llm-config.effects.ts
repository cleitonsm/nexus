import { inject } from "@angular/core";
import { Actions, createEffect, ofType } from "@ngrx/effects";
import { catchError, concatMap, map, mergeMap, of, switchMap } from "rxjs";

import { NexusApiService } from "../core/services/nexus-api.service";
import { describeApiError } from "../shared/documents/document-lifecycle";
import { parseConflict } from "../shared/llm/llm-config";
import { llmConfigActions } from "./llm-config.actions";

function changeFailure(error: unknown) {
  const conflict = parseConflict(error);
  return llmConfigActions.credentialChangeFailure({
    error: conflict ? conflict.message : describeApiError(error),
    conflict
  });
}

export const loadLlmCredentialsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.loadCredentials),
      switchMap(() =>
        api.listLlmCredentials().pipe(
          map((list) => llmConfigActions.loadCredentialsSuccess({ list })),
          catchError((error) =>
            of(llmConfigActions.loadCredentialsFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const createLlmCredentialEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.createCredential),
      concatMap(({ input }) =>
        api.createLlmCredential(input).pipe(
          map((credential) => llmConfigActions.createCredentialSuccess({ credential })),
          catchError((error) => of(changeFailure(error)))
        )
      )
    ),
  { functional: true }
);

export const updateLlmCredentialEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.updateCredential),
      concatMap(({ id, input }) =>
        api.updateLlmCredential(id, input).pipe(
          map((credential) => llmConfigActions.updateCredentialSuccess({ credential })),
          catchError((error) => of(changeFailure(error)))
        )
      )
    ),
  { functional: true }
);

export const deleteLlmCredentialEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.deleteCredential),
      concatMap(({ id }) =>
        api.deleteLlmCredential(id).pipe(
          map(() => llmConfigActions.deleteCredentialSuccess({ id })),
          catchError((error) => of(changeFailure(error)))
        )
      )
    ),
  { functional: true }
);

export const setDefaultLlmCredentialEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.setDefaultCredential),
      concatMap(({ id }) =>
        api.setDefaultLlmCredential(id).pipe(
          map((credential) => llmConfigActions.setDefaultCredentialSuccess({ credential })),
          catchError((error) => of(changeFailure(error)))
        )
      )
    ),
  { functional: true }
);

/** Toda alteracao muda outras linhas (padrao, quem usa): recarrega a lista. */
export const reloadLlmCredentialsEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(
        llmConfigActions.createCredentialSuccess,
        llmConfigActions.updateCredentialSuccess,
        llmConfigActions.deleteCredentialSuccess,
        llmConfigActions.setDefaultCredentialSuccess
      ),
      map(() => llmConfigActions.loadCredentials())
    ),
  { functional: true }
);

export const loadDefaultImpactEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.loadDefaultImpact),
      switchMap(({ id, modelNames }) =>
        api.getDefaultChangeImpact(id, modelNames).pipe(
          map((impact) => llmConfigActions.loadDefaultImpactSuccess({ impact })),
          catchError((error) =>
            of(llmConfigActions.loadDefaultImpactFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const testLlmCredentialEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.testCredential),
      switchMap(({ id, model }) =>
        api.testLlmCredential(id, model).pipe(
          map((result) => llmConfigActions.testCredentialSuccess({ result })),
          catchError((error) =>
            of(llmConfigActions.testCredentialFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadLlmOptionsEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.loadOptions),
      switchMap(() =>
        api.listLlmCredentialOptions().pipe(
          map((options) => llmConfigActions.loadOptionsSuccess({ options })),
          catchError((error) =>
            of(llmConfigActions.loadOptionsFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadAssistantLlmEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.loadAssistantLlm),
      switchMap(({ assistantId }) =>
        api.getAssistantLlm(assistantId).pipe(
          map((llm) => llmConfigActions.loadAssistantLlmSuccess({ assistantId, llm })),
          catchError((error) =>
            of(llmConfigActions.loadAssistantLlmFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const saveAssistantLlmEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.saveAssistantLlm),
      concatMap(({ assistantId, input }) =>
        api.saveAssistantLlm(assistantId, input).pipe(
          map((llm) => llmConfigActions.saveAssistantLlmSuccess({ assistantId, llm })),
          catchError((error) =>
            of(llmConfigActions.saveAssistantLlmFailure({ error: describeApiError(error) }))
          )
        )
      )
    ),
  { functional: true }
);

export const loadAssistantRetrievalEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.loadAssistantRetrieval),
      mergeMap(({ assistantId }) =>
        api.getAssistantRetrieval(assistantId).pipe(
          map((retrieval) =>
            llmConfigActions.loadAssistantRetrievalSuccess({ assistantId, retrieval })
          ),
          catchError((error) =>
            of(
              llmConfigActions.loadAssistantRetrievalFailure({ error: describeApiError(error) })
            )
          )
        )
      )
    ),
  { functional: true }
);

export const saveAssistantRetrievalEffect = createEffect(
  (actions$ = inject(Actions), api = inject(NexusApiService)) =>
    actions$.pipe(
      ofType(llmConfigActions.saveAssistantRetrieval),
      concatMap(({ assistantId, input }) =>
        api.saveAssistantRetrieval(assistantId, input).pipe(
          map((retrieval) =>
            llmConfigActions.saveAssistantRetrievalSuccess({ assistantId, retrieval })
          ),
          catchError((error) =>
            of(
              llmConfigActions.saveAssistantRetrievalFailure({ error: describeApiError(error) })
            )
          )
        )
      )
    ),
  { functional: true }
);

export const llmConfigEffects = {
  loadLlmCredentialsEffect,
  createLlmCredentialEffect,
  updateLlmCredentialEffect,
  deleteLlmCredentialEffect,
  setDefaultLlmCredentialEffect,
  reloadLlmCredentialsEffect,
  loadDefaultImpactEffect,
  testLlmCredentialEffect,
  loadLlmOptionsEffect,
  loadAssistantLlmEffect,
  saveAssistantLlmEffect,
  loadAssistantRetrievalEffect,
  saveAssistantRetrievalEffect
};
