# OpenAPI summary

- Title: Synthetic OpenAPI from cartographer
- Version: synth
- Endpoints: 32

**Note:** synthesized from static endpoint detection — schemas are minimal. Run your server and pass `--live-url http://localhost:PORT/openapi.json` for full schemas.

## Endpoints
| Method | Path | Operation | Tag | Handler |
|--------|------|-----------|-----|---------|
| POST | `/api-key` | `save_api_key` | routes | `backend/src/api/routes/admin.py::save_api_key` |
| GET | `/api-key/status` | `get_api_key_status` | routes | `backend/src/api/routes/admin.py::get_api_key_status` |
| POST | `/api-key/test` | `test_api_key` | routes | `backend/src/api/routes/admin.py::test_api_key` |
| GET | `/audit-events` | `list_audit_events` | routes | `backend/src/api/routes/admin.py::list_audit_events` |
| GET | `/feedback` | `list_feedback` | routes | `backend/src/api/routes/feedback.py::list_feedback` |
| GET | `/feedback/export` | `export_feedback` | routes | `backend/src/api/routes/feedback.py::export_feedback` |
| POST | `/feedback/{feedback_id}/review` | `review_feedback` | routes | `backend/src/api/routes/feedback.py::review_feedback` |
| GET | `/groups` | `list_groups` | routes | `backend/src/api/routes/me.py::list_groups` |
| GET | `/health` | `health` | api | `backend/src/api/main.py::health` |
| GET | `/index-status` | `get_index_status` | routes | `backend/src/api/routes/index.py::get_index_status` |
| POST | `/infer` | `infer_assistant` | routes | `backend/src/api/routes/assistants.py::infer_assistant` |
| GET | `/me` | `get_me` | routes | `backend/src/api/routes/me.py::get_me` |
| POST | `/messages/{message_id}/feedback` | `submit_feedback` | routes | `backend/src/api/routes/feedback.py::submit_feedback` |
| GET | `/metrics` | `metrics` | api | `backend/src/api/main.py::metrics` |
| GET | `/ping` | `RequestContextTests.setUp` | integration | `backend/tests/integration/test_request_context.py::RequestContextTests.setUp` |
| POST | `/reindex` | `start_reindex` | routes | `backend/src/api/routes/index.py::start_reindex` |
| GET | `/usage` | `get_usage_report` | routes | `backend/src/api/routes/admin.py::get_usage_report` |
| GET | `/usage-limits` | `get_usage_limits` | routes | `backend/src/api/routes/admin.py::get_usage_limits` |
| PUT | `/usage-limits` | `update_usage_limits` | routes | `backend/src/api/routes/admin.py::update_usage_limits` |
| DELETE | `/{assistant_id}` | `delete_assistant` | routes | `backend/src/api/routes/assistants.py::delete_assistant` |
| GET | `/{assistant_id}/conversations` | `list_assistant_conversations` | routes | `backend/src/api/routes/assistants.py::list_assistant_conversations` |
| PUT | `/{assistant_id}/groups` | `set_assistant_groups` | routes | `backend/src/api/routes/assistants.py::set_assistant_groups` |
| GET | `/{conversation_id}` | `get_archived_conversation` | routes | `backend/src/api/routes/conversations.py::get_archived_conversation` |
| DELETE | `/{conversation_id}` | `delete_archived_conversation` | routes | `backend/src/api/routes/conversations.py::delete_archived_conversation` |
| POST | `/{conversation_id}/chat` | `chat_with_assistant` | routes | `backend/src/api/routes/conversations.py::chat_with_assistant` |
| POST | `/{conversation_id}/chat/stream` | `chat_with_assistant_stream` | routes | `backend/src/api/routes/conversations.py::chat_with_assistant_stream` |
| POST | `/{conversation_id}/messages` | `add_message` | routes | `backend/src/api/routes/conversations.py::add_message` |
| GET | `/{document_id}` | `get_document` | routes | `backend/src/api/routes/documents.py::get_document` |
| DELETE | `/{document_id}` | `delete_document` | routes | `backend/src/api/routes/documents.py::delete_document` |
| PUT | `/{document_id}/content` | `replace_document` | routes | `backend/src/api/routes/documents.py::replace_document` |
| PUT | `/{document_id}/groups` | `set_document_groups` | routes | `backend/src/api/routes/documents.py::set_document_groups` |
| POST | `/{document_id}/reprocess` | `reprocess_document` | routes | `backend/src/api/routes/documents.py::reprocess_document` |