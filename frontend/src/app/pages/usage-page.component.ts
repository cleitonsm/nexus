import { CommonModule } from "@angular/common";
import { Component, effect, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import { UsageSummary } from "../shared/models/nexus.models";
import { nexusActions } from "../store/nexus.actions";
import {
  selectAssistants,
  selectError,
  selectLoadingState,
  selectNotice,
  selectUsageLimits,
  selectUsageReport
} from "../store/nexus.selectors";

/** Teto aceito pela API para cada janela (MAX_LIMIT_VALUE). */
const MAX_LIMIT = 1_000_000;

/** Periodos rapidos da consulta, em dias. */
const PERIODS = [1, 7, 30, 90];

/**
 * Consumo e custo estimado por usuario e por conversa (RF-57) e limites de
 * perguntas por minuto e por dia (D3). So o administrador acessa.
 */
@Component({
  selector: "app-usage-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: "./usage-page.component.html",
  host: { class: "flex-1 min-h-0 overflow-y-auto p-4 lg:p-6" }
})
export class UsagePageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly report = this.store.selectSignal(selectUsageReport);
  protected readonly limits = this.store.selectSignal(selectUsageLimits);
  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly notice = this.store.selectSignal(selectNotice);
  protected readonly periods = PERIODS;
  protected periodDays = 30;

  protected readonly limitsForm = this.formBuilder.nonNullable.group({
    perMinute: [20, [Validators.required, Validators.min(0), Validators.max(MAX_LIMIT)]],
    perDay: [500, [Validators.required, Validators.min(0), Validators.max(MAX_LIMIT)]]
  });

  constructor() {
    this.loadReport(this.periodDays);
    this.store.dispatch(nexusActions.loadUsageLimits());
    effect(() => {
      const limits = this.limits();
      if (limits) {
        this.limitsForm.setValue({ perMinute: limits.per_minute, perDay: limits.per_day });
      }
    });
  }

  protected loadReport(days: number): void {
    this.periodDays = days;
    const to = new Date();
    const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
    this.store.dispatch(
      nexusActions.loadUsageReport({ from: from.toISOString(), to: to.toISOString() })
    );
  }

  protected saveLimits(): void {
    if (this.limitsForm.invalid || this.loading().saveUsageLimits) {
      this.limitsForm.markAllAsTouched();
      return;
    }
    const { perMinute, perDay } = this.limitsForm.getRawValue();
    this.store.dispatch(
      nexusActions.saveUsageLimits({
        limits: { per_minute: Math.trunc(perMinute), per_day: Math.trunc(perDay) }
      })
    );
  }

  protected userLabel(item: UsageSummary): string {
    return item.user_name || item.user_id || item.key;
  }

  protected assistantName(assistantId: string | null): string {
    if (!assistantId) {
      return "—";
    }
    return this.assistants().find((item) => item.id === assistantId)?.name ?? assistantId;
  }

  protected cost(value: number, currency: string): string {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 4
    }).format(value);
  }

  protected tokens(value: number): string {
    return new Intl.NumberFormat("pt-BR").format(value);
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
