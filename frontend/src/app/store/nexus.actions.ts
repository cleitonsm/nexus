import { createActionGroup, emptyProps, props } from "@ngrx/store";

import {
  ApiKeyStatus,
  Assistant,
  ChatMessage,
  Conversation,
  IngestedDocument
} from "../shared/models/nexus.models";

export const nexusActions = createActionGroup({
  source: "Nexus",
  events: {
    "Clear Error": emptyProps(),
    "Load Assistants": emptyProps(),
    "Load Assistants Success": props<{ assistants: Assistant[] }>(),
    "Load Assistants Failure": props<{ error: string }>(),

    "Create Assistant": props<{ name: string; description: string | null }>(),
    "Create Assistant Success": props<{ assistant: Assistant }>(),
    "Create Assistant Failure": props<{ error: string }>(),

    "Select Assistant": props<{ assistantId: string }>(),

    "Create Conversation": props<{ assistantId: string }>(),
    "Create Conversation Success": props<{ assistantId: string; conversation: Conversation }>(),
    "Create Conversation Failure": props<{ error: string }>(),
    "Load Assistant Conversations": props<{ assistantId: string }>(),
    "Load Assistant Conversations Success": props<{
      assistantId: string;
      conversations: Conversation[];
    }>(),
    "Load Assistant Conversations Failure": props<{ error: string }>(),
    "Select Conversation": props<{ conversationId: string }>(),

    "Load Conversation": props<{ conversationId: string }>(),
    "Load Conversation Success": props<{
      conversationId: string;
      messages: ChatMessage[];
    }>(),
    "Load Conversation Failure": props<{ error: string }>(),

    "Upload Document": props<{
      assistantId: string;
      file: File;
      metadata: Record<string, string>;
    }>(),
    "Upload Document Success": props<{ document: IngestedDocument }>(),
    "Upload Document Failure": props<{ error: string }>(),

    "Send Chat Question": props<{ conversationId: string; question: string; topK: number }>(),
    "Send Chat Question Success": props<{
      conversationId: string;
      userMessage: ChatMessage;
      assistantMessage: ChatMessage;
    }>(),
    "Send Chat Question Failure": props<{ error: string }>(),

    "Load Api Key Status": emptyProps(),
    "Load Api Key Status Success": props<{ status: ApiKeyStatus }>(),
    "Load Api Key Status Failure": props<{ error: string }>(),
    "Save Api Key": props<{ apiKey: string }>(),
    "Save Api Key Success": props<{ status: ApiKeyStatus }>(),
    "Save Api Key Failure": props<{ error: string }>()
  }
});
