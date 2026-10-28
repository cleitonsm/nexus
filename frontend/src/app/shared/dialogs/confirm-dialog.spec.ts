import { describe, expect, it } from "vitest";

import {
  assistantDeletionDialog,
  canConfirm,
  canDismiss,
  confirmationMatches,
  conversationDeletionDialog,
  conversationLabel,
  deletionDialog,
  deletionOutcome
} from "./confirm-dialog";

describe("confirm dialog rules (SPEC-014, CT-117)", () => {
  it("requires the exact assistant name, ignoring surrounding spaces (D2)", () => {
    expect(confirmationMatches("", "Jurídico")).toBe(false);
    expect(confirmationMatches("jurídico", "Jurídico")).toBe(false);
    expect(confirmationMatches("Juríd", "Jurídico")).toBe(false);
    expect(confirmationMatches("  Jurídico ", "Jurídico")).toBe(true);
  });

  it("does not require typing when the dialog has no text to confirm", () => {
    expect(confirmationMatches("", null)).toBe(true);
  });

  it("blocks the confirmation while busy or before the name is typed", () => {
    const config = assistantDeletionDialog("RH");
    expect(canConfirm(config, "", false)).toBe(false);
    expect(canConfirm(config, "RH", false)).toBe(true);
    expect(canConfirm(config, "RH", true)).toBe(false);
    expect(canConfirm(conversationDeletionDialog("x"), "", false)).toBe(true);
  });

  it("cannot be dismissed while the deletion runs (RF-99)", () => {
    expect(canDismiss(true)).toBe(false);
    expect(canDismiss(false)).toBe(true);
  });

  it("closes after success and stays open showing the error after failure (RF-99)", () => {
    expect(deletionOutcome(false, false, null)).toBeNull();
    expect(deletionOutcome(true, true, null)).toBe("waiting");
    expect(deletionOutcome(true, false, null)).toBe("succeeded");
    expect(deletionOutcome(true, false, "Há uma reindexação em andamento")).toBe("failed");
  });

  it("warns that the vector base is deleted with the assistant (RF-97)", () => {
    const config = assistantDeletionDialog("Jurídico");
    expect(config.title).toContain("Jurídico");
    expect(config.message).toContain("base vetorial");
    expect(config.message).toContain("Deseja continuar?");
    expect(config.consequences.join(" ")).toContain("base vetorial");
    expect(config.requireText).toBe("Jurídico");
  });

  it("builds the conversation dialog without typing (RF-98)", () => {
    const config = deletionDialog({
      kind: "conversation",
      assistantId: "a-1",
      conversationId: "c-1",
      name: "Férias"
    });
    expect(config.title).toBe("Excluir conversa?");
    expect(config.message).toContain("Férias");
    expect(config.requireText).toBeNull();
    expect(config.warning).toBeNull();
  });

  it("labels unnamed conversations by the id prefix", () => {
    expect(conversationLabel({ id: "1234567890", name: null })).toBe("Conversa 12345678");
    expect(conversationLabel({ id: "1234567890", name: " Férias " })).toBe("Férias");
  });
});
