/** SPEC-006 D13 (fix-6): fim do streaming sem evento final e cancelamento. */
import "@angular/compiler";
import { describe, expect, it } from "vitest";

import { Conversation } from "../shared/models/nexus.models";
import { INTERRUPTED_ANSWER, chatStreamActions, interruptedChatActions } from "./chat-stream-flow";
import { nexusActions } from "./nexus.actions";

const conversation: Conversation = {
  id: "conv-new",
  assistant_id: "a-1",
  name: null,
  created_at: "2026-10-13T12:00:00Z",
  updated_at: "2026-10-13T12:00:00Z",
  message_count: 0
};

const types = (actions: { type: string }[]) => actions.map((action) => action.type);

describe("chatStreamActions", () => {
  it("maps text events to delta and replace", () => {
    expect(types(chatStreamActions({ kind: "delta", text: "x" }))).toEqual([
      nexusActions.chatStreamDelta.type
    ]);
    expect(types(chatStreamActions({ kind: "replace", text: "x" }))).toEqual([
      nexusActions.chatStreamReplace.type
    ]);
  });

  it("turns an error event into a failure with the API detail", () => {
    const [action] = chatStreamActions({ kind: "error", status: 502, detail: "LLM fora" });
    expect(action).toEqual(nexusActions.sendChatQuestionFailure({ error: "LLM fora" }));
  });
});

describe("interruptedChatActions", () => {
  it("reports an answer that ended without a final event and reloads the conversation", () => {
    const actions = interruptedChatActions({
      cancelled: false,
      conversationId: "conv-1",
      assistantId: "a-1",
      createdConversation: null
    });
    expect(actions).toEqual([
      nexusActions.sendChatQuestionFailure({ error: INTERRUPTED_ANSWER }),
      nexusActions.loadConversation({ conversationId: "conv-1" })
    ]);
  });

  it("cancels quietly and shows the new conversation with the stored question", () => {
    const actions = interruptedChatActions({
      cancelled: true,
      conversationId: null,
      assistantId: "a-1",
      createdConversation: conversation
    });
    expect(actions).toEqual([
      nexusActions.createConversationSuccess({ assistantId: "a-1", conversation }),
      nexusActions.chatStreamCancelled(),
      nexusActions.loadConversation({ conversationId: "conv-new" })
    ]);
  });

  it("only clears the bubble when cancelled before the conversation existed", () => {
    expect(
      interruptedChatActions({
        cancelled: true,
        conversationId: null,
        assistantId: "a-1",
        createdConversation: null
      })
    ).toEqual([nexusActions.chatStreamCancelled()]);
  });
});
