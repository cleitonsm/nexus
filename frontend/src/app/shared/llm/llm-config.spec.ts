import { describe, expect, it } from "vitest";

import { AssistantRetrieval, LlmCredential } from "../models/nexus.models";
import {
  describeConflict,
  destinationChanged,
  effectiveUrl,
  modelsFromRows,
  parseConflict,
  priceLabel,
  retrievalDraftFrom,
  retrievalInputFrom
} from "./llm-config";

const URLS = {
  openai: "https://api.openai.com/v1/chat/completions",
  gemini: "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
};

function credential(overrides: Partial<LlmCredential> = {}): LlmCredential {
  return {
    id: "c1",
    name: "OpenAI",
    provider: "openai",
    api_url: URLS.openai,
    models: [{ name: "gpt-4o-mini", input_per_1k: null, output_per_1k: null }],
    default_model: "gpt-4o-mini",
    is_default: true,
    key_configured: true,
    assistant_ids: [],
    following_assistant_ids: [],
    ...overrides
  };
}

function retrieval(overrides: Partial<AssistantRetrieval> = {}): AssistantRetrieval {
  return {
    hybrid_enabled: { stored: null, effective: true, origin: "default" },
    candidates: { stored: null, effective: 30, origin: "default" },
    top_k: { stored: null, effective: 5, origin: "default" },
    min_score: { stored: null, effective: 0.1, origin: "default" },
    top_k_clamped: false,
    limits: { candidates: [5, 100], top_k: [1, 20], min_score: [0, 1] },
    ...overrides
  };
}

describe("modelsFromRows (D4, D8)", () => {
  it("keeps names and optional prices, accepting a decimal comma", () => {
    const { models, errors } = modelsFromRows([
      { name: " gpt-4o ", inputPrice: "0,0025", outputPrice: "0.01" },
      { name: "gpt-4o-mini", inputPrice: "", outputPrice: "" },
      { name: "", inputPrice: "", outputPrice: "" }
    ]);
    expect(errors).toEqual([]);
    expect(models).toEqual([
      { name: "gpt-4o", input_per_1k: "0.0025", output_per_1k: "0.01" },
      { name: "gpt-4o-mini", input_per_1k: null, output_per_1k: null }
    ]);
  });

  it("rejects spaces, repeated names, half prices and bad numbers", () => {
    const { errors } = modelsFromRows([
      { name: "gpt 4o", inputPrice: "", outputPrice: "" },
      { name: "m", inputPrice: "", outputPrice: "" },
      { name: "m", inputPrice: "", outputPrice: "" },
      { name: "a", inputPrice: "1", outputPrice: "" },
      { name: "b", inputPrice: "-1", outputPrice: "1" }
    ]);
    expect(errors).toHaveLength(4);
  });

  it("asks for at least one model", () => {
    expect(modelsFromRows([{ name: " ", inputPrice: "", outputPrice: "" }]).errors).toEqual([
      "Informe ao menos um modelo."
    ]);
  });
});

describe("destination (D5, D12)", () => {
  it("uses the preset URL and the typed one only for custom", () => {
    expect(effectiveUrl("gemini", "https://x", URLS)).toBe(URLS.gemini);
    expect(effectiveUrl("custom", " https://x/v1 ", URLS)).toBe("https://x/v1");
  });

  it("flags a new provider or URL, but not an unchanged one", () => {
    const current = credential();
    expect(destinationChanged(current, "openai", "", URLS)).toBe(false);
    expect(destinationChanged(current, "gemini", "", URLS)).toBe(true);
    expect(destinationChanged(current, "custom", URLS.openai, URLS)).toBe(true);
    const custom = credential({ provider: "custom", api_url: "https://x/v1" });
    expect(destinationChanged(custom, "custom", "https://x/v1", URLS)).toBe(false);
    expect(destinationChanged(custom, "custom", "https://y/v1", URLS)).toBe(true);
  });
});

describe("conflict (RN-38)", () => {
  const error = {
    status: 409,
    error: {
      detail: {
        code: "llm_credential_in_use",
        message: "the default credential cannot be removed.",
        assistant_ids: ["a1", "a2"],
        models: [],
        is_default: true
      }
    }
  };

  it("reads the 409 body and ignores other errors", () => {
    expect(parseConflict(error)?.assistant_ids).toEqual(["a1", "a2"]);
    expect(parseConflict({ error: { detail: "x" } })).toBeNull();
    expect(parseConflict(null)).toBeNull();
  });

  it("describes it with assistant names", () => {
    const names: Record<string, string> = { a1: "RH", a2: "Financeiro" };
    const text = describeConflict(parseConflict(error)!, (id) => names[id] ?? id);
    expect(text).toContain("padrão não pode ser excluída");
    expect(text).toContain("RH, Financeiro");
    const models = describeConflict(
      { message: "", assistant_ids: ["a1"], models: ["gpt-4o"], is_default: false },
      (id) => names[id] ?? id
    );
    expect(models).toContain("gpt-4o");
  });
});

describe("priceLabel (D8)", () => {
  it("says when the environment price applies", () => {
    expect(priceLabel({ name: "m", input_per_1k: null, output_per_1k: null }, "USD")).toContain(
      "usa o do ambiente"
    );
    expect(priceLabel({ name: "m", input_per_1k: "1", output_per_1k: "2" }, "USD")).toBe(
      "USD 1 entrada / 2 saída por 1K tokens"
    );
  });
});

describe("retrieval draft (RF-91, D6, T3)", () => {
  it("round-trips the stored values; empty means the default", () => {
    const stored = retrieval({
      hybrid_enabled: { stored: false, effective: false, origin: "assistant" },
      min_score: { stored: 0.3, effective: 0.3, origin: "assistant" }
    });
    const draft = retrievalDraftFrom(stored);
    expect(draft).toEqual({ hybrid: "off", candidates: "", topK: "", minScore: "0.3" });
    expect(retrievalInputFrom(draft, stored)).toEqual({
      input: { hybrid_enabled: false, candidates: null, top_k: null, min_score: 0.3 },
      errors: []
    });
  });

  it("checks the ranges of D6", () => {
    const { errors } = retrievalInputFrom(
      { hybrid: "", candidates: "101", topK: "0", minScore: "1,5" },
      retrieval()
    );
    expect(errors).toHaveLength(3);
  });

  it("checks top k against the effective candidates when both are known", () => {
    const current = retrieval();
    expect(
      retrievalInputFrom({ hybrid: "", candidates: "10", topK: "12", minScore: "" }, current).errors
    ).toHaveLength(1);
    // Candidatos do ambiente (30): top k 12 cabe.
    expect(
      retrievalInputFrom({ hybrid: "", candidates: "", topK: "12", minScore: "" }, current).errors
    ).toEqual([]);
    // Candidatos gravados e apagados agora: o padrao nao e conhecido; a API confere.
    const stored = retrieval({ candidates: { stored: 10, effective: 10, origin: "assistant" } });
    expect(
      retrievalInputFrom({ hybrid: "", candidates: "", topK: "15", minScore: "" }, stored).errors
    ).toEqual([]);
  });
});
