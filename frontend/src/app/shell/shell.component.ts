import { CommonModule } from "@angular/common";
import { Component, computed, effect, inject, signal, untracked } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { CdkMenu, CdkMenuItem, CdkMenuTrigger } from "@angular/cdk/menu";
import { ConnectedPosition } from "@angular/cdk/overlay";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { NavigationEnd, Router, RouterOutlet } from "@angular/router";
import { Store } from "@ngrx/store";
import { filter, map } from "rxjs";

import { AdministrationItem, administrationMenu } from "../core/auth/access";
import { ConfirmDialogComponent } from "../shared/dialogs/confirm-dialog.component";
import {
  PendingDeletion,
  conversationLabel,
  deletionDialog,
  deletionOutcome
} from "../shared/dialogs/confirm-dialog";
import { NexusIconComponent } from "../shared/icons/nexus-icon.component";
import { newConversationAssistant } from "../shared/home/home-assistants";
import { Assistant, Conversation } from "../shared/models/nexus.models";
import { TooltipDirective } from "../shared/tooltip/tooltip.directive";
import { SidebarSection, itemTooltipDisabled, sidebarToggleLabel } from "./sidebar";

import { authActions } from "../store/auth.actions";
import { selectMenu, selectSessionUser } from "../store/auth.selectors";
import { nexusActions } from "../store/nexus.actions";
import {
  selectActiveAssistantConversations,
  selectActiveAssistantId,
  selectAssistants,
  selectCreateAssistantModalOpen,
  selectCurrentConversationId,
  selectError,
  selectHomeCards,
  selectLoadingState,
  selectNotice
} from "../store/nexus.selectors";

