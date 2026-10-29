/**
 * SPEC-017: edicao de nome, descricao e prompt do assistente (CT-137).
 *
 * Intercepta a API do assistente para nao alterar os dados da pilha; o PUT fica
 * numa variavel do teste e sobrevive ao recarregamento, como faria o servidor.
 * Chamadas acessorias da pagina (indice, LLM, recuperacao) recebem 404 e nao
 * entram nas verificacoes. Dados ficticios.
 */
import { Page, Route, expect, test } from "@playwright/test";

import { login } from "./helpers";

const NOW = new Date().toISOString();
const ID = "a-e2e-edicao";

interface Profile {
  name: string;
  description: string | null;
  initial_prompt: string | null;
}

async function mockApi(page: Page, groups: string[]): Promise<{ puts: Profile[] }> {
  const puts: Profile[] = [];
  let current: Profile = {
    name: "Juridico E2E",
    description: "Contratos ficticios",
    initial_prompt: "Aja como advogado ficticio."
  };
  const assistant = () => ({ id: ID, created_at: NOW, groups, ...current });

  await page.route("**/api/assistants", (route) =>
    route.request().method() === "GET" ? route.fulfill({ json: [assistant()] }) : route.fallback()
  );
  await page.route(`**/api/assistants/${ID}`, async (route: Route) => {
    if (route.request().method() !== "PUT") {
      return route.fallback();
    }
    const body = route.request().postDataJSON() as Profile;
    puts.push(body);
    current = body;
    await route.fulfill({ json: assistant() });
  });
  await page.route("**/api/me/home-assistants", (route) =>
    route.fulfill({
      json: { assistant_ids: [ID], default_assistant_id: ID, max: 4, customized: false }
    })
  );
  await page.route(new RegExp(`/api/assistants/${ID}/(documents|conversations)$`), (route) =>
    route.fulfill({ json: [] })
  );
  await page.route(new RegExp(`/api/assistants/${ID}/(index-status|llm|retrieval-settings)$`), (route) =>
    route.fulfill({ status: 404, json: { detail: "ficticio", code: "not_found" } })
  );
  await page.route("**/api/groups", (route) => route.fulfill({ json: groups }));
  return { puts };
}

const profileCard = (page: Page) => page.getByTestId("assistant-profile");

test.describe("CT-137: edicao do assistente (SPEC-017)", () => {
  test("administrador edita nome e prompt e ve o nome novo sem recarregar (RF-108, RF-110)", async ({ page }) => {
    const api = await mockApi(page, []);
    await login(page, "admin.nexus");
    await page.goto("/assistants");

    const card = profileCard(page);
    await expect(card).toBeVisible();
    const save = card.getByTestId("assistant-profile-save");
    await expect(save).toBeDisabled();

    await card.getByLabel("Nome").fill("Juridico E2E editado");
    await card.getByLabel("Prompt inicial").fill("Responda em topicos ficticios.");
    await expect(save).toBeEnabled();
    await save.click();

    await expect.poll(() => api.puts.length).toBe(1);
    expect(api.puts[0]).toEqual({
      name: "Juridico E2E editado",
      description: "Contratos ficticios",
      initial_prompt: "Responda em topicos ficticios."
    });
    await expect(page.getByText("Documentos de Juridico E2E editado")).toBeVisible();
    await expect(save).toBeDisabled();

    await page.reload();
    await expect(profileCard(page).getByLabel("Nome")).toHaveValue("Juridico E2E editado");
  });

  test("prompt vazio mostra o aviso e prompt acima do limite bloqueia (D3, D4)", async ({ page }) => {
    await mockApi(page, []);
    await login(page, "admin.nexus");
    await page.goto("/assistants");

    const card = profileCard(page);
    const prompt = card.getByLabel("Prompt inicial");
    await prompt.fill("");
    await expect(card.getByText("Sem prompt, o assistente usa a instrução padrão do sistema.")).toBeVisible();

    await prompt.fill("p".repeat(4001));
    await expect(card.getByText("4001 / 4000")).toBeVisible();
    await expect(card.getByTestId("assistant-profile-save")).toBeDisabled();
  });

  test("curadora ve o card so no assistente que cura (D1)", async ({ page }) => {
    await mockApi(page, ["rh"]);
    await login(page, "curadora.rh");
    await page.goto("/assistants");
    await expect(profileCard(page)).toBeVisible();
  });

  test("curadora nao ve o card em assistente sem grupo dela (D1)", async ({ page }) => {
    await mockApi(page, []);
    await login(page, "curadora.rh");
    await page.goto("/assistants");
    await expect(page.getByText("Documentos de Juridico E2E")).toBeVisible();
    await expect(profileCard(page)).toHaveCount(0);
  });

  test("usuario comum nao chega a tela do card", async ({ page }) => {
    await mockApi(page, []);
    await login(page, "usuario.rh");
    await page.goto("/assistants");
    await expect(page).toHaveURL(/\/chat$/);
    await expect(profileCard(page)).toHaveCount(0);
  });
});
