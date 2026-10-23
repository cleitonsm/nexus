# `POST /reindex`

- **operationId**: `start_reindex`
- **tag**: routes
- **handler**: `backend/src/api/routes/index.py::start_reindex`
- **call tree size**: 14 nodes, 13 edges
- **external calls**: 0 (top 15 below)

## Request
_No parameters._

## Responses
- **200**: OK

## Internal call tree
```mermaid
flowchart LR
  backend_src_api_routes_index_py__existing_assistant_id["_existing_assistant_id<br/><small>backend/src/api/routes/index.py:49</small>"]
  backend_src_api_routes_index_py__job_response["_job_response<br/><small>backend/src/api/routes/index.py:68</small>"]
  backend_src_api_routes_index_py_start_reindex["start_reindex<br/><small>backend/src/api/routes/index.py:77</small>"]
  backend_src_api_schemas_index_py_ReindexJobResponse["ReindexJobResponse<br/><small>backend/src/api/schemas/index.py:8</small>"]
  backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user["from_user<br/><small>backend/src/application/dto/access_dto.py:17</small>"]
  backend_src_application_services_access_control_py_AccessControl_audit["audit<br/><small>backend/src/application/services/access_control.py:78</small>"]
  backend_src_application_services_access_control_py_AuditTrail_record["record<br/><small>backend/src/application/services/access_control.py:36</small>"]
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas["execute<br/><small>backend/src/application/use_cases/audit_and_session.py:40</small>"]
  backend_src_application_use_cases_reindex_assistant_py_StartReindexInput["StartReindexInput<br/><small>backend/src/application/use_cases/reindex_assistant.py:61</small>"]
  backend_src_application_use_cases_reindex_assistant_py_StartReindexUseCase["StartReindexUseCase<br/><small>backend/src/application/use_cases/reindex_assistant.py:66</small>"]
  backend_src_domain_audit_py_AuditEvent["AuditEvent<br/><small>backend/src/domain/audit.py:61</small>"]
  backend_src_domain_interfaces_py_AssistantRepository_get_by_id["get_by_id<br/><small>backend/src/domain/interfaces.py:44</small>"]
  backend_src_domain_interfaces_py_AuditLogRepository_append["append<br/><small>backend/src/domain/interfaces.py:572</small>"]
  backend_src_domain_value_objects_py_AssistantId["AssistantId<br/><small>backend/src/domain/value_objects.py:18</small>"]
  backend_src_api_routes_index_py__existing_assistant_id --> backend_src_domain_interfaces_py_AssistantRepository_get_by_id
  backend_src_api_routes_index_py__existing_assistant_id --> backend_src_domain_value_objects_py_AssistantId
  backend_src_api_routes_index_py__job_response --> backend_src_api_schemas_index_py_ReindexJobResponse
  backend_src_api_routes_index_py_start_reindex --> backend_src_api_routes_index_py__existing_assistant_id
  backend_src_api_routes_index_py_start_reindex --> backend_src_api_routes_index_py__job_response
  backend_src_api_routes_index_py_start_reindex --> backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas
  backend_src_api_routes_index_py_start_reindex --> backend_src_application_use_cases_reindex_assistant_py_StartReindexInput
  backend_src_api_routes_index_py_start_reindex --> backend_src_application_use_cases_reindex_assistant_py_StartReindexUseCase
  backend_src_application_services_access_control_py_AccessControl_audit --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_audit_py_AuditEvent
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_api_routes_index_py_start_reindex:::entry
classDef entry fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Internal modules touched
| File | Symbols touched |
|------|------------------|
| `backend/src/api/routes/index.py` | 3 |
| `backend/src/application/services/access_control.py` | 2 |
| `backend/src/application/use_cases/reindex_assistant.py` | 2 |
| `backend/src/domain/interfaces.py` | 2 |
| `backend/src/api/schemas/index.py` | 1 |
| `backend/src/application/dto/access_dto.py` | 1 |
| `backend/src/application/use_cases/audit_and_session.py` | 1 |
| `backend/src/domain/audit.py` | 1 |
| `backend/src/domain/value_objects.py` | 1 |

## External dependencies (top 15)
_None or all internal._

## Cross-endpoint reuse
Symbols this endpoint shares with other endpoints (top 20):

| Symbol | Also called from |
|--------|------------------|
| `record` (`backend/src/application/services/access_control.py:36`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `ReindexJobResponse` (`backend/src/api/schemas/index.py:8`) | `GET /index-status` |
| `append` (`backend/src/domain/interfaces.py:572`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `from_user` (`backend/src/application/dto/access_dto.py:17`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
| `_job_response` (`backend/src/api/routes/index.py:68`) | `GET /index-status` |
| `AuditEvent` (`backend/src/domain/audit.py:61`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `AssistantId` (`backend/src/domain/value_objects.py:18`) | `GET /index-status`, `GET /{assistant_id}/conversations` |
| `get_by_id` (`backend/src/domain/interfaces.py:44`) | `GET /index-status`, `GET /{assistant_id}/conversations`, `GET /{conversation_id}`, `POST /{conversation_id}/chat/stream` |
| `_existing_assistant_id` (`backend/src/api/routes/index.py:49`) | `GET /index-status` |
| `execute` (`backend/src/application/use_cases/audit_and_session.py:40`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
| `audit` (`backend/src/application/services/access_control.py:78`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
