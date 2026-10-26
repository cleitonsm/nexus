import { expect, test } from "@playwright/test";

// SPEC-011: tema de login "nexus" no Keycloak (CT-87 e CT-88).
// Roda contra a pilha do Compose com o realm de desenvolvimento importado.

test.describe("tema de login do Keycloak (SPEC-011)", () => {
  // O Keycloak escolhe o idioma pelo Accept-Language; o Chromium do Playwright manda
  // en-US por padrão. Fixa pt-BR para o ponto de partida ser o idioma padrão do Nexus.
  test.use({ locale: "pt-BR" });

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#username")).toBeVisible({ timeout: 30_000 });
  });

  test("CT-87: carrega o tema nexus com marca, selo e botao em pilula", async ({ page }) => {
    const themeCss = page.locator('link[rel="stylesheet"][href*="/login/nexus/css/nexus.css"]');
    await expect(themeCss).toHaveCount(1);

    await expect(page.locator("#kc-header-wrapper .nexus-brand")).toHaveText("Nexus");
    await expect(page.locator("#kc-header-wrapper .nexus-badge")).toHaveText("desenvolvimento");

    const button = page.locator("#kc-login");
    await expect(button).toHaveCSS("background-color", "rgb(79, 70, 229)");
    const radius = await button.evaluate((el) => parseFloat(getComputedStyle(el).borderTopLeftRadius));
    expect(radius).toBeGreaterThanOrEqual(9999);

    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(15, 23, 42)");
  });

  test("CT-88: senha errada mostra o erro dentro do cartao", async ({ page }) => {
    await page.locator("#username").fill("usuario.rh");
    await page.locator("#password").fill("senha-errada");
    await page.locator("#kc-login").click();

    // A versão da imagem decide em qual campo o Keycloak prende o erro de credencial
    // (#input-error-username na 26.0.17, #input-error-password na imagem 26.0 em uso).
    const error = page.locator("#input-error-username, #input-error-password").first();
    await expect(error).toBeVisible();
    await expect(error).toHaveCSS("color", "rgb(251, 113, 133)");
    await expect(page.locator(".pf-v5-c-login__main")).toContainText(/inv[aá]lid/i);
  });

  test("CT-88: troca para ingles mantendo o layout", async ({ page }) => {
    await expect(page.locator("#kc-login")).toHaveText("Entrar");
    // O rótulo da opção é traduzido ("Inglês (English)" em pt-BR); o kc_locale da URL não.
    const english = await page
      .locator('#login-select-toggle option[value*="kc_locale=en"]')
      .getAttribute("value");
    await page.locator("#login-select-toggle").selectOption(english ?? "");
    await expect(page.locator("#kc-login")).toHaveText("Sign in");
    await expect(page.locator("#kc-page-title")).toHaveText("Sign in to Nexus");
    await expect(page.locator("#kc-login")).toHaveCSS("background-color", "rgb(79, 70, 229)");
  });

  test("RNF-36: sem rolagem horizontal a 360 px", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
