# `POST /api-key/test`

- **operationId**: `test_api_key`
- **tag**: routes
- **handler**: `backend/src/api/routes/admin.py::test_api_key`
- **call tree size**: 17 nodes, 18 edges
- **external calls**: 0 (top 15 below)

## Request
_No parameters._

## Responses
- **200**: OK

## Internal call tree
```mermaid
flowchart LR
  backend_src_api_dependencies_py_UnconfiguredLLMGateway_generate["generate<br/><small>backend/src/api/dependencies.py:272</small>"]
  backend_src_api_dependencies_py_get_configured_llm_model["get_configured_llm_model<br/><small>backend/src/api/dependencies.py:331</small>"]
  backend_src_api_routes_admin_py_test_api_key["test_api_key<br/><small>backend/src/api/routes/admin.py:114</small>"]
  backend_src_api_schemas_admin_py_ApiKeyTestResponse["ApiKeyTestResponse<br/><small>backend/src/api/schemas/admin.py:12</small>"]
  backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user["from_user<br/><small>backend/src/application/dto/access_dto.py:17</small>"]
  backend_src_application_services_access_control_py_AccessControl__deny["_deny<br/><small>backend/src/application/services/access_control.py:195</small>"]
  backend_src_application_services_access_control_py_AccessControl_audit["audit<br/><small>backend/src/application/services/access_control.py:78</small>"]
  backend_src_application_services_access_control_py_AccessControl_require_llm_con["require_llm_configuration<br/><small>backend/src/application/services/access_control.py:127</small>"]
  backend_src_application_services_access_control_py_AuditTrail_record["record<br/><small>backend/src/application/services/access_control.py:36</small>"]
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas["execute<br/><small>backend/src/application/use_cases/audit_and_session.py:40</small>"]
  backend_src_application_use_cases_manage_api_key_py_GetGlobalApiKeyValueUseCase["GetGlobalApiKeyValueUseCase<br/><small>backend/src/application/use_cases/manage_api_key.py:87</small>"]
  backend_src_domain_access_py_AccessPolicy_can_configure_llm["can_configure_llm<br/><small>backend/src/domain/access.py:113</small>"]
  backend_src_domain_audit_py_AuditEvent["AuditEvent<br/><small>backend/src/domain/audit.py:61</small>"]
  backend_src_domain_errors_py_AccessDeniedError["AccessDeniedError<br/><small>backend/src/domain/errors.py:20</small>"]
  backend_src_domain_interfaces_py_AuditLogRepository_append["append<br/><small>backend/src/domain/interfaces.py:572</small>"]
  backend_src_infrastructure_composition_py_llm_model_name["llm_model_name<br/><small>backend/src/infrastructure/composition.py:276</small>"]
  backend_src_infrastructure_llm_http_chat_llm_py_HttpChatCompletionsLLM["HttpChatCompletionsLLM<br/><small>backend/src/infrastructure/llm/http_chat_llm.py:83</small>"]
  backend_src_api_dependencies_py_get_configured_llm_model --> backend_src_infrastructure_composition_py_llm_model_name
  backend_src_api_routes_admin_py_test_api_key --> backend_src_api_dependencies_py_UnconfiguredLLMGateway_generate
  backend_src_api_routes_admin_py_test_api_key --> backend_src_api_dependencies_py_get_configured_llm_model
  backend_src_api_routes_admin_py_test_api_key --> backend_src_api_schemas_admin_py_ApiKeyTestResponse
  backend_src_api_routes_admin_py_test_api_key --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_api_routes_admin_py_test_api_key --> backend_src_application_services_access_control_py_AccessControl_require_llm_con
  backend_src_api_routes_admin_py_test_api_key --> backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas
  backend_src_api_routes_admin_py_test_api_key --> backend_src_application_use_cases_manage_api_key_py_GetGlobalApiKeyValueUseCase
  backend_src_api_routes_admin_py_test_api_key --> backend_src_infrastructure_llm_http_chat_llm_py_HttpChatCompletionsLLM
  backend_src_application_services_access_control_py_AccessControl__deny --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AccessControl__deny --> backend_src_domain_errors_py_AccessDeniedError
  backend_src_application_services_access_control_py_AccessControl_audit --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AccessControl_require_llm_con --> backend_src_application_services_access_control_py_AccessControl__deny
  backend_src_application_services_access_control_py_AccessControl_require_llm_con --> backend_src_domain_access_py_AccessPolicy_can_configure_llm
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_audit_py_AuditEvent
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_api_routes_admin_py_test_api_key:::entry
classDef entry fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Internal modules touched
| File | Symbols touched |
|------|------------------|
| `backend/src/application/services/access_control.py` | 4 |
| `backend/src/api/dependencies.py` | 2 |
| `backend/src/api/routes/admin.py` | 1 |
| `backend/src/api/schemas/admin.py` | 1 |
| `backend/src/application/dto/access_dto.py` | 1 |
| `backend/src/application/use_cases/audit_and_session.py` | 1 |
| `backend/src/application/use_cases/manage_api_key.py` | 1 |
| `backend/src/domain/access.py` | 1 |
| `backend/src/domain/audit.py` | 1 |
| `backend/src/domain/errors.py` | 1 |
| `backend/src/domain/interfaces.py` | 1 |
| `backend/src/infrastructure/composition.py` | 1 |
| `backend/src/infrastructure/llm/http_chat_llm.py` | 1 |

## External dependencies (top 15)
_None or all internal._

## Cross-endpoint reuse
Symbols this endpoint shares with other endpoints (top 20):

| Symbol | Also called from |
|--------|------------------|
| `AccessDeniedError` (`backend/src/domain/errors.py:20`) | `POST /{conversation_id}/chat/stream` |
| `_deny` (`backend/src/application/services/access_control.py:195`) | `POST /{conversation_id}/chat/stream` |
| `append` (`backend/src/domain/interfaces.py:572`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `AuditEvent` (`backend/src/domain/audit.py:61`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `audit` (`backend/src/application/services/access_control.py:78`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `record` (`backend/src/application/services/access_control.py:36`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `from_user` (`backend/src/application/dto/access_dto.py:17`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
| `execute` (`backend/src/application/use_cases/audit_and_session.py:40`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
