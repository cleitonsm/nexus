# Campanha — candidato `validacao-final-rc2` (2026-10-20/21): interrompida na V3

| Etapa | Commit | Resultado |
|---|---|---|
| V0, V1 | `866e1c1` (rc2) | OK (ambiente limpo, pilha saudável) |
| V2 | `ab210c2` (rc3; a variável `NEXUS_REPORT_DIR` ainda apontava para esta pasta) | OK |
| V3 | `ab210c2` | FALHA: 146 testes de integração, 145 ok (inclusive `GroupDirectoryRealTests`, SPEC-009 D5); o CT-40 mediu 3,17 s no primeiro envio de 25 MB (PDF), acima de 2 s; o DOCX seguinte passou |

Causa: o teste e o medidor da V7 mediam o primeiro envio a frio, sem o aquecimento exigido pela seção 7.1 do
plano de validação. Correção em `2bf956f` (candidato `rc4`): 3 envios descartados no teste e 10 no medidor.