@Component({
  selector: "app-shell",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterOutlet,
    CdkMenu,
    CdkMenuItem,
    CdkMenuTrigger,
    ConfirmDialogComponent,
    NexusIconComponent,
    TooltipDirective
  ],
  templateUrl: "./shell.component.html"
})
export class ShellComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly store = inject(Store);
  private readonly router = inject(Router);

  protected readonly assistants = this.store.selectSignal(selectAssistants);
  protected readonly activeAssistantId = this.store.selectSignal(selectActiveAssistantId);
  private readonly homeCards = this.store.selectSignal(selectHomeCards);
  protected readonly newConversationTarget = computed(() =>
    newConversationAssistant(this.homeCards().defaultId, this.activeAssistantId())
  );
  protected readonly conversations = this.store.selectSignal(selectActiveAssistantConversations);
  protected readonly currentConversationId = this.store.selectSignal(selectCurrentConversationId);
  protected readonly loading = this.store.selectSignal(selectLoadingState);
  protected readonly error = this.store.selectSignal(selectError);
  protected readonly notice = this.store.selectSignal(selectNotice);
  protected readonly createAssistantModalOpen = this.store.selectSignal(
    selectCreateAssistantModalOpen
  );
  /** Usuario da sessao e o que o papel dele pode ver (RF-46). */
  protected readonly user = this.store.selectSignal(selectSessionUser);
  protected readonly menu = this.store.selectSignal(selectMenu);

  protected readonly sidebarCollapsed = signal(true);
  protected readonly mobileSidebarOpen = signal(false);
  protected readonly assistantsCollapsed = signal(false);
  protected readonly conversationsCollapsed = signal(false);

  protected readonly sidebarContentVisible = computed(
    () => !this.sidebarCollapsed() || this.mobileSidebarOpen()
  );

  /** SPEC-015 (RF-102): "Abrir barra lateral" ou "Fechar barra lateral". */
  protected readonly sidebarToggleLabel = computed(() =>
    sidebarToggleLabel(this.sidebarContentVisible())
  );
  /** SPEC-015 (RF-101): tooltip dos itens so com a barra recolhida. */
  protected readonly itemTooltipDisabled = computed(() =>
    itemTooltipDisabled(this.sidebarContentVisible())
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

  private selectedAssistantFiles: File[] = [];

  /** SPEC-014: exclusao aguardando confirmacao no modal (RF-97, RF-98). */
  protected readonly pendingDeletion = signal<PendingDeletion | null>(null);
  private readonly deletionSubmitted = signal(false);
  protected readonly deletionDialog = computed(() => {
    const pending = this.pendingDeletion();
    return pending ? deletionDialog(pending) : null;
  });
  protected readonly deletionBusy = computed(() => {
    const pending = this.pendingDeletion();
    if (!pending) {
      return false;
    }
    return pending.kind === "assistant"
      ? this.loading().deleteAssistant
      : this.loading().deleteConversation;
  });
  /** RF-99: o erro aparece no modal so depois de confirmar. */
  protected readonly deletionError = computed(() =>
    deletionOutcome(this.deletionSubmitted(), this.deletionBusy(), this.error()) === "failed"
      ? this.error()
      : null
  );

  constructor() {
    this.store.dispatch(nexusActions.loadAssistants());
    // RF-99: fecha o modal quando a exclusao termina sem erro.
    effect(() => {
      const outcome = deletionOutcome(
        this.deletionSubmitted(),
        this.deletionBusy(),
        this.error()
      );
      if (outcome === "succeeded") {
        untracked(() => this.resetDeletion());
      }
    });
  }

  protected isAdministrationItemActive(item: AdministrationItem): boolean {
    const path = this.currentUrl().split(/[?#]/)[0];
    return path === item.target.path;
  }

  protected openAdministrationItem(item: AdministrationItem): void {
    this.closeMobileSidebar();
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

  /** SPEC-015 (D4): o icone da secao na barra recolhida abre a barra com a secao aberta. */
  protected openSection(section: SidebarSection): void {
    if (section === "assistants") {
      this.assistantsCollapsed.set(false);
    } else {
      this.conversationsCollapsed.set(false);
    }
    this.sidebarCollapsed.set(false);
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

  /** SPEC-016 (D5, RF-105): "Nova conversa" volta ao assistente padrao. */
  protected createConversation(): void {
    const assistantId = this.newConversationTarget();
    if (!assistantId || this.loading().createConversation) {
      return;
    }
    if (assistantId !== this.activeAssistantId()) {
      this.store.dispatch(nexusActions.applyDefaultAssistant({ assistantId }));
    }
    this.store.dispatch(nexusActions.createConversation({ assistantId }));
  }

  protected selectConversation(conversationId: string): void {
    this.store.dispatch(nexusActions.selectConversation({ conversationId }));
  }

  /** RF-96: so o administrador ve a acao; a API repete a verificacao. */
  protected askDeleteAssistant(assistant: Assistant): void {
    if (!this.menu().manageAssistants || this.pendingDeletion()) {
      return;
    }
    this.pendingDeletion.set({
      kind: "assistant",
      assistantId: assistant.id,
      name: assistant.name
    });
  }

  protected askDeleteConversation(conversation: Conversation): void {
    const assistantId = this.activeAssistantId();
    if (!assistantId || this.pendingDeletion()) {
      return;
    }
    this.pendingDeletion.set({
      kind: "conversation",
      assistantId,
      conversationId: conversation.id,
      name: conversationLabel(conversation)
    });
  }

  protected confirmDeletion(): void {
    const pending = this.pendingDeletion();
    if (!pending || this.deletionBusy()) {
      return;
    }
    this.deletionSubmitted.set(true);
    if (pending.kind === "assistant") {
      this.store.dispatch(nexusActions.deleteAssistant({ assistantId: pending.assistantId }));
    } else {
      this.store.dispatch(
        nexusActions.deleteConversation({
          assistantId: pending.assistantId,
          conversationId: pending.conversationId
        })
      );
    }
  }

  protected cancelDeletion(): void {
    if (this.deletionBusy()) {
      return;
    }
    // O erro ja foi lido no modal; nao fica repetido na tela de chat.
    if (this.deletionError()) {
      this.store.dispatch(nexusActions.clearError());
    }
    this.resetDeletion();
  }

  private resetDeletion(): void {
    this.pendingDeletion.set(null);
    this.deletionSubmitted.set(false);
  }

  protected clearError(): void {
    this.store.dispatch(nexusActions.clearError());
  }
}
