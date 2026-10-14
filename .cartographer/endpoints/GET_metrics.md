# `GET /metrics`

- **operationId**: `metrics`
- **tag**: api
- **handler**: `backend/src/api/main.py::metrics`
- **call tree size**: 23 nodes, 32 edges
- **external calls**: 0 (top 15 below)

## Request
_No parameters._

## Responses
- **200**: OK

## Internal call tree
```mermaid
flowchart LR
  backend_src_api_main_py_metrics["metrics<br/><small>backend/src/api/main.py:102</small>"]
  backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user["from_user<br/><small>backend/src/application/dto/access_dto.py:17</small>"]
  backend_src_application_services_access_control_py_AccessControl_audit["audit<br/><small>backend/src/application/services/access_control.py:78</small>"]
  backend_src_application_services_access_control_py_AuditTrail_record["record<br/><small>backend/src/application/services/access_control.py:36</small>"]
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas["execute<br/><small>backend/src/application/use_cases/audit_and_session.py:40</small>"]
  backend_src_application_use_cases_manage_documents_py_DocumentRefInput["DocumentRefInput<br/><small>backend/src/application/use_cases/manage_documents.py:28</small>"]
  backend_src_application_use_cases_manage_documents_py_GetDocumentUseCase["GetDocumentUseCase<br/><small>backend/src/application/use_cases/manage_documents.py:33</small>"]
  backend_src_domain_audit_py_AuditEvent["AuditEvent<br/><small>backend/src/domain/audit.py:61</small>"]
  backend_src_domain_interfaces_py_AuditLogRepository_append["append<br/><small>backend/src/domain/interfaces.py:572</small>"]
  backend_src_infrastructure_composition_py_build_metrics["build_metrics<br/><small>backend/src/infrastructure/composition.py:306</small>"]
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry["MetricsRegistry<br/><small>backend/src/infrastructure/observability/metrics.py:62</small>"]
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry__collect["_collect<br/><small>backend/src/infrastructure/observability/metrics.py:124</small>"]
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render["render<br/><small>backend/src/infrastructure/observability/metrics.py:104</small>"]
  backend_src_infrastructure_observability_metrics_py__Histogram["_Histogram<br/><small>backend/src/infrastructure/observability/metrics.py:45</small>"]
  backend_src_infrastructure_observability_metrics_py__copy["_copy<br/><small>backend/src/infrastructure/observability/metrics.py:134</small>"]
  backend_src_infrastructure_observability_metrics_py__escape["_escape<br/><small>backend/src/infrastructure/observability/metrics.py:184</small>"]
  backend_src_infrastructure_observability_metrics_py__gauge_lines["_gauge_lines<br/><small>backend/src/infrastructure/observability/metrics.py:156</small>"]
  backend_src_infrastructure_observability_metrics_py__header["_header<br/><small>backend/src/infrastructure/observability/metrics.py:168</small>"]
  backend_src_infrastructure_observability_metrics_py__histogram_lines["_histogram_lines<br/><small>backend/src/infrastructure/observability/metrics.py:142</small>"]
  backend_src_infrastructure_observability_metrics_py__label_key["_label_key<br/><small>backend/src/infrastructure/observability/metrics.py:173</small>"]
  backend_src_infrastructure_observability_metrics_py__labels["_labels<br/><small>backend/src/infrastructure/observability/metrics.py:177</small>"]
  backend_src_infrastructure_observability_metrics_py__number["_number<br/><small>backend/src/infrastructure/observability/metrics.py:188</small>"]
  backend_tests_unit_test_document_lifecycle_py_LifecycleTestCase_get["get<br/><small>backend/tests/unit/test_document_lifecycle.py:269</small>"]
  backend_src_api_main_py_metrics --> backend_src_infrastructure_composition_py_build_metrics
  backend_src_api_main_py_metrics --> backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render
  backend_src_api_main_py_metrics --> backend_tests_unit_test_document_lifecycle_py_LifecycleTestCase_get
  backend_src_application_services_access_control_py_AccessControl_audit --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_audit_py_AuditEvent
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_dto_access_dto_py_CurrentUserDTO_from_user
  backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_infrastructure_composition_py_build_metrics --> backend_src_infrastructure_observability_metrics_py_MetricsRegistry
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py_MetricsRegistry__collect
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py__copy
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py__gauge_lines
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py__header
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py__histogram_lines
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py__labels
  backend_src_infrastructure_observability_metrics_py_MetricsRegistry_render --> backend_src_infrastructure_observability_metrics_py__number
  backend_src_infrastructure_observability_metrics_py__copy --> backend_src_infrastructure_observability_metrics_py__Histogram
  backend_src_infrastructure_observability_metrics_py__gauge_lines --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_infrastructure_observability_metrics_py__gauge_lines --> backend_src_infrastructure_observability_metrics_py__header
  backend_src_infrastructure_observability_metrics_py__gauge_lines --> backend_src_infrastructure_observability_metrics_py__label_key
  backend_src_infrastructure_observability_metrics_py__gauge_lines --> backend_src_infrastructure_observability_metrics_py__labels
  backend_src_infrastructure_observability_metrics_py__gauge_lines --> backend_src_infrastructure_observability_metrics_py__number
  backend_src_infrastructure_observability_metrics_py__header --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_infrastructure_observability_metrics_py__header --> backend_tests_unit_test_document_lifecycle_py_LifecycleTestCase_get
  backend_src_infrastructure_observability_metrics_py__histogram_lines --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_infrastructure_observability_metrics_py__histogram_lines --> backend_src_infrastructure_observability_metrics_py__labels
  backend_src_infrastructure_observability_metrics_py__histogram_lines --> backend_src_infrastructure_observability_metrics_py__number
  backend_src_infrastructure_observability_metrics_py__labels --> backend_src_infrastructure_observability_metrics_py__escape
  backend_tests_unit_test_document_lifecycle_py_LifecycleTestCase_get --> backend_src_application_use_cases_audit_and_session_py_DescribeCurrentUserUseCas
  backend_tests_unit_test_document_lifecycle_py_LifecycleTestCase_get --> backend_src_application_use_cases_manage_documents_py_DocumentRefInput
  backend_tests_unit_test_document_lifecycle_py_LifecycleTestCase_get --> backend_src_application_use_cases_manage_documents_py_GetDocumentUseCase
  backend_src_api_main_py_metrics:::entry
classDef entry fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Internal modules touched
| File | Symbols touched |
|------|------------------|
| `backend/src/infrastructure/observability/metrics.py` | 12 |
| `backend/src/application/services/access_control.py` | 2 |
| `backend/src/application/use_cases/manage_documents.py` | 2 |
| `backend/src/api/main.py` | 1 |
| `backend/src/application/dto/access_dto.py` | 1 |
| `backend/src/application/use_cases/audit_and_session.py` | 1 |
| `backend/src/domain/audit.py` | 1 |
| `backend/src/domain/interfaces.py` | 1 |
| `backend/src/infrastructure/composition.py` | 1 |
| `backend/tests/unit/test_document_lifecycle.py` | 1 |

## External dependencies (top 15)
_None or all internal._

## Cross-endpoint reuse
Symbols this endpoint shares with other endpoints (top 20):

| Symbol | Also called from |
|--------|------------------|
| `DocumentRefInput` (`backend/src/application/use_cases/manage_documents.py:28`) | `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, `GET /groups`, … (+9) |
| `GetDocumentUseCase` (`backend/src/application/use_cases/manage_documents.py:33`) | `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, `GET /groups`, `GET /health`, … (+8) |
| `append` (`backend/src/domain/interfaces.py:572`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `execute` (`backend/src/application/use_cases/audit_and_session.py:40`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
| `AuditEvent` (`backend/src/domain/audit.py:61`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `audit` (`backend/src/application/services/access_control.py:78`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `get` (`backend/tests/unit/test_document_lifecycle.py:269`) | `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, `GET /feedback/export`, `GET /groups`, `GET /health`, … (+8) |
| `record` (`backend/src/application/services/access_control.py:36`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `from_user` (`backend/src/application/dto/access_dto.py:17`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+23) |
