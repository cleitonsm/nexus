"""Grupos do realm pela API de administracao do Keycloak (decisao PC-D6).

O backend se autentica como o cliente de servico ``nexus-backend`` (fluxo
client credentials), cuja conta de servico so tem o papel ``query-groups`` do
``realm-management``: le a arvore de grupos e nada mais. Tudo com a biblioteca
padrao, sem dependencia nova.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from urllib import error, parse, request

from src.domain import GroupDirectoryUnavailableError

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_CACHE_SECONDS = 60.0
# Margem para renovar o token antes de ele expirar.
_TOKEN_MARGIN_SECONDS = 10.0
_PAGE_SIZE = 500

PostForm = Callable[[str, dict[str, str]], dict[str, object]]
GetJson = Callable[[str, str], object]


def http_post_form(timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> PostForm:
    def post(url: str, fields: dict[str, str]) -> dict[str, object]:
        body = parse.urlencode(fields).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    return post


def http_get_json(timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> GetJson:
    def get(url: str, token: str) -> object:
        req = request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    return get


class KeycloakGroupDirectory:
    """Nomes de todos os grupos do realm, inclusive subgrupos.

    O token do cliente de servico e a lista ficam em memoria (a lista por
    ``cache_seconds``). Falha de rede, credencial recusada ou resposta
    inesperada viram ``GroupDirectoryUnavailableError``; o segredo nunca vai
    para a mensagem nem para o log.
    """

    def __init__(
        self,
        *,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        post_form: PostForm | None = None,
        get_json: GetJson | None = None,
        clock: Callable[[], float] = time.monotonic,
        cache_seconds: float = DEFAULT_CACHE_SECONDS,
    ) -> None:
        root = base_url.rstrip("/")
        self._token_url = f"{root}/realms/{realm}/protocol/openid-connect/token"
        self._groups_url = f"{root}/admin/realms/{realm}/groups"
        self._client_id = client_id
        self._client_secret = client_secret
        self._post_form = post_form or http_post_form()
        self._get_json = get_json or http_get_json()
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._groups: list[str] | None = None
        self._groups_expire_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def list_groups(self) -> list[str]:
        if not self.configured:
            raise GroupDirectoryUnavailableError(
                "group directory is not configured (KEYCLOAK_BACKEND_CLIENT_SECRET)."
            )
        now = self._clock()
        if self._groups is not None and now < self._groups_expire_at:
            return list(self._groups)
        try:
            names = self._fetch_all(self._access_token(now))
        except GroupDirectoryUnavailableError:
            raise
        except (error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
            # Credencial recusada (401) ou sem papel (403) tambem caem aqui.
            raise GroupDirectoryUnavailableError(
                f"keycloak group directory unavailable: {type(exc).__name__}."
            ) from None
        self._groups = names
        self._groups_expire_at = now + self._cache_seconds
        return list(names)

    def _access_token(self, now: float) -> str:
        if self._token is not None and now < self._token_expires_at:
            return self._token
        payload = self._post_form(
            self._token_url,
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        token = payload["access_token"]
        if not isinstance(token, str) or not token:
            raise ValueError("token endpoint returned no access_token.")
        expires_in = float(payload.get("expires_in", 60))
        self._token = token
        self._token_expires_at = now + max(expires_in - _TOKEN_MARGIN_SECONDS, 0.0)
        return token

    def _fetch_all(self, token: str) -> list[str]:
        names: set[str] = set()
        pending = [self._paged(f"{self._groups_url}?briefRepresentation=true", token)]
        while pending:
            for group in pending.pop():
                if not isinstance(group, dict):
                    raise ValueError("unexpected group representation.")
                name = group.get("name")
                if isinstance(name, str) and name.strip():
                    names.add(name.strip())
                children = group.get("subGroups") or []
                if children:
                    pending.append(list(children))
                elif int(group.get("subGroupCount") or 0) > 0:
                    # Keycloak 23+ nao traz os subgrupos na lista: busca por grupo.
                    pending.append(
                        self._paged(
                            f"{self._groups_url}/{group['id']}/children"
                            "?briefRepresentation=true",
                            token,
                        )
                    )
        return sorted(names, key=str.casefold)

    def _paged(self, url: str, token: str) -> list[object]:
        items: list[object] = []
        first = 0
        while True:
            page = self._get_json(f"{url}&first={first}&max={_PAGE_SIZE}", token)
            if not isinstance(page, list):
                raise ValueError("unexpected groups page.")
            items.extend(page)
            if len(page) < _PAGE_SIZE:
                return items
            first += _PAGE_SIZE
