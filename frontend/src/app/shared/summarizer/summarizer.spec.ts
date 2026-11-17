import { describe, expect, it } from "vitest";

import { SummarizerInfo, SummaryDocument } from "../models/nexus.models";
import {
  canAttach,
  canRetrySummary,
  canShowSummary,
  describeSummarizerError,
  isFinalStage,
  isSummarizer,
  stageHint,
  stageLabel,
  validateSummaryFile
} from "./summarizer";

const INFO: SummarizerInfo = {
  assistant_id: "system-document-summarizer",
  formats: [".txt", ".pdf", ".docx"],
  max_bytes: 1000,
  max_megabytes_label: "25 MB",
  max_tokens: 40000,
  pages_hint: "55 a 60",
  retention_days: 30,
  daily_limit: 10,
  out_of_scope: [],
  welcome_markdown: "Olá"
};

function doc(overrides: Partial<SummaryDocument> = {}): SummaryDocument {
  return {
    document_id: "d1",
    conversation_id: "c1",
    source_name: "contrato.pdf",
    size_bytes: 10,
    stage: "enviado",
    done: 0,
    total: 0,
    failure_code: null,
    failure_detail: null,
    questions_available: false,
    created_at: "2026-10-30T12:00:00Z",
    expires_at: null,
    ...overrides
  };
}

describe("resumidor: etapas (CT-150, D36)", () => {
  it("labels every stage", () => {
    expect(stageLabel(doc())).toBe("Enviado");
    expect(stageLabel(doc({ stage: "extraindo" }))).toBe("Lendo o documento");
    expect(stageLabel(doc({ stage: "resumindo", done: 3, total: 9 }))).toBe("Resumindo parte 4 de 9");
    expect(stageLabel(doc({ stage: "resumindo", done: 9, total: 9 }))).toBe("Resumindo parte 9 de 9");
    expect(stageLabel(doc({ stage: "falhou", questions_available: true }))).toBe("Falha no resumo");
    expect(stageLabel(doc({ stage: "falhou" }))).toBe("Falha no processamento");
  });

  it("tells when questions are already available and why it failed", () => {
    expect(stageHint(doc({ stage: "resumindo", questions_available: true }))).toContain("perguntas");
    expect(stageHint(doc({ stage: "falhou", failure_detail: "O documento tem 52.000 tokens" }))).toContain(
      "52.000"
    );
    expect(stageHint(doc())).toBeNull();
  });

  it("stops polling only at final stages", () => {
    expect(isFinalStage("resumindo")).toBe(false);
    expect(["pronto", "falhou", "expirado"].every((stage) => isFinalStage(stage as never))).toBe(true);
  });

  it("enables the actions by stage (RN-64, D31)", () => {
    expect(canRetrySummary(doc({ stage: "falhou", questions_available: true }))).toBe(true);
    expect(canRetrySummary(doc({ stage: "falhou" }))).toBe(false);
    expect(canShowSummary(doc({ stage: "pronto" }))).toBe(true);
    expect(canAttach(null)).toBe(true);
    expect(canAttach(doc())).toBe(false);
  });
});

describe("resumidor: arquivo e erros (CT-150, D16, D17)", () => {
  it("refuses format, size and empty file locally", () => {
    expect(validateSummaryFile({ name: "a.PDF", size: 10 }, INFO)).toBeNull();
    expect(validateSummaryFile({ name: "a.xlsx", size: 10 }, INFO)).toContain("Formato");
    expect(validateSummaryFile({ name: "a.pdf", size: 1001 }, INFO)).toContain("25 MB");
    expect(validateSummaryFile({ name: "a.pdf", size: 0 }, INFO)).toContain("vazio");
    expect(validateSummaryFile({ name: "a.xlsx", size: 10 }, null)).toBeNull();
  });

  it("maps the API codes", () => {
    expect(describeSummarizerError({ error: { code: "summary_daily_limit" } })).toContain("limite");
    expect(describeSummarizerError({ error: { code: "conversation_document_exists" } })).toContain(
      "nova conversa"
    );
    expect(describeSummarizerError(null)).toContain("Não foi possível");
  });

  it("recognizes the system assistant", () => {
    expect(isSummarizer({ id: "x", name: "x", description: null, initial_prompt: null, created_at: "", is_system: true })).toBe(true);
    expect(isSummarizer(null)).toBe(false);
  });
});
