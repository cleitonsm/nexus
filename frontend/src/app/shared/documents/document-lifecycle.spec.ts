import { describe, expect, it } from "vitest";

import { DocumentAccess } from "../models/nexus.models";
import {
  DOCUMENT_POLL_INTERVAL_MS,
  UNEXPECTED_ERROR,
  canReplace,
  canReprocess,
  describeApiError,
  formatBytes,
  hasDocumentsInProgress,
  orderWithVersions,
  pendingVersionOf,
  statusLabel
} from "./document-lifecycle";

const document = (id: string, changes: Partial<DocumentAccess> = {}): DocumentAccess => ({
  id,
  assistant_id: "assistant-1",
  source_name: `${id}.md`,
  created_at: "2026-10-08T10:00:00Z",
  chunk_count: 3,
  groups: [],
  status: "indexado",
  version: 1,
  failure_reason: null,
  size_bytes: 2048,
  replaces_document_id: null,
  content_hash: `hash-${id}`,
  has_original: true,
  ...changes
});

describe("document states (RF-49)", () => {
  it("labels every state in Portuguese", () => {
    expect(statusLabel("pendente")).toBe("Pendente");
    expect(statusLabel("processando")).toBe("Processando");
    expect(statusLabel("indexado")).toBe("Indexado");
    expect(statusLabel("falhou")).toBe("Falhou");
  });

  it("keeps polling only while something is pending or processing (D4)", () => {
    expect(DOCUMENT_POLL_INTERVAL_MS).toBe(3000);
    expect(hasDocumentsInProgress([document("a"), document("b", { status: "falhou" })])).toBe(
      false
    );
    expect(hasDocumentsInProgress([document("a"), document("b", { status: "pendente" })])).toBe(
      true
    );
    expect(hasDocumentsInProgress([document("a", { status: "processando" })])).toBe(true);
    expect(hasDocumentsInProgress([])).toBe(false);
  });
});

describe("document actions", () => {
  it("replaces only indexed documents without a pending version (RF-51)", () => {
    const current = document("doc-1");
    const pending = document("doc-1-v2", { status: "pendente", replaces_document_id: "doc-1" });
    expect(canReplace(current, [current])).toBe(true);
    expect(canReplace(current, [current, pending])).toBe(false);
    expect(pendingVersionOf(current, [current, pending])).toEqual(pending);
    expect(canReplace(document("x", { status: "falhou" }), [])).toBe(false);
    const failedVersion = { ...pending, status: "falhou" as const };
    expect(canReplace(current, [current, failedVersion])).toBe(true);
  });

  it("reprocesses only failed documents with the original stored (RF-54)", () => {
    expect(canReprocess(document("a", { status: "falhou" }))).toBe(true);
    expect(canReprocess(document("a", { status: "falhou", has_original: false }))).toBe(false);
    expect(canReprocess(document("a"))).toBe(false);
  });

  it("lists each new version right below the current one", () => {
    const ordered = orderWithVersions([
      document("v2", { replaces_document_id: "doc-1", status: "processando" }),
      document("doc-2"),
      document("doc-1"),
      document("orfa", { replaces_document_id: "excluido" })
    ]);
    expect(ordered.map((item) => item.id)).toEqual(["doc-2", "doc-1", "v2", "orfa"]);
  });

  it("formats sizes", () => {
    expect(formatBytes(null)).toBe("");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25,0 MB");
  });
});

describe("API errors", () => {
  it("names the existing document on a duplicate upload (RN-26)", () => {
    const error = {
      status: 409,
      error: {
        detail: {
          code: "duplicate_document",
          message: "duplicate",
          document_id: "doc-1",
          source_name: "politica.pdf"
        }
      }
    };
    expect(describeApiError(error)).toBe(
      'Este arquivo já foi enviado a este assistente como "politica.pdf". Nenhum documento novo foi criado.'
    );
  });

  it("uses the text detail and falls back for anything else", () => {
    expect(describeApiError({ error: { detail: "document not found" } })).toBe(
      "document not found"
    );
    expect(describeApiError({ error: { detail: [{ msg: "x" }] } })).toBe(UNEXPECTED_ERROR);
    expect(describeApiError({ error: null })).toBe(UNEXPECTED_ERROR);
    expect(describeApiError("boom")).toBe(UNEXPECTED_ERROR);
  });
});
