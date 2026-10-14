/** FE-05: selectors de citacoes por mensagem, documentos por estado e menu por papel. */
import { describe, expect, it } from "vitest";

import { Roles } from "../core/auth/auth.models";
import { ChatMessage, Citation, DocumentAccess } from "../shared/models/nexus.models";
import { initialAuthState } from "./auth.reducer";
import { selectMenu } from "./auth.selectors";
import { initialNexusState } from "./nexus.reducer";
import {
  selectActiveDocumentAccess,
  selectCurrentChatStream,
  selectCurrentCitationsByMessage,
  selectCurrentMessages
} from "./nexus.selectors";

const citation = (number: number): Citation => ({
  number,
  document_id: `d${number}`,
  chunk_id: `c${number}`,
  source_name: `doc${number}.md`,
  section_path: "",
  page: null,
  score: 0.9,
  excerpt: "trecho"
});

const message = (id: string, citations?: Citation[]): ChatMessage => ({
  id,
  conversation_id: "c1",
  role: "assistant",
  content: "texto",
  created_at: "2026-10-14T10:00:00Z",
  citations
});

const documentAccess = (id: string, status: DocumentAccess["status"]): DocumentAccess => ({
  id,
  assistant_id: "a1",
  source_name: `${id}.md`,
  created_at: "2026-10-14T10:00:00Z",
  chunk_count: 1,
  groups: [],
  status,
  version: 1,
  failure_reason: null,
  size_bytes: 1,
  replaces_document_id: null,
  content_hash: id,
  has_original: true
});

const nexus = (patch: Partial<typeof initialNexusState>) => ({
  nexus: { ...initialNexusState, ...patch }
});

describe("citacoes por mensagem (RF-38)", () => {
  it("agrupa por id, ordena por numero e ignora mensagens sem fontes", () => {
    const state = nexus({
      currentConversationId: "c1",
      messagesByConversation: {
        c1: [
          message("m1"),
          message("m2", [citation(2), citation(1)]),
          message("m3", [])
        ]
      }
    });
    expect(selectCurrentMessages(state)).toHaveLength(3);
    const grouped = selectCurrentCitationsByMessage(state);
    expect(Object.keys(grouped)).toEqual(["m2"]);
    expect(grouped["m2"].map((item) => item.number)).toEqual([1, 2]);
  });

  it("sem conversa atual nao ha mensagens nem fontes", () => {
    const state = nexus({ currentConversationId: null });
    expect(selectCurrentMessages(state)).toEqual([]);
    expect(selectCurrentCitationsByMessage(state)).toEqual({});
  });
});

describe("documentos do assistente ativo", () => {
  it("devolve a lista do assistente ativo com o estado de cada documento", () => {
    const state = nexus({
      activeAssistantId: "a1",
      documentAccessByAssistant: {
        a1: [documentAccess("d1", "indexado"), documentAccess("d2", "processando")],
        a2: [documentAccess("d3", "falhou")]
      }
    });
    expect(selectActiveDocumentAccess(state).map((item) => item.status)).toEqual([
      "indexado",
      "processando"
    ]);
  });

  it("sem assistente ativo a lista e vazia", () => {
    expect(selectActiveDocumentAccess(nexus({ activeAssistantId: null }))).toEqual([]);
  });
});

describe("resposta em streaming", () => {
  it("so aparece na conversa a que pertence", () => {
    const stream = { conversationId: "c1", question: "?", text: "par" };
    expect(
      selectCurrentChatStream(nexus({ currentConversationId: "c1", chatStream: stream }))
    ).toEqual(stream);
    expect(
      selectCurrentChatStream(nexus({ currentConversationId: "c2", chatStream: stream }))
    ).toBeNull();
    const fresh = { conversationId: null, question: "?", text: "" };
    expect(
      selectCurrentChatStream(nexus({ currentConversationId: "c2", chatStream: fresh }))
    ).toEqual(fresh);
  });
});

describe("menu por papel (RF-46)", () => {
  const menuOf = (roles: string[] | null) =>
    selectMenu({
      auth: {
        ...initialAuthState,
        status: "authenticated",
        user: roles ? { id: "u", name: "U", roles, groups: [] } : null
      }
    });

  it("administrador ve tudo", () => {
    expect(Object.values(menuOf([Roles.admin])).every(Boolean)).toBe(true);
  });

  it("curador gerencia documentos e avaliacoes, nada alem", () => {
    const menu = menuOf([Roles.curator]);
    expect(menu.manageDocuments).toBe(true);
    expect(menu.reviewFeedback).toBe(true);
    expect(menu.manageAssistants).toBe(false);
    expect(menu.configureLlm).toBe(false);
    expect(menu.viewAudit).toBe(false);
    expect(menu.viewUsage).toBe(false);
  });

  it("usuario comum nao ve nenhum item administrativo", () => {
    expect(Object.values(menuOf([Roles.user])).some(Boolean)).toBe(false);
  });

  it("sem sessao nao ha itens", () => {
    expect(Object.values(menuOf(null)).some(Boolean)).toBe(false);
  });
});
