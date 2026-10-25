import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, signal } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { CdkMenu, CdkMenuItem, CdkMenuTrigger } from "@angular/cdk/menu";
import { ConnectedPosition } from "@angular/cdk/overlay";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { NavigationEnd, Router, RouterOutlet } from "@angular/router";
import { Store } from "@ngrx/store";
import { filter, map } from "rxjs";

import { AdministrationItem, administrationMenu } from "../core/auth/access";

import { authActions } from "../store/auth.actions";
import { selectMenu, selectSessionUser } from "../store/auth.selectors";
import { LlmProvider } from "../shared/models/nexus.models";
import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantConversations,
  selectActiveAssistantId,
  selectApiKeyTestResult,
  selectApiKeyStatus,
  selectAssistants,
  selectCreateAssistantModalOpen,
  selectCurrentConversationId,
  selectError,
  selectLlmSettings,
  selectLoadingState,
  selectNotice
} from "../store/nexus.selectors";

@Component({
  selector: "app-shell",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterOutlet, CdkMenu, CdkMenuItem, CdkMenuTrigger],
  templateUrl: "./shell.component.html"
})
export class ShellComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);
  private readonly router = inject(Router);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  protected readonly conversations = this.store.selectSignal(selectActiveAssistantConversations);
  protected readonly currentConversationId = this.store.selectSignal(selectCurrentConversationId);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly apiKeyStatus = this.store.selectSignal(selectApiKeyStatus);
  protected readonly apiKeyTestResult = this.store.selectSignal(selectApiKeyTestResult);
  protected readonly llmSettings = this.store.selectSignal(selectLlmSettings);
  protected readonly notice = this.store.selectSignal(selectNotice);
  protected readonly createAssistantModalOpen = this.store.selectSignal(
    selectCreateAssistantModalOpen
  );
  /** Usuario da sessao e o que o papel dele pode ver (RF-46). */
  protected readonly user = this.store.selectSignal(selectSessionUser);
  protected readonly menu = this.store.selectSignal(selectMenu);

  protected readonly sidebarCollapsed = signal(false);
  protected readonly mobileSidebarOpen = signal(false);
  protected readonly adminModalOpen = signal(false);
  protected readonly assistantsCollapsed = signal(false);
  protected readonly conversationsCollapsed = signal(false);

  protected readonly sidebarContentVisible = computed(
    () => !this.sidebarCollapsed() || this.mobileSidebarOpen()
  );

  /** SPEC-010 (RF-76): telas do menu Administracao que o papel enxerga. */
  protected readonly administrationItems = computed(() => administrationMenu(this.menu()));

  private readonly currentUrl = toSignal(
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      map((event) => event.urlAfterRedirects)
    ),
    { initialValue: this.router.url }
  );

  /** O botao fica destacado quando a tela atual e uma das do menu. */
  protected readonly administrationActive = computed(() =>
    this.administrationItems().some((item) => this.isAdministrationItemActive(item))
  );

  /** Abre para cima; com a barra recolhida, a direita do icone. */
  protected readonly administrationMenuPositions = computed<ConnectedPosition[]>(() => {
    const above: ConnectedPosition = {
      originX: "start",
      originY: "top",
      overlayX: "start",
      overlayY: "bottom",
      offsetY: -8
    };
    const beside: ConnectedPosition = {
      originX: "end",
      originY: "bottom",
      overlayX: "start",
      overlayY: "bottom",
      offsetX: 8
    };
    return this.sidebarContentVisible() ? [above, beside] : [beside, above];
  });

  protected readonly activeAssistant = computed(() =>
    this.assistants().find((assistant) => assistant.id === this.activeAssistantId()) ?? null
  );

  protected readonly assistantForm = this.formBuilder.nonNullable.group({
    name: ["", [Validators.required, Validators.maxLength(80)]],
    description: [""],
    initialPrompt: [""],
    documentMetadata: [""]
  });

  protected readonly apiKeyForm = this.formBuilder.nonNullable.group({
    apiKey: ["", [Validators.required]]
  });

  /** SPEC-008: provedor, modelo e URL do LLM (a URL so vale para ``custom``). */
  protected readonly llmForm = this.formBuilder.nonNullable.group({
    provider: ["openai" as LlmProvider, [Validators.required]],
    model: ["", [Validators.required, Validators.maxLength(200), Validators.pattern(/^\S+$/)]],
    apiUrl: [""]
  });

  protected readonly llmProviders: { value: LlmProvider; label: string }[] = [
    { value: "openai", label: "OpenAI" },
    { value: "gemini", label: "Gemini (Google)" },
    { value: "custom", label: "Personalizado (compatível com OpenAI)" }
  ];

  private selectedAssistantFiles: File[] = [];

  constructor() {
    // A situacao da chave do LLM e pedida pelo efeito da sessao, so para
    // administradores.
    this.store.dispatch(nexusActions.loadAssistants());

    // SPEC-008: preenche o formulario com a conexao efetiva do LLM sempre que
    // ela chega do servidor.
    effect(() => {
      const settings = this.llmSettings();
      if (settings) {
        this.llmForm.reset({
          provider: settings.provider,
          model: settings.model,
          apiUrl: settings.provider === "custom" ? settings.api_url : ""
        });
      }
    });
  }

  protected isAdministrationItemActive(item: AdministrationItem): boolean {
    if (item.target.kind !== "route") {
      return false;
    }
    const path = this.currentUrl().split(/[?#]/)[0];
    return path === item.target.path;
  }

  protected openAdministrationItem(item: AdministrationItem): void {
    this.closeMobileSidebar();
    if (item.target.kind === "llmSettings") {
      this.openAdminModal();
      return;
    }
    void this.router.navigateByUrl(item.target.path);
  }

  protected logout(): void {
    this.store.dispatch(authActions.logout());
  }

  protected toggleAssistants(): void {
    this.assistantsCollapsed.update((v) => !v);
  }

  protected toggleConversations(): void {
    this.conversationsCollapsed.update((v) => !v);
  }

  protected toggleNavigation(): void {
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      this.mobileSidebarOpen.update((isOpen) => !isOpen);
      return;
    }
    this.sidebarCollapsed.update((isCollapsed) => !isCollapsed);
  }

  protected closeMobileSidebar(): void {
    this.mobileSidebarOpen.set(false);
  }

  protected openCreateAssistantModal(): void {
    if (!this.menu().manageAssistants) {
      return;
    }
    this.store.dispatch(nexusActions.openCreateAssistantModal());
  }

  protected closeCreateAssistantModal(): void {
    this.store.dispatch(nexusActions.closeCreateAssistantModal());
    this.assistantForm.reset({
      name: "",
      description: "",
      initialPrompt: "",
      documentMetadata: ""
    });
    this.selectedAssistantFiles = [];
  }

  protected openAdminModal(): void {
    if (!this.menu().configureLlm) {
      return;
    }
    this.adminModalOpen.set(true);
    this.store.dispatch(nexusActions.loadLlmSettings());
  }

  protected closeAdminModal(): void {
    this.adminModalOpen.set(false);
    this.apiKeyForm.reset({ apiKey: "" });
  }

  protected selectAssistant(assistantId: string): void {
    this.store.dispatch(nexusActions.selectAssistant({ assistantId }));
  }

  protected createAssistant(): void {
    if (this.assistantForm.invalid || this.loading().createAssistant) {
      this.assistantForm.markAllAsTouched();
      return;
    }

    const value = this.assistantForm.getRawValue();
    const metadataRaw = value.documentMetadata.trim();
    let documentMetadata: Record<string, string> = {};
    if (metadataRaw) {
      try {
        documentMetadata = JSON.parse(metadataRaw) as Record<string, string>;
      } catch {
        this.store.dispatch(
          nexusActions.createAssistantFailure({
            error: "Metadata deve estar em JSON válido, por exemplo {\"origem\":\"manual\"}."
          })
        );
        return;
      }
    }

    this.store.dispatch(
      nexusActions.createAssistant({
        name: value.name.trim(),
        description: value.description.trim() ? value.description.trim() : null,
        initialPrompt: value.initialPrompt.trim() ? value.initialPrompt.trim() : null,
        documentFiles: this.selectedAssistantFiles,
        documentMetadata
      })
    );
    this.closeCreateAssistantModal();
  }

  protected onAssistantFilesSelected(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    this.selectedAssistantFiles = Array.from(target?.files ?? []);
  }

  protected createConversation(): void {
    const assistantId = this.activeAssistantId();
    if (!assistantId || this.loading().createConversation) {
      return;
    }
    this.store.dispatch(nexusActions.createConversation({ assistantId }));
  }

  protected selectConversation(conversationId: string): void {
    this.store.dispatch(nexusActions.selectConversation({ conversationId }));
  }

  protected deleteAssistant(assistantId: string, assistantName: string): void {
    if (this.loading().deleteAssistant) {
      return;
    }
    const confirmed = window.confirm(
      `Excluir o assistente "${assistantName}" e todo o seu histórico?`
    );
    if (!confirmed) {
      return;
    }
    this.store.dispatch(nexusActions.deleteAssistant({ assistantId }));
  }

  protected deleteConversation(conversationId: string): void {
    const assistantId = this.activeAssistantId();
    if (!assistantId || this.loading().deleteConversation) {
      return;
    }
    const confirmed = window.confirm("Excluir esta conversa?");
    if (!confirmed) {
      return;
    }
    this.store.dispatch(nexusActions.deleteConversation({ assistantId, conversationId }));
  }

  protected saveApiKey(): void {
    if (this.apiKeyForm.invalid || this.loading().saveApiKey) {
      this.apiKeyForm.markAllAsTouched();
      return;
    }

    this.store.dispatch(
      nexusActions.saveApiKey({
        apiKey: this.apiKeyForm.controls.apiKey.value.trim()
      })
    );
    this.apiKeyForm.reset({ apiKey: "" });
  }

  protected isCustomProvider(): boolean {
    return this.llmForm.controls.provider.value === "custom";
  }

  /** URL que sera usada: a do provedor predefinido ou a digitada. */
  protected llmEndpointPreview(): string {
    const provider = this.llmForm.controls.provider.value;
    if (provider === "custom") {
      return this.llmForm.controls.apiUrl.value.trim();
    }
    return this.llmSettings()?.provider_urls?.[provider] ?? "";
  }

  protected saveLlmSettings(): void {
    const { provider, model, apiUrl } = this.llmForm.getRawValue();
    const needsUrl = provider === "custom";
    if (
      this.llmForm.invalid ||
      (needsUrl && !apiUrl.trim()) ||
      this.loading().saveLlmSettings
    ) {
      this.llmForm.markAllAsTouched();
      return;
    }
    this.store.dispatch(
      nexusActions.saveLlmSettings({
        input: {
          provider,
          model: model.trim(),
          api_url: needsUrl ? apiUrl.trim() : null
        }
      })
    );
  }

  protected testApiKey(): void {
    if (this.loading().testApiKey || !this.apiKeyStatus()?.configured) {
      return;
    }
    this.store.dispatch(nexusActions.testApiKey());
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
