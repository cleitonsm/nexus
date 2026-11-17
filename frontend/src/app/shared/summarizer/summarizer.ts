/**
 * SPEC-018: regras puras do resumidor de documentos na tela (RF-113 a RF-119).
 * A API decide; aqui ficam o texto das etapas (D36), a recusa local antes do
 * envio (D16, D17) e as mensagens dos erros com ``code``.
 */

import { Assistant, SummarizerInfo, SummaryDocument, SummaryStage } from "../models/nexus.models";

/** Mesma cadencia da ingestao (SPEC-005). */
export const SUMMARY_POLL_INTERVAL_MS = 3000;

const FINAL_STAGES: readonly SummaryStage[] = ["pronto", "falhou", "expirado"];

export function isSummarizer(assistant: Assistant | null | undefined): boolean {
  return !!assistant?.is_system;
}

/** Etapas em que a tela para de consultar o andamento. */
export function isFinalStage(stage: SummaryStage): boolean {
  return FINAL_STAGES.includes(stage);
}

/** D36: rotulo curto da etapa, com "parte x de y" no resumo. */
export function stageLabel(document: SummaryDocument): string {
  switch (document.stage) {
    case "enviado":
      return "Enviado";
    case "extraindo":
      return "Lendo o documento";
    case "indexando":
      return "Preparando para perguntas";
    case "resumindo":
      return document.total > 0
        ? `Resumindo parte ${Math.min(document.done + 1, document.total)} de ${document.total}`
        : "Resumindo";
    case "pronto":
      return "Resumo pronto";
    case "expirado":
      return "Documento expirado";
    case "falhou":
      return document.questions_available ? "Falha no resumo" : "Falha no processamento";
  }
}

/** Texto de apoio abaixo do rotulo; ``null`` quando nao ha o que dizer. */
export function stageHint(document: SummaryDocument): string | null {
  if (document.stage === "falhou") {
    if (document.questions_available) {
      return "Você ainda pode fazer perguntas sobre o documento.";
    }
    return document.failure_detail || "Envie o arquivo de novo em uma nova conversa.";
  }
  if (document.stage === "expirado") {
    return "Para resumir outro documento, abra uma nova conversa.";
  }
  if (document.questions_available && document.stage === "resumindo") {
    return "Enquanto isso, você já pode fazer perguntas.";
  }
  return null;
}

export function canRetrySummary(document: SummaryDocument | null): boolean {
  return !!document && document.stage === "falhou" && document.questions_available;
}

export function canShowSummary(document: SummaryDocument | null): boolean {
  return !!document && document.stage === "pronto";
}

/** D7 e D8: o clipe so aparece no resumidor e so com a conversa sem documento. */
export function canAttach(document: SummaryDocument | null): boolean {
  return document === null;
}

/** Recusa local (D16, D17); a API continua sendo a guarda. */
export function validateSummaryFile(
  file: { name: string; size: number },
  info: SummarizerInfo | null
): string | null {
  if (file.size === 0) {
    return "O arquivo está vazio.";
  }
  if (!info) {
    return null;
  }
  const dot = file.name.lastIndexOf(".");
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!info.formats.includes(extension)) {
    return `Formato não aceito. Envie ${info.formats.join(", ")}.`;
  }
  if (file.size > info.max_bytes) {
    return `O arquivo passa de ${info.max_megabytes_label}.`;
  }
  return null;
}

const ERROR_MESSAGES: Record<string, string> = {
  conversation_document_exists:
    "Esta conversa já tem um documento. Para resumir outro, abra uma nova conversa.",
  summary_daily_limit: "Você atingiu o limite de documentos de hoje. Tente de novo amanhã.",
  unsupported_format: "Formato não aceito pelo resumidor.",
  payload_too_large: "O arquivo passa do tamanho máximo do resumidor.",
  not_summarizer_conversation: "Documentos só podem ser enviados ao Resumidor de documentos.",
  summary_not_failed: "O resumo não está em falha.",
  summary_not_ready: "O resumo ainda não está pronto."
};

/** Mensagem do erro da API pelo ``code`` (fix-14); sem ``code``, a generica. */
export function describeSummarizerError(error: unknown): string {
  const code = (error as { error?: { code?: unknown } } | null)?.error?.code;
  if (typeof code === "string" && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return "Não foi possível enviar o documento. Tente de novo.";
}
