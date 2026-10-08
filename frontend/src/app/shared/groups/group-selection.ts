import { parseGroups } from "../../core/auth/access";

/** Grupos marcados no texto separado por virgulas (mesmo formato do campo livre). */
export function selectedGroups(value: string): string[] {
  return parseGroups(value);
}

/** Marca ou desmarca um grupo e devolve o texto normalizado. */
export function toggleGroup(value: string, group: string): string {
  const current = parseGroups(value);
  const next = current.includes(group)
    ? current.filter((item) => item !== group)
    : [...current, group];
  return parseGroups(next.join(",")).join(", ");
}

/**
 * Grupos marcados que nao existem no Keycloak (digitados antes da lista ou
 * removidos do realm). Continuam visiveis para poderem ser desmarcados.
 */
export function unknownGroups(value: string, available: readonly string[]): string[] {
  const known = new Set(available);
  return parseGroups(value).filter((group) => !known.has(group));
}
