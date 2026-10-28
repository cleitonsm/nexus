/**
 * SPEC-014: regras puras do modal de confirmacao (RF-97 a RF-99).
 * O componente so apresenta; o que exibir e quando fechar vem daqui.
 */

export interface ConfirmDialogConfig {
  title: string;
  /** Pergunta principal, sempre visivel. */
  message: string;
  /** Aviso destacado das consequencias; ``null`` dispensa o bloco. */
  warning: string | null;
  /** Itens que tambem serao excluidos. */
  consequences: readonly string[];
  confirmLabel: string;
  busyLabel: string;
  /** Texto que o usuario precisa digitar para habilitar a confirmacao (D2). */
  requireText: string | null;
}

export type PendingDeletion =
  | { kind: "conversation"; assistantId: string; conversationId: string; name: string }
  | { kind: "assistant"; assistantId: string; name: string };

export type DeletionOutcome = "waiting" | "succeeded" | "failed";

/** D2: o nome digitado, sem espacos nas pontas, precisa ser igual ao esperado. */
export function confirmationMatches(typed: string, expected: string | null): boolean {
  if (expected === null) {
    return true;
  }
  return typed.trim() === expected.trim();
}

export function canConfirm(config: ConfirmDialogConfig, typed: string, busy: boolean): boolean {
  return !busy && confirmationMatches(typed, config.requireText);
}

/** RF-99: durante a exclusao o modal nao fecha por Esc, fundo ou Cancelar. */
export function canDismiss(busy: boolean): boolean {
  return !busy;
}

/**
 * RF-99: depois de confirmar, o modal fecha quando a requisicao termina sem
 * erro e continua aberto mostrando o erro quando ela falha.
 */
export function deletionOutcome(
  submitted: boolean,
  busy: boolean,
  error: string | null
): DeletionOutcome | null {
  if (!submitted) {
    return null;
  }
  if (busy) {
    return "waiting";
  }
  return error ? "failed" : "succeeded";
}

export function conversationLabel(conversation: { id: string; name?: string | null }): string {
  return conversation.name?.trim() || `Conversa ${conversation.id.slice(0, 8)}`;
}

/** RF-97: aviso de que a base vetorial sai junto com o assistente. */
export function assistantDeletionDialog(name: string): ConfirmDialogConfig {
  return {
    title: `Excluir o assistente "${name}"?`,
    message:
      "Ao excluir este assistente, a base vetorial dele também será excluída. Deseja continuar?",
    warning: "Esta ação não pode ser desfeita. Serão excluídos permanentemente:",
    consequences: [
      "a base vetorial do assistente, com todos os trechos indexados",
      "os documentos enviados e seus arquivos originais",
      "as conversas e o histórico de mensagens do assistente",
      "os grupos de acesso e as configurações do assistente"
    ],
    confirmLabel: "Excluir assistente",
    busyLabel: "Excluindo…",
    requireText: name
  };
}

/** RF-98: mesmo modal, sem digitacao. */
export function conversationDeletionDialog(name: string): ConfirmDialogConfig {
  return {
    title: "Excluir conversa?",
    message: `A conversa "${name}" e todas as mensagens dela serão excluídas permanentemente.`,
    warning: null,
    consequences: [],
    confirmLabel: "Excluir",
    busyLabel: "Excluindo…",
    requireText: null
  };
}

export function deletionDialog(pending: PendingDeletion): ConfirmDialogConfig {
  return pending.kind === "assistant"
    ? assistantDeletionDialog(pending.name)
    : conversationDeletionDialog(pending.name);
}
