/** Regras do interceptor, sem Angular, para poderem ser testadas isoladas. */

export const API_PREFIX = "/api/";
export const FORBIDDEN_MESSAGE = "Você não tem permissão para esta operação.";

/** O token so acompanha chamadas a API do Nexus; nunca vai a outros enderecos. */
export function isApiRequest(url: string): boolean {
  return url.startsWith(API_PREFIX);
}

export const SESSION_URL = `${API_PREFIX}me`;

/**
 * Um 401 encerra a sessao e leva ao login, menos na leitura da propria sessao:
 * se a API recusa o token recem-emitido, voltar ao login repetiria o erro sem
 * fim. Esse caso vira uma mensagem na tela.
 */
export function endsSessionOnUnauthorized(url: string): boolean {
  return isApiRequest(url) && url !== SESSION_URL;
}

export function bearer(token: string): string {
  return `Bearer ${token}`;
}
