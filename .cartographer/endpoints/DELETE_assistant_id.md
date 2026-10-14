# `DELETE /{assistant_id}`

- **operationId**: `delete_assistant`
- **tag**: routes
- **handler**: `backend/src/api/routes/assistants.py::delete_assistant`
- **call tree size**: 10 nodes, 9 edges
- **external calls**: 0 (top 15 below)

## Request
### Parameters
| Name | In | Required | Type | Description |
|------|-----|----------|------|-------------|
| `assistant_id` | path | True | string |  |

## Responses
- **200**: OK

## Internal call tree
```mermaid
flowchart LR
  backend_src_api_routes_assistants_py_delete_assistant["delete_assistant<br/><small>backend/src/api/routes/assistants.py:141</small>"]
  backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user["from_user<br/><small>backend/src/application/dto/access_dto.py:17</small>"]
  backend_src_application_services_access_control_py_AccessControl_audit["audit<br/><small>backend/src/application/services/access_control.py:78</small>"]
  backend_src_application_services_access_control_py_AuditTrail_record["record<br/><small>backend/src/application/services/access_control.py:36</small>"]
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas["execute<br/><small>backend/src/application/use_cases/audit_and_session.py:40</small>"]
  backend_src_application_use_cases_manage_assistant_access_py_DeleteAssistantInpu["DeleteAssistantInput<br/><small>backend/src/application/use_cases/manage_assistant_access.py:34</small>"]
  backend_src_application_use_cases_manage_assistant_access_py_DeleteAssistantUseC["DeleteAssistantUseCase<br/><small>backend/src/application/use_cases/manage_assistant_access.py:39</small>"]
  backend_src_domain_audit_py_AuditEvent["AuditEvent<br/><small>backend/src/domain/audit.py:61</small>"]
  backend_src_domain_interfaces_py_AssistantRepository_delete["delete<br/><small>backend/src/domain/interfaces.py:46</small>"]
  backend_src_domain_interfaces_py_AuditLogRepository_append["append<br/><small>backend/src/domain/interfaces.py:572</small>"]
  backend_src_api_routes_assistants_py_delete_assistant --> backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas
  backend_src_api_routes_assistants_py_delete_assistant --> backend_src_application_use_cases_manage_assistant_access_py_DeleteAssistantInpu
  backend_src_api_routes_assistants_py_delete_assistant --> backend_src_application_use_cases_manage_assistant_access_py_DeleteAssistantUseC
  backend_src_api_routes_assistants_py_delete_assistant --> backend_src_domain_interfaces_py_AssistantRepository_delete
  backend_src_application_services_access_control_py_AccessControl_audit --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_audit_py_AuditEvent
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_api_routes_assistants_py_delete_assistant:::entry
classDef entry fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Internal modules touched
| File | Symbols touched |
|------|------------------|
| `backend/src/application/services/access_control.py` | 2 |
| `backend/src/application/use_cases/manage_assistant_access.py` | 2 |
| `backend/src/domain/interfaces.py` | 2 |
| `backend/src/api/routes/assistants.py` | 1 |
| `backend/src/application/dto/access_dto.py` | 1 |
| `backend/src/application/use_cases/audit_and_session.py` | 1 |
| `backend/src/domain/audit.py` | 1 |

## External dependencies (top 15)
_None or all internal._

## Cross-endpoint reuse
Symbols this endpoint shares with other endpoints (top 20):

| Symbol | Also called from |
|--------|------------------|
| `record` (`backend/src/application/services/access_control.py:36`) | `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, … (+24) |
| `append` (`backend/src/domain/interfaces.py:572`) | `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, … (+24) |
| `from_user` (`backend/src/application/dto/access_dto.py:17`) | `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, … (+23) |
| `AuditEvent` (`backend/src/domain/audit.py:61`) | `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, … (+24) |
| `delete` (`backend/src/domain/interfaces.py:46`) | `DELETE /{conversation_id}`, `DELETE /{document_id}` |
| `execute` (`backend/src/application/use_cases/audit_and_session.py:40`) | `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, … (+23) |
| `audit` (`backend/src/application/services/access_control.py:78`) | `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, … (+24) |
