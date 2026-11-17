import { createActionGroup, emptyProps, props } from "@ngrx/store";

import { SummarizerInfo, SummaryDocument } from "../shared/models/nexus.models";

/** SPEC-018: resumidor de documentos (RF-113 a RF-119). */
export const summarizerActions = createActionGroup({
  source: "Summarizer",
  events: {
    "Load Info": emptyProps(),
    "Load Info Success": props<{ info: SummarizerInfo }>(),
    "Load Info Failure": props<{ error: string }>(),

    /** Sem conversa ainda, o efeito cria a conversa do resumidor antes (D7). */
    "Upload Document": props<{ conversationId: string | null; assistantId: string; file: File }>(),
    "Upload Document Success": props<{ document: SummaryDocument }>(),
    "Upload Document Failure": props<{ error: string }>(),

    "Load Document": props<{ conversationId: string }>(),
    /** ``document`` nulo: a conversa ainda nao tem documento (404 da API). */
    "Load Document Success": props<{
      conversationId: string;
      document: SummaryDocument | null;
      previousStage: string | null;
    }>(),
    "Load Document Failure": props<{ conversationId: string; error: string }>(),

    "Retry Summary": props<{ conversationId: string }>(),
    "Retry Summary Success": props<{ document: SummaryDocument }>(),
    "Retry Summary Failure": props<{ error: string }>(),

    "Clear Error": emptyProps()
  }
});
