# `POST /messages/{message_id}/feedback`

- **operationId**: `submit_feedback`
- **tag**: routes
- **handler**: `backend/src/api/routes/feedback.py::submit_feedback`
- **call tree size**: 11 nodes, 10 edges
- **external calls**: 0 (top 15 below)

## Request
### Parameters
| Name | In | Required | Type | Description |
|------|-----|----------|------|-------------|
| `message_id` | path | True | string |  |

## Responses
- **200**: OK

## Internal call tree
```mermaid
flowchart LR
  backend_src_api_routes_feedback_py__response["_response<br/><small>backend/src/api/routes/feedback.py:180</small>"]
  backend_src_api_routes_feedback_py_submit_feedback["submit_feedback<br/><small>backend/src/api/routes/feedback.py:51</small>"]
  backend_src_api_schemas_operations_py_FeedbackResponse["FeedbackResponse<br/><small>backend/src/api/schemas/operations.py:38</small>"]
  backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user["from_user<br/><small>backend/src/application/dto/access_dto.py:17</small>"]
  backend_src_application_services_access_control_py_AccessControl_audit["audit<br/><small>backend/src/application/services/access_control.py:78</small>"]
  backend_src_application_services_access_control_py_AuditTrail_record["record<br/><small>backend/src/application/services/access_control.py:36</small>"]
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas["execute<br/><small>backend/src/application/use_cases/audit_and_session.py:40</small>"]
  backend_src_application_use_cases_manage_feedback_py_SubmitFeedbackInput["SubmitFeedbackInput<br/><small>backend/src/application/use_cases/manage_feedback.py:44</small>"]
  backend_src_application_use_cases_manage_feedback_py_SubmitFeedbackUseCase["SubmitFeedbackUseCase<br/><small>backend/src/application/use_cases/manage_feedback.py:51</small>"]
  backend_src_domain_audit_py_AuditEvent["AuditEvent<br/><small>backend/src/domain/audit.py:61</small>"]
  backend_src_domain_interfaces_py_AuditLogRepository_append["append<br/><small>backend/src/domain/interfaces.py:572</small>"]
  backend_src_api_routes_feedback_py__response --> backend_src_api_schemas_operations_py_FeedbackResponse
  backend_src_api_routes_feedback_py_submit_feedback --> backend_src_api_routes_feedback_py__response
  backend_src_api_routes_feedback_py_submit_feedback --> backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas
  backend_src_api_routes_feedback_py_submit_feedback --> backend_src_application_use_cases_manage_feedback_py_SubmitFeedbackInput
  backend_src_api_routes_feedback_py_submit_feedback --> backend_src_application_use_cases_manage_feedback_py_SubmitFeedbackUseCase
  backend_src_application_services_access_control_py_AccessControl_audit --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_audit_py_AuditEvent
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_api_routes_feedback_py_submit_feedback:::entry
classDef entry fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Internal modules touched
| File | Symbols touched |
|------|------------------|
| `backend/src/api/routes/feedback.py` | 2 |
| `backend/src/application/services/access_control.py` | 2 |
| `backend/src/application/use_cases/manage_feedback.py` | 2 |
| `backend/src/api/schemas/operations.py` | 1 |
| `backend/src/application/dto/access_dto.py` | 1 |
| `backend/src/application/use_cases/audit_and_session.py` | 1 |
| `backend/src/domain/audit.py` | 1 |
| `backend/src/domain/interfaces.py` | 1 |

## External dependencies (top 15)
_None or all internal._

## Cross-endpoint reuse
Symbols this endpoint shares with other endpoints (top 20):

| Symbol | Also called from |
|--------|------------------|
| `_response` (`backend/src/api/routes/feedback.py:180`) | `GET /feedback`, `POST /feedback/{feedback_id}/review` |
| `record` (`backend/src/application/services/access_control.py:36`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `FeedbackResponse` (`backend/src/api/schemas/operations.py:38`) | `GET /feedback`, `POST /feedback/{feedback_id}/review` |
| `append` (`backend/src/domain/interfaces.py:572`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `from_user` (`backend/src/application/dto/access_dto.py:17`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
| `AuditEvent` (`backend/src/domain/audit.py:61`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `execute` (`backend/src/application/use_cases/audit_and_session.py:40`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
| `audit` (`backend/src/application/services/access_control.py:78`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
