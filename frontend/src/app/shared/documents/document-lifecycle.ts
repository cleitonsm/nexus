import { DocumentAccess, DocumentStatus } from "../models/nexus.models";

/** D4: intervalo da consulta enquanto houver documento pendente ou processando. */
export const DOCUMENT_POLL_INTERVAL_MS = 3000;

const STATUS_LABELS: Record<DocumentStatus, string> = {
  pendente: "Pendente",
  processando: "Processando",
  indexado: "Indexado",
  falhou: "Falhou",
  substituido: "Substituído"
};

export function statusLabel(status: DocumentStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function isInProgress(document: DocumentAccess): boolean {
  return document.status === "pendente" || document.status === "processando";
}

/** RNF-33: a tela consulta de novo so enquanto algo ainda vai mudar. */
export function hasDocumentsInProgress(documents: readonly DocumentAccess[]): boolean {
  return documents.some(isInProgress);
}

/** Nova versao ainda em processamento, se houver (RN-28). */
export function pendingVersionOf(
  document: DocumentAccess,
  documents: readonly DocumentAccess[]
): DocumentAccess | null {
  return (
    documents.find((item) => item.replaces_document_id === document.id && isInProgress(item)) ??
    null
  );
}

/** RF-51: so a versao indexada recebe nova versao, uma de cada vez. */
export function canReplace(
  document: DocumentAccess,
  documents: readonly DocumentAccess[]
): boolean {
  return document.status === "indexado" && pendingVersionOf(document, documents) === null;
}

/** RF-54: reprocessamento so de quem falhou e tem o original guardado. */
export function canReprocess(document: DocumentAccess): boolean {
  return document.status === "falhou" && document.has_original;
}

/**
 * A lista mostra a versao vigente com a nova versao logo abaixo dela; uma nova
 * versao cuja anterior ja saiu da lista aparece normalmente.
 */
export function orderWithVersions(documents: readonly DocumentAccess[]): DocumentAccess[] {
  const ids = new Set(documents.map((item) => item.id));
  const isNested = (item: DocumentAccess) =>
    item.replaces_document_id !== null && ids.has(item.replaces_document_id);
  const ordered: DocumentAccess[] = [];
  for (const item of documents) {
    if (isNested(item)) {
      continue;
    }
    ordered.push(item, ...documents.filter((child) => child.replaces_document_id === item.id));
  }
  return ordered;
}

export function formatBytes(size: number | null): string {
  if (size === null) {
    return "";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(0)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

interface DuplicateDetail {
  code: "duplicate_document";
  message?: string;
  document_id: string;
  source_name: string;
}

function isDuplicateDetail(detail: unknown): detail is DuplicateDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { code?: unknown }).code === "duplicate_document"
  );
}

export const UNEXPECTED_ERROR = "Falha inesperada ao processar a requisição.";

/**
 * Mensagem para o usuario a partir do erro HTTP. O ``detail`` da API e texto,
 * exceto no arquivo duplicado (RN-26), que traz o documento existente.
 */
export function describeApiError(error: unknown): string {
  if (typeof error !== "object" || error === null || !("error" in error)) {
    return UNEXPECTED_ERROR;
  }
  const detail = (error as { error?: { detail?: unknown } }).error?.detail;
  if (isDuplicateDetail(detail)) {
    const name = detail.source_name || "outro documento";
    return `Este arquivo já foi enviado a este assistente como "${name}". Nenhum documento novo foi criado.`;
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return UNEXPECTED_ERROR;
}
