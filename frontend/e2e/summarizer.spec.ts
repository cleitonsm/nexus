/**
 * SPEC-018: resumidor de documentos (CT-151).
 *
 * 1. Fluxo com a API interceptada (sempre roda): boas-vindas sem o campo de
 *    mensagem por cima, envio com retorno imediato, etapas, resumo postado e
 *    "Resumir". Dados ficticios; nada e gravado na pilha.
 * 2. Medicao na pilha real (so com E2E_SUMMARIZER_FILE apontando para um documento
 *    ficticio gerado por scripts/gerar_documentos_resumidor.py): tempo do envio ate
 *    "Resumo pronto" (RNF-40, meta de 5 min) e do "Resumir" (RNF-37, < 1 s).
 */
import { Page, Route, expect, test } from "@playwright/test";

import { login } from "./helpers";

const NOW = new Date().toISOString();
const SUMMARIZER = "system-document-summarizer";
const CONVERSATION = "c-resumidor-e2e";
const ASSISTANTS = [
  {
    id: SUMMARIZER,
    name: "Resumidor de documentos",
    description: "Resume documentos enviados por você.",
    initial_prompt: null,
    created_at: NOW,
    is_system: true
  },
  { id: "a-rh", name: "RH E2E", description: null, initial_prompt: null, created_at: NOW }
];
const INFO = {
  assistant_id: SUMMARIZER,
  formats: [".txt", ".md", ".markdown", ".pdf", ".doc", ".docx"],
  max_bytes: 25 * 1024 * 1024,
  max_megabytes_label: "25 MB",
  max_tokens: 40000,
  pages_hint: "55 a 60",
  retention_days: 30,
  daily_limit: 10,
  out_of_scope: ["comparar dois ou mais documentos"],
  welcome_markdown:
    "Olá! Eu sou o **Resumidor de documentos**.\n\n" +
    Array.from({ length: 12 }, (_, i) => `- Especificação fictícia ${i + 1}.`).join("\n")
};

function documentAt(stage: string, done = 0, total = 0): object {
  return {
    document_id: "d-e2e",
    conversation_id: CONVERSATION,
    source_name: "contrato-ficticio.txt",
    size_bytes: 20,
    stage,
    done,
    total,
    failure_code: null,
    failure_detail: null,
    questions_available: ["resumindo", "pronto"].includes(stage),
    created_at: NOW,
    expires_at: null
  };
}

async function mockApi(page: Page): Promise<void> {
  const stages = [documentAt("extraindo"), documentAt("resumindo", 1, 2), documentAt("pronto", 2, 2)];
  let uploaded = false;
  await page.route("**/api/assistants", (route) =>
    route.request().method() === "GET" ? route.fulfill({ json: ASSISTANTS }) : route.fallback()
  );
  await page.route("**/api/me/home-assistants", (route) =>
    route.fulfill({
      json: {
        assistant_ids: [SUMMARIZER, "a-rh"],
        default_assistant_id: SUMMARIZER,
        max: 4,
        customized: false,
        pinned_assistant_id: SUMMARIZER
      }
    })
  );
  await page.route("**/api/summarizer", (route) => route.fulfill({ json: INFO }));
  await page.route(/\/api\/assistants\/[^/]+\/conversations$/, (route) => route.fulfill({ json: [] }));
  await page.route("**/api/conversations", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          json: {
            id: CONVERSATION,
            assistant_id: SUMMARIZER,
            name: null,
            created_at: NOW,
            updated_at: NOW,
            message_count: 0
          }
        })
      : route.fallback()
  );
  await page.route(`**/api/conversations/${CONVERSATION}/document`, async (route: Route) => {
    if (route.request().method() === "POST") {
      uploaded = true;
      await new Promise((resolve) => setTimeout(resolve, 800)); // envio lento
      return route.fulfill({ status: 202, json: documentAt("enviado") });
    }
    if (!uploaded) {
      return route.fulfill({ status: 404, json: { detail: {}, code: "summary_document_not_found" } });
    }
    return route.fulfill({ json: stages.length > 1 ? stages.shift() : stages[0] });
  });
  await page.route(`**/api/conversations/${CONVERSATION}`, (route) =>
    route.fulfill({
      json: {
        id: CONVERSATION,
        assistant_id: SUMMARIZER,
        created_at: NOW,
        updated_at: NOW,
        messages:
          stages.length === 1 && (stages[0] as { stage: string }).stage === "pronto"
            ? [
                {
                  id: "m-resumo",
                  conversation_id: CONVERSATION,
                  role: "assistant",
                  content: "## Visão geral\nResumo fictício do contrato [1].",
                  created_at: NOW,
                  citations: []
                }
              ]
            : []
      }
    })
  );
}

test.describe("Resumidor de documentos (CT-151)", () => {
  test("boas-vindas, envio, etapas e resumo postado", async ({ page }) => {
    await mockApi(page);
    await login(page, "usuario.rh");

    const welcome = page.getByTestId("summarizer-welcome");
    await expect(welcome).toBeVisible();
    await expect(welcome).toContainText("Resumidor de documentos");
    // O campo de mensagem fica no rodape, sem cobrir o texto (achado da validacao manual).
    await expect(page.locator("div.sticky:has(form)")).toHaveCount(1);

    await page.getByTestId("summary-file-input").setInputFiles({
      name: "contrato-ficticio.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Cláusula 1. Prazo fictício de 30 dias.")
    });
    // Retorno imediato, antes da resposta do envio.
    await expect(page.getByTestId("summary-uploading")).toBeVisible({ timeout: 500 });
    await expect(page.getByTestId("summary-document")).toContainText(/Lendo o documento|Resumindo/, {
      timeout: 15_000
    });
    await expect(page.getByTestId("summary-document")).toContainText("Resumo pronto", { timeout: 15_000 });
    await expect(page.getByText("Resumo fictício do contrato")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("summary-show")).toBeVisible();
    await expect(page.getByTestId("summary-attach")).toBeDisabled();
  });
});

test.describe("Resumidor na pilha real (RNF-37, RNF-40)", () => {
  const file = process.env["E2E_SUMMARIZER_FILE"];
  test.skip(!file, "defina E2E_SUMMARIZER_FILE com um documento ficticio gerado pelo script");
  test.setTimeout(8 * 60_000);

  test("mede o envio ate o resumo e o Resumir", async ({ page }) => {
    await login(page, "usuario.rh");
    await page.getByRole("button", { name: /Resumidor de documentos/ }).first().click();
    const started = Date.now();
    await page.getByTestId("summary-file-input").setInputFiles(file!);
    await expect(page.getByTestId("summary-document")).toContainText("Resumo pronto", {
      timeout: 7 * 60_000
    });
    const toReady = (Date.now() - started) / 1000;
    test.info().annotations.push({ type: "RNF-40 (s)", description: toReady.toFixed(1) });

    const answered = page.waitForResponse((response) => response.url().includes("/chat/stream"));
    const asked = Date.now();
    await page.getByTestId("summary-show").click();
    await (await answered).finished();
    const showSeconds = (Date.now() - asked) / 1000;
    test.info().annotations.push({ type: "RNF-37 (s)", description: showSeconds.toFixed(2) });
    // RNF-40 e meta medida, nao portao: o tempo fica registrado na anotacao e no relatorio.
    // RNF-37 e criterio de aceite: o resumo gravado sai em menos de 1 s.
    expect(showSeconds).toBeLessThan(1);
  });
});
