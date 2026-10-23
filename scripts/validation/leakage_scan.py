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
    status, original = admin.json("GET", "/admin/llm-settings")
    if status != 200:
        raise RuntimeError(f"llm-settings: {status}")
    status, assistant = admin.json(
        "POST", "/assistants", payload={"name": f"CT-56 acesso {uuid4().hex[:6]}"}
    )
    if status != 201:
        raise RuntimeError(f"assistente: {status} {assistant}")
    assistant_id = assistant["id"]
    findings: list[dict] = []
    errors: list[str] = []
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
            status, _ = admin.json(
                "PUT",
                "/admin/llm-settings",
                payload={
                    "provider": "custom",
                    "model": "modelo-simulado",
                    "api_url": llm.url,
                },
            )
            if status != 200:
                raise RuntimeError(f"llm-settings (simulado): {status}")
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
        restore = {"provider": original["provider"], "model": original["model"]}
        if original["provider"] == "custom":
            restore["api_url"] = original["api_url"]
        cleanup.json("PUT", "/admin/llm-settings", payload=restore)
    return findings, errors


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
