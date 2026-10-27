"""CT-56 (RNF-23, meta "zero vazamento"): varredura de vazamento por grupo.

Cria um assistente com os documentos ficticios de
``backend/tests/evaluation/datasets/nexus-acesso`` (restritos por grupo), e,
para cada usuario do realm de desenvolvimento, pergunta sobre CADA documento,
inclusive os de outros grupos. Para documentos que o usuario nao pode ver,
nenhum destes pode conter o documento ou seu marcador unico:

* as citacoes e seus trechos na resposta da API;
* o texto da resposta;
* o conteudo enviado ao LLM (simulado no proprio script), que e o vazamento
  mais grave, pois o texto sairia do sistema.

Para documentos permitidos, a pergunta precisa recuperar o documento (controle
contra uma varredura que passa so porque nada e recuperado).

Roda no container do backend, com ``backend/tests/integration`` em
``/app/integration`` e a pasta de dados em ``/app/evaluation``:

  docker compose run --rm --no-deps -v ./backend/tests/integration:/app/integration:ro \
    -v ./backend/tests/evaluation:/app/evaluation -v ./scripts:/app/scripts:ro \
    backend python /app/scripts/validation/leakage_scan.py --out /app/evaluation/reports/acesso

Codigo de saida: 0 sem vazamento; 1 com vazamento ou controle falho; 2 erro.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, "/app/integration")

from stack_support import Api, FakeLLMServer, token_for  # noqa: E402

DATA = Path("/app/evaluation/datasets/nexus-acesso")


def _strip(group: str) -> str:
    return group.strip().lstrip("/")


def scan(data: Path) -> tuple[list[dict], list[str]]:
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    documents = manifest["documents"]
    admin = Api(token_for("admin.nexus"))
    status, assistant = admin.json(
        "POST", "/assistants", payload={"name": f"CT-56 acesso {uuid4().hex[:6]}"}
    )
    if status != 201:
        raise RuntimeError(f"assistente: {status} {assistant}")
    assistant_id = assistant["id"]
    findings: list[dict] = []
    errors: list[str] = []
    credential_id: str | None = None
    try:
        status, _ = admin.json(
            "PUT",
            f"/assistants/{assistant_id}/groups",
            payload={"groups": manifest["assistant_groups"]},
        )
        if status != 200:
            raise RuntimeError(f"grupos do assistente: {status}")
        for item in documents:
            content = (data / item["file"]).read_bytes()
            status, created = admin.upload(
                assistant_id, item["file"], content, groups=json.dumps(item["groups"])
            )
            if status != 202:
                raise RuntimeError(f"envio de {item['file']}: {status} {created}")
            done = admin.wait_indexed(created["id"])
            if done["status"] != "indexado":
                raise RuntimeError(f"{item['file']} nao foi indexado: {done}")
        with FakeLLMServer() as llm:
            # SPEC-013: credencial temporaria so neste assistente; a padrao da
            # pilha nao muda e nenhum texto de teste vai ao provedor real.
            credential_id = _use_fake_llm(admin, assistant_id, llm.url)
            for username, groups in manifest["users"].items():
                api = Api(token_for(username))
                for item in documents:
                    allowed = not item["groups"] or bool(
                        set(item["groups"]) & {_strip(g) for g in groups}
                    )
                    _check(
                        api, assistant_id, llm, username, item, allowed,
                        findings, errors,
                    )
    finally:
        cleanup = Api(token_for("admin.nexus"))
        cleanup.request("DELETE", f"/assistants/{assistant_id}")
        if credential_id:
            cleanup.request("DELETE", f"/admin/llm-credentials/{credential_id}")
    return findings, errors


def _use_fake_llm(admin: Api, assistant_id: str, url: str) -> str:
    status, listed = admin.json("GET", "/admin/llm-credentials")
    if status != 200 or not listed["items"]:
        # A simulada viraria a padrao e nao poderia ser excluida (RN-37/RN-38).
        raise RuntimeError(
            "a pilha nao tem credencial de LLM: cadastre a real antes do CT-56."
        )
    status, created = admin.json(
        "POST",
        "/admin/llm-credentials",
        payload={
            "name": f"CT-56 simulado {uuid4().hex[:6]}",
            "provider": "custom",
            "api_url": url,
            "models": [{"name": "modelo-simulado"}],
            "default_model": "modelo-simulado",
            "api_key": "chave-ficticia-ct56",
        },
    )
    if status != 201:
        raise RuntimeError(f"credencial simulada: {status} {created}")
    status, data = admin.json(
        "PUT",
        f"/assistants/{assistant_id}/llm",
        payload={"credential_id": created["id"], "model": "modelo-simulado"},
    )
    if status != 200:
        raise RuntimeError(f"LLM do assistente: {status} {data}")
    return created["id"]


def _check(api, assistant_id, llm, username, item, allowed, findings, errors) -> None:
    status, conversation = api.json(
        "POST", "/conversations", payload={"assistant_id": assistant_id}
    )
    if status != 201:
        errors.append(f"{username}: conversa {status}")
        return
    llm.requests.clear()
    status, answer = api.json(
        "POST",
        f"/conversations/{conversation['id']}/chat",
        payload={"question": item["question"]},
    )
    if status != 201:
        errors.append(f"{username} x {item['file']}: chat {status}")
        return
    message = answer["assistant_message"]
    surfaces = {
        "citacoes": json.dumps(message["citations"], ensure_ascii=False),
        "resposta": message["content"],
        "enviado ao LLM": json.dumps(llm.requests, ensure_ascii=False),
    }
    cited_files = {c["source_name"] for c in message["citations"]}
    if allowed:
        if item["file"] not in cited_files:
            errors.append(
                f"controle: {username} deveria recuperar {item['file']} e nao recuperou"
            )
        if not llm.requests:
            # Sem isto, a superficie "enviado ao LLM" ficaria sempre vazia e a
            # varredura passaria sem medir nada (revisao do P4 da SPEC-013).
            errors.append(
                f"controle: {username} x {item['file']}: o LLM simulado nao foi chamado"
            )
        return
    if item["file"] in cited_files:
        findings.append(
            {"user": username, "document": item["file"], "where": "fonte citada"}
        )
    for where, text in surfaces.items():
        if item["marker"] in text:
            findings.append(
                {"user": username, "document": item["file"], "where": where}
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        findings, errors = scan(args.data)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de ambiente
        print(f"ERRO: {exc}")
        return 2
    summary = {"leaks": findings, "control_failures": errors}
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "leakage_scan.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    for item in findings:
        print(f"VAZAMENTO: {item}")
    for item in errors:
        print(f"CONTROLE: {item}")
    if findings or errors:
        return 1
    print("OK: nenhum vazamento; todos os controles recuperaram o documento permitido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
