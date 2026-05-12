import { createActionGroup, emptyProps, props } from "@ngrx/store";

import {
  ApiKeyTestResult,
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

    "Create Assistant": props<{
      name: string;
      description: string | null;
      initialPrompt: string | null;
      documentFiles: File[];
      documentMetadata: Record<string, string>;
    }>(),
    "Create Assistant Success": props<{ assistant: Assistant }>(),
    "Create Assistant Failure": props<{ error: string }>(),
    "Open Create Assistant Modal": emptyProps(),
    "Close Create Assistant Modal": emptyProps(),
    "Delete Assistant": props<{ assistantId: string }>(),
    "Delete Assistant Success": props<{ assistantId: string }>(),
    "Delete Assistant Failure": props<{ error: string }>(),

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
    "Delete Conversation": props<{ assistantId: string; conversationId: string }>(),
    "Delete Conversation Success": props<{ assistantId: string; conversationId: string }>(),
    "Delete Conversation Failure": props<{ error: string }>(),

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

    "Send Chat Question": props<{
      assistantId: string;
      conversationId: string | null;
      question: string;
      topK: number;
    }>(),
    "Infer Assistant And Send": props<{ question: string; topK: number }>(),
    "Infer Assistant And Send Success": props<{
      assistantId: string;
      question: string;
      topK: number;
    }>(),
    "Infer Assistant And Send Failure": props<{ error: string }>(),
    "Clear Infer Assistant Error": emptyProps(),
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
    "Save Api Key Failure": props<{ error: string }>(),
    "Test Api Key": emptyProps(),
    "Test Api Key Success": props<{ result: ApiKeyTestResult }>(),
    "Test Api Key Failure": props<{ error: string }>()
  }
});
