import { IndexStatus, SparseParameters } from "../models/nexus.models";

/** Intervalo da consulta enquanto uma reindexacao estiver em andamento. */
export const INDEX_POLL_INTERVAL_MS = 3000;

export interface IndexNotice {
  level: "warning" | "info" | "error";
  text: string;
}

export function isReindexRunning(status: IndexStatus | null): boolean {
  return status?.last_reindex?.status === "running";
}

function describeParameters(parameters: SparseParameters | null): string {
  if (!parameters) {
    return "desconhecidos";
  }
  return `k1=${parameters.k1}, b=${parameters.b}, comprimento médio=${parameters.average_length}`;
}

/**
 * Avisos do indice de busca, do mais ao menos grave. A mudanca de parametros
 * do BM25 (PC-D2) so avisa: a busca e os envios continuam funcionando.
 */
export function indexNotices(status: IndexStatus | null): IndexNotice[] {
  if (!status) {
    return [];
  }
  const notices: IndexNotice[] = [];
  if (isReindexRunning(status)) {
    const job = status.last_reindex!;
    notices.push({
      level: "info",
      text: `Reindexação em andamento: ${job.processed_documents} de ${job.total_documents} documentos.`
    });
  } else if (status.last_reindex?.status === "failed") {
    notices.push({
      level: "error",
      text: `A última reindexação falhou: ${status.last_reindex.error ?? "motivo não informado"}.`
    });
  }
  if (status.outdated) {
    notices.push({
      level: "warning",
      text: "A base foi gerada com outro modelo ou outra versão do processamento. Reindexe antes de enviar novos arquivos."
    });
  }
  if (status.sparse_parameters_changed) {
    notices.push({
      level: "warning",
      text:
        "Reindexação necessária: os parâmetros da busca por palavras (BM25) mudaram desde que a base foi gerada " +
        `(base: ${describeParameters(status.sparse_parameters_recorded)}; ` +
        `atual: ${describeParameters(status.sparse_parameters_current)}). ` +
        "A busca continua funcionando, mas só usa os parâmetros novos depois de reindexar."
    });
  }
  if (status.documents_without_original.length > 0) {
    notices.push({
      level: "warning",
      text:
        "Sem o arquivo original, estes documentos ficam de fora da reindexação: " +
        status.documents_without_original.join(", ") +
        "."
    });
  }
  return notices;
}

/** O botao fica disponivel quando ha base e nenhuma reindexacao em curso. */
export function canStartReindex(status: IndexStatus | null): boolean {
  return status !== null && status.documents_total > 0 && !isReindexRunning(status);
}
