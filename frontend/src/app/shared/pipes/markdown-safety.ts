/**
 * Defesa contra exfiltracao pela resposta do LLM (SPEC-006 D12, RF-60).
 *
 * Um documento com injecao de prompt pode levar o LLM a escrever uma imagem
 * cujo endereco carrega dados da conversa; ao ser exibida, o navegador faria a
 * requisicao. Por isso nenhuma imagem e carregada: ela vira o texto
 * ``[imagem: descricao]``. Links ganham ``rel="noopener noreferrer"``. Recebe
 * o HTML ja sanitizado pelo Angular.
 */
const IMAGE_TAG = /<img\b[^>]*>/gi;
const ALT_ATTRIBUTE = /\balt\s*=\s*("([^"]*)"|'([^']*)')/i;
const LINK_WITHOUT_REL = /<a\b(?![^>]*\brel\s*=)/gi;

export function neutralizeRemoteContent(html: string): string {
  return html
    .replace(IMAGE_TAG, (tag) => describeImage(tag))
    .replace(LINK_WITHOUT_REL, '<a rel="noopener noreferrer"');
}

function describeImage(tag: string): string {
  const match = ALT_ATTRIBUTE.exec(tag);
  const alt = (match?.[2] ?? match?.[3] ?? "").trim();
  // O alt sanitizado ja vem com entidades; so os sinais soltos sao escapados.
  const text = alt.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return text ? `[imagem: ${text}]` : "[imagem]";
}
