import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";
import { Store } from "@ngrx/store";

import { AuditEvent } from "../shared/models/nexus.models";
import { nexusActions } from "../store/nexus.actions";
import {
  selectAssistants,
  selectAuditEvents,
  selectError,
  selectLoadingState
} from "../store/nexus.selectors";

const ACTION_LABELS: Record<string, string> = {
  "auth.session_started": "Início de sessão",
  "access.denied": "Acesso negado",
  "chat.question": "Pergunta",
  "assistant.created": "Assistente criado",
  "assistant.deleted": "Assistente excluído",
  "assistant.groups_changed": "Grupos do assistente alterados",
  "assistant.reindex_started": "Reindexação iniciada",
  "document.uploaded": "Documento enviado",
  "document.groups_changed": "Restrição de documento alterada",
  "llm_api_key.changed": "Chave do LLM alterada",
  "llm_api_key.tested": "Chave do LLM testada",
  "audit.consulted": "Auditoria consultada",
  "audit.purged": "Limpeza por retenção",
  "chat.rate_limited": "Pergunta bloqueada pelo limite de uso",
  "chat.prompt_injection_suspected": "Suspeita de injeção de prompt em documento",
  "feedback.submitted": "Resposta avaliada",
  "feedback.reviewed": "Avaliação revisada pelo curador",
  "feedback.consulted": "Avaliações consultadas",
  "feedback.exported": "Avaliações exportadas",
  "usage.consulted": "Consumo consultado",
  "usage.limits_changed": "Limites de uso alterados",
  "archived_conversation.consulted": "Conversas arquivadas consultadas",
  "archived_conversation.viewed": "Conversa arquivada lida",
  "archived_conversation.deleted": "Conversa arquivada excluída"
};

/** Consulta da trilha de auditoria (UC-13). A trilha so e lida. */
@Component({
  selector: "app-audit-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: "./audit-page.component.html",
  host: { class: "flex-1 min-h-0 overflow-y-auto p-4 lg:p-6" }
})
export class AuditPageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly events = this.store.selectSignal(selectAuditEvents);
  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly actions = Object.entries(ACTION_LABELS).map(([value, label]) => ({
    value,
    label
  }));

  protected readonly filters = this.formBuilder.nonNullable.group({
    userId: [""],
    action: [""],
    assistantId: [""],
    from: [""],
    to: [""]
  });

  constructor() {
    this.search();
  }

  protected search(): void {
    this.store.dispatch(nexusActions.loadAuditEvents({ filters: this.filters.getRawValue() }));
  }

  protected clearFilters(): void {
    this.filters.reset();
    this.search();
  }

  protected actionLabel(event: AuditEvent): string {
    return ACTION_LABELS[event.action] ?? event.action;
  }

  protected userLabel(event: AuditEvent): string {
    const name = event.details["user_name"];
    return typeof name === "string" && name !== event.user_id
      ? `${name} (${event.user_id})`
      : event.user_id;
  }

  /** Documentos recuperados em uma pergunta; so nomes, nunca o texto. */
  protected retrievedDocuments(event: AuditEvent): string[] {
    const retrieved = event.details["retrieved_documents"];
    if (!Array.isArray(retrieved)) {
      return [];
    }
    const names = retrieved
      .map((item: unknown) => (item as { source_name?: unknown } | null)?.source_name)
      .filter((name): name is string => typeof name === "string" && name.length > 0);
    return [...new Set(names)];
  }

  /** Resumo do que mudou, para os eventos que nao sao perguntas. */
  protected summary(event: AuditEvent): string {
    const details = event.details;
    const parts: string[] = [];
    if (typeof details["attempted_action"] === "string") {
      parts.push(`tentativa: ${ACTION_LABELS[details["attempted_action"]] ?? details["attempted_action"]}`);
    }
    if (typeof details["source_name"] === "string") {
      parts.push(`arquivo: ${details["source_name"]}`);
    }
    if (Array.isArray(details["before"]) || Array.isArray(details["after"])) {
      parts.push(`grupos: ${groupList(details["before"])} → ${groupList(details["after"])}`);
    }
    if (details["failed"] === true) {
      parts.push("falhou antes da resposta");
    }
    if (typeof details["removed"] === "number") {
      parts.push(`eventos removidos: ${details["removed"]}`);
    }
    if (details["fallback_used"] === true) {
      parts.push("sem resposta nos documentos");
    }
    return parts.join(" · ");
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}

function groupList(value: unknown): string {
  const groups = Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
  return groups.length > 0 ? groups.join(", ") : "nenhum";
}
