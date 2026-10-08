import { describe, expect, it } from "vitest";

import { IndexStatus, ReindexJob } from "../models/nexus.models";
import { canStartReindex, indexNotices, isReindexRunning } from "./index-status";

const job = (changes: Partial<ReindexJob> = {}): ReindexJob => ({
  id: "job-1",
  assistant_id: "assistant-1",
  status: "running",
  target_collection: "assistant-assistant-1-v2",
  total_documents: 4,
  processed_documents: 1,
  error: null,
  started_at: "2026-10-08T10:00:00Z",
  finished_at: null,
  ...changes
});

const status = (changes: Partial<IndexStatus> = {}): IndexStatus => ({
  assistant_id: "assistant-1",
  embedding_model: "modelo",
  pipeline_version: "3",
  collection_name: "assistant-assistant-1-v1",
  outdated: false,
  documents_total: 4,
  documents_indexed: 4,
  documents_without_original: [],
  last_reindex: null,
  sparse_parameters_changed: false,
  sparse_parameters_recorded: { k1: 1.2, b: 0.75, average_length: 64 },
  sparse_parameters_current: { k1: 1.2, b: 0.75, average_length: 64 },
  ...changes
});

describe("index status (RF-31, PC-D2)", () => {
  it("has no notice when the base is current", () => {
    expect(indexNotices(status())).toEqual([]);
    expect(indexNotices(null)).toEqual([]);
  });

  it("warns that a reindex is needed when the BM25 parameters changed", () => {
    const notices = indexNotices(
      status({
        sparse_parameters_changed: true,
        sparse_parameters_current: { k1: 1.5, b: 0.75, average_length: 64 }
      })
    );
    expect(notices).toHaveLength(1);
    expect(notices[0].level).toBe("warning");
    expect(notices[0].text).toContain("Reindexação necessária");
    expect(notices[0].text).toContain("k1=1.2");
    expect(notices[0].text).toContain("k1=1.5");
  });

  it("reports progress, failure, outdated base and missing originals", () => {
    expect(indexNotices(status({ last_reindex: job() }))[0]).toEqual({
      level: "info",
      text: "Reindexação em andamento: 1 de 4 documentos."
    });
    expect(
      indexNotices(status({ last_reindex: job({ status: "failed", error: "Qdrant fora" }) }))[0]
        .level
    ).toBe("error");
    expect(indexNotices(status({ outdated: true }))[0].text).toContain("Reindexe");
    expect(
      indexNotices(status({ documents_without_original: ["a.pdf", "b.md"] }))[0].text
    ).toContain("a.pdf, b.md");
  });

  it("allows a reindex only with documents and none running", () => {
    expect(canStartReindex(status())).toBe(true);
    expect(canStartReindex(status({ documents_total: 0 }))).toBe(false);
    expect(canStartReindex(status({ last_reindex: job() }))).toBe(false);
    expect(canStartReindex(status({ last_reindex: job({ status: "succeeded" }) }))).toBe(true);
    expect(canStartReindex(null)).toBe(false);
    expect(isReindexRunning(status({ last_reindex: job() }))).toBe(true);
  });
});
