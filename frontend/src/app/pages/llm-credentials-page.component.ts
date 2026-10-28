import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, signal } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Store } from "@ngrx/store";

import {
  LLM_PROVIDERS,
  ModelRow,
  describeConflict,
  destinationChanged,
  effectiveUrl,
  modelsFromRows,
  priceLabel,
  providerLabel
} from "../shared/llm/llm-config";
import { LlmCredential, LlmModel, LlmProvider } from "../shared/models/nexus.models";
import { llmConfigActions } from "../store/llm-config.actions";
import {
  selectDefaultImpact,
  selectLlmConflict,
  selectLlmCredentials,
  selectLlmCurrency,
  selectLlmError,
  selectLlmLoading,
  selectLlmProviderUrls,
  selectLlmSavedCount,
  selectLlmTestResult
} from "../store/llm-config.selectors";
import { nexusActions } from "../store/nexus.actions";
import { selectAssistants } from "../store/nexus.selectors";

const EMPTY_ROW: ModelRow = { name: "", inputPrice: "", outputPrice: "" };

/**
 * Chaves de LLM (SPEC-013, RF-87 a RF-89, RF-93). So o administrador acessa;
 * a API repete a verificacao. A chave so e digitada: nunca volta do servidor.
 */
@Component({
  selector: "app-llm-credentials-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: "./llm-credentials-page.component.html",
  host: { class: "flex-1 min-h-0 overflow-y-auto p-4 lg:p-6" }
})
export class LlmCredentialsPageComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);

  protected readonly credentials = this.store.selectSignal(selectLlmCredentials);
  protected readonly providerUrls = this.store.selectSignal(selectLlmProviderUrls);
  protected readonly currency = this.store.selectSignal(selectLlmCurrency);
  protected readonly impact = this.store.selectSignal(selectDefaultImpact);
  protected readonly testResult = this.store.selectSignal(selectLlmTestResult);
  protected readonly loading = this.store.selectSignal(selectLlmLoading);
  protected readonly error = this.store.selectSignal(selectLlmError);
  protected readonly conflict = this.store.selectSignal(selectLlmConflict);
  private readonly assistants = this.store.selectSignal(selectAssistants);
  private readonly savedCount = this.store.selectSignal(selectLlmSavedCount);

  protected readonly providers = LLM_PROVIDERS;
  protected readonly providerLabel = providerLabel;
  protected readonly priceLabel = priceLabel;

  /** ``"new"``: criando; id: editando; ``null``: formulario fechado. */
  protected readonly editing = signal<string | null>(null);
  protected readonly modelRows = signal<ModelRow[]>([{ ...EMPTY_ROW }]);
  protected readonly formErrors = signal<string[]>([]);
  protected readonly confirmingDelete = signal<string | null>(null);
  protected readonly confirmingDefault = signal<string | null>(null);
  /** Modelo escolhido para o teste, por credencial. */
  protected readonly testModels = signal<Record<string, string>>({});
  protected readonly testedId = signal<string | null>(null);

  protected readonly form = this.formBuilder.nonNullable.group({
    name: ["", [Validators.required, Validators.maxLength(100)]],
    provider: ["openai" as LlmProvider, [Validators.required]],
    apiUrl: [""],
    defaultModel: [""],
    apiKey: [""],
    makeDefault: [false]
  });

  /** Modelos digitados, para a escolha do modelo padrao. */
  protected readonly modelNames = computed(() =>
    this.modelRows()
      .map((row) => row.name.trim())
      .filter((name, index, all) => name && all.indexOf(name) === index)
  );

  protected readonly editingCredential = computed(
    () => this.credentials().find((item) => item.id === this.editing()) ?? null
  );

  protected readonly conflictMessage = computed(() => {
    const conflict = this.conflict();
    return conflict ? describeConflict(conflict, (id) => this.assistantName(id)) : null;
  });

  constructor() {
    this.store.dispatch(llmConfigActions.clearFeedback());
    this.store.dispatch(llmConfigActions.loadCredentials());
    this.store.dispatch(nexusActions.loadAssistants());
    // Credencial gravada (contador sobe): fecha o formulario e as confirmacoes.
    let lastSaved = this.savedCount();
    effect(() => {
      const saved = this.savedCount();
      if (saved !== lastSaved) {
        lastSaved = saved;
        this.closeForm();
        this.confirmingDelete.set(null);
        this.confirmingDefault.set(null);
      }
    });
  }

  protected assistantName(assistantId: string): string {
    return this.assistants().find((item) => item.id === assistantId)?.name ?? assistantId;
  }

  protected assistantNames(ids: string[]): string {
    return ids.map((id) => this.assistantName(id)).join(", ");
  }

  protected presetUrl(): string {
    const provider = this.form.controls.provider.value;
    return provider === "custom" ? "" : this.providerUrls()[provider] ?? "";
  }

  protected openCreate(): void {
    this.store.dispatch(llmConfigActions.clearFeedback());
    this.form.reset({
      name: "",
      provider: "openai",
      apiUrl: "",
      defaultModel: "",
      apiKey: "",
      makeDefault: this.credentials().length === 0
    });
    this.modelRows.set([{ ...EMPTY_ROW }]);
    this.formErrors.set([]);
    this.editing.set("new");
  }

  protected openEdit(credential: LlmCredential): void {
    this.store.dispatch(llmConfigActions.clearFeedback());
    this.form.reset({
      name: credential.name,
      provider: credential.provider,
      apiUrl: credential.provider === "custom" ? credential.api_url : "",
      defaultModel: credential.default_model,
      apiKey: "",
      makeDefault: false
    });
    this.modelRows.set(credential.models.map(rowOf));
    this.formErrors.set([]);
    this.editing.set(credential.id);
  }

  protected closeForm(): void {
    this.editing.set(null);
    this.form.controls.apiKey.reset("");
    this.formErrors.set([]);
  }

  protected addModelRow(): void {
    this.modelRows.update((rows) => [...rows, { ...EMPTY_ROW }]);
  }

  protected removeModelRow(index: number): void {
    this.modelRows.update((rows) => rows.filter((_, position) => position !== index));
  }

  protected updateModelRow(index: number, field: keyof ModelRow, value: string): void {
    this.modelRows.update((rows) =>
      rows.map((row, position) => (position === index ? { ...row, [field]: value } : row))
    );
  }

  /** D12: na edicao, destino novo exige chave nova (lido a cada mudanca da tela). */
  protected needsNewKey(): boolean {
    const current = this.editingCredential();
    return current
      ? destinationChanged(
          current,
          this.form.controls.provider.value,
          this.form.controls.apiUrl.value,
          this.providerUrls()
        )
      : false;
  }

  protected save(): void {
    if (this.loading().saveCredential) {
      return;
    }
    const value = this.form.getRawValue();
    const { models, errors } = modelsFromRows(this.modelRows());
    const defaultModel = value.defaultModel || models[0]?.name || "";
    if (!value.name.trim()) {
      errors.push("Informe o nome da credencial.");
    }
    if (value.provider === "custom" && !value.apiUrl.trim()) {
      errors.push("Informe a URL do endpoint compatível com chat completions.");
    }
    if (models.length && !models.some((model) => model.name === defaultModel)) {
      errors.push("O modelo padrão precisa estar na lista de modelos.");
    }
    const creating = this.editing() === "new";
    const current = this.editingCredential();
    const apiKey = value.apiKey.trim();
    if (creating && !apiKey) {
      errors.push("Informe a chave de API.");
    }
    if (
      !creating &&
      current &&
      !apiKey &&
      destinationChanged(current, value.provider, value.apiUrl, this.providerUrls())
    ) {
      errors.push("Ao trocar o provedor ou a URL, informe a chave de API do novo destino.");
    }
    this.formErrors.set(errors);
    if (errors.length) {
      return;
    }
    const input = {
      name: value.name.trim(),
      provider: value.provider,
      api_url: value.provider === "custom" ? value.apiUrl.trim() : null,
      models,
      default_model: defaultModel,
      api_key: apiKey || null,
      make_default: value.makeDefault
    };
    if (creating) {
      this.store.dispatch(llmConfigActions.createCredential({ input }));
    } else if (current) {
      this.store.dispatch(llmConfigActions.updateCredential({ id: current.id, input }));
    }
    this.form.controls.apiKey.reset("");
  }

  protected askDelete(credential: LlmCredential): void {
    this.store.dispatch(llmConfigActions.clearFeedback());
    this.confirmingDelete.set(credential.id);
  }

  protected confirmDelete(credential: LlmCredential): void {
    this.store.dispatch(llmConfigActions.deleteCredential({ id: credential.id }));
  }

  /** D11: antes de trocar a padrao, mostra quem segue e quem vai recuar. */
  protected askDefault(credential: LlmCredential): void {
    this.store.dispatch(llmConfigActions.clearFeedback());
    this.confirmingDefault.set(credential.id);
    this.store.dispatch(
      llmConfigActions.loadDefaultImpact({ id: credential.id, modelNames: null })
    );
  }

  protected cancelDefault(): void {
    this.confirmingDefault.set(null);
    this.store.dispatch(llmConfigActions.clearDefaultImpact());
  }

  protected confirmDefault(credential: LlmCredential): void {
    this.store.dispatch(llmConfigActions.setDefaultCredential({ id: credential.id }));
  }

  protected testModel(credential: LlmCredential): string {
    return this.testModels()[credential.id] ?? credential.default_model;
  }

  protected setTestModel(credential: LlmCredential, model: string): void {
    this.testModels.update((models) => ({ ...models, [credential.id]: model }));
  }

  protected test(credential: LlmCredential): void {
    this.testedId.set(credential.id);
    this.store.dispatch(
      llmConfigActions.testCredential({ id: credential.id, model: this.testModel(credential) })
    );
  }

  protected urlOf(credential: LlmCredential): string {
    return effectiveUrl(credential.provider, credential.api_url, this.providerUrls());
  }

  protected hasUnpricedModels(models: LlmModel[]): boolean {
    return models.some((model) => model.input_per_1k === null);
  }

  protected clearFeedback(): void {
    this.store.dispatch(llmConfigActions.clearFeedback());
  }
}

function rowOf(model: LlmModel): ModelRow {
  return {
    name: model.name,
    inputPrice: model.input_per_1k ?? "",
    outputPrice: model.output_per_1k ?? ""
  };
}
