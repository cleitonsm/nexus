# Endpoint trace index
- Total endpoints: **32**
- Linked to handler: **32**

## Top 15 endpoints by call-tree size
| Method | Path | Tag | Nodes | Files touched | Card |
|--------|------|-----|-------|---------------|------|
| POST | `/{conversation_id}/chat/stream` | routes | 56 | 14 | [detail](endpoints/POST_conversation_id_chat_stream.md) |
| GET | `/ping` | integration | 29 | 11 | [detail](endpoints/GET_ping.md) |
| GET | `/{conversation_id}` | routes | 24 | 13 | [detail](endpoints/GET_conversation_id.md) |
| GET | `/metrics` | api | 23 | 10 | [detail](endpoints/GET_metrics.md) |
| GET | `/index-status` | routes | 18 | 11 | [detail](endpoints/GET_index-status.md) |
| POST | `/api-key/test` | routes | 17 | 13 | [detail](endpoints/POST_api-key_test.md) |
| POST | `/{conversation_id}/chat` | routes | 17 | 8 | [detail](endpoints/POST_conversation_id_chat.md) |
| GET | `/{assistant_id}/conversations` | routes | 15 | 11 | [detail](endpoints/GET_assistant_id_conversations.md) |
| GET | `/usage` | routes | 15 | 10 | [detail](endpoints/GET_usage.md) |
| GET | `/feedback` | routes | 14 | 10 | [detail](endpoints/GET_feedback.md) |
| POST | `/reindex` | routes | 14 | 9 | [detail](endpoints/POST_reindex.md) |
| GET | `/{document_id}` | routes | 13 | 9 | [detail](endpoints/GET_document_id.md) |
| GET | `/usage-limits` | routes | 13 | 10 | [detail](endpoints/GET_usage-limits.md) |
| GET | `/audit-events` | routes | 13 | 9 | [detail](endpoints/GET_audit-events.md) |
| POST | `/{conversation_id}/messages` | routes | 13 | 8 | [detail](endpoints/POST_conversation_id_messages.md) |

## Functions called from 2+ endpoints (top 20)
| Symbol | File:Line | Used by N endpoints |
|--------|-----------|----------------------|
| `audit` | `backend/src/application/services/access_control.py:78` | 31 |
| `record` | `backend/src/application/services/access_control.py:36` | 31 |
| `AuditEvent` | `backend/src/domain/audit.py:61` | 31 |
| `append` | `backend/src/domain/interfaces.py:572` | 31 |
| `from_user` | `backend/src/application/dto/access_dto.py:17` | 30 |
| `execute` | `backend/src/application/use_cases/audit_and_session.py:40` | 30 |
| `DocumentRefInput` | `backend/src/application/use_cases/manage_documents.py:28` | 16 |
| `GetDocumentUseCase` | `backend/src/application/use_cases/manage_documents.py:33` | 15 |
| `get` | `backend/tests/unit/test_document_lifecycle.py:269` | 15 |
| `get_by_id` | `backend/src/domain/interfaces.py:44` | 5 |
| `_translate_errors` | `backend/src/api/routes/documents.py:307` | 5 |
| `_not_found` | `backend/src/api/routes/conversations.py:92` | 5 |
| `_document_response` | `backend/src/api/routes/documents.py:357` | 4 |
| `DocumentAccessResponse` | `backend/src/api/schemas/access.py:25` | 4 |
| `_message_response` | `backend/src/api/routes/conversations.py:439` | 4 |
| `CitationResponse` | `backend/src/api/schemas/conversations.py:42` | 4 |
| `MessageResponse` | `backend/src/api/schemas/conversations.py:55` | 4 |
| `delete` | `backend/src/domain/interfaces.py:46` | 3 |
| `AssistantId` | `backend/src/domain/value_objects.py:18` | 3 |
| `_response` | `backend/src/api/routes/feedback.py:180` | 3 |