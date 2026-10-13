/**
 * Acoes do chat em streaming (RF-58, SPEC-006 D13). Funcoes puras, usadas pelo
 * effect e testadas sem Angular.
 */
import { Action } from "@ngrx/store";

import { ChatStreamEvent, Conversation } from "../shared/models/nexus.models";
import { nexusActions } from "./nexus.actions";

/** Resposta que terminou sem o evento final ``done`` ou ``error``. */
export const INTERRUPTED_ANSWER =
  "A resposta foi interrompida antes do fim. A pergunta ficou na conversa; tente novamente.";

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

export function isTerminal(event: ChatStreamEvent): boolean {
  return event.kind === "done" || event.kind === "error";
}

export interface InterruptedChat {
  /** Verdadeiro quando o usuario parou ou saiu da tela. */
  cancelled: boolean;
  conversationId: string | null;
  assistantId: string;
  /** Conversa criada para esta pergunta, se a criacao chegou a terminar. */
  createdConversation: Conversation | null;
}

/**
 * Fim sem evento final: o balao some, a conversa e recarregada (a pergunta ja
 * foi gravada pela API) e, se nao foi o usuario quem parou, o erro aparece.
 */
export function interruptedChatActions(chat: InterruptedChat): Action[] {
  const created = chat.createdConversation;
  const conversationId = created?.id ?? chat.conversationId;
  return [
    ...(created
      ? [nexusActions.createConversationSuccess({ assistantId: chat.assistantId, conversation: created })]
      : []),
    chat.cancelled
      ? nexusActions.chatStreamCancelled()
      : nexusActions.sendChatQuestionFailure({ error: INTERRUPTED_ANSWER }),
    ...(conversationId ? [nexusActions.loadConversation({ conversationId })] : [])
  ];
}
