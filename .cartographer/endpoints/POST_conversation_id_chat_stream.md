# `POST /{conversation_id}/chat/stream`

- **operationId**: `chat_with_assistant_stream`
- **tag**: routes
- **handler**: `backend/src/api/routes/conversations.py::chat_with_assistant_stream`
- **call tree size**: 56 nodes, 70 edges
- **external calls**: 0 (top 15 below)

## Request
### Parameters
| Name | In | Required | Type | Description |
|------|-----|----------|------|-------------|
| `conversation_id` | path | True | string |  |

## Responses
- **200**: OK

## Internal call tree
```mermaid
flowchart LR
  backend_src_api_dependencies_py_UnconfiguredLLMGateway_generate_stream["generate_stream<br/><small>backend/src/api/dependencies.py:284</small>"]
  backend_src_api_routes_conversations_py__chat_error["_chat_error<br/><small>backend/src/api/routes/conversations.py:358</small>"]
  backend_src_api_routes_conversations_py__chat_input["_chat_input<br/><small>backend/src/api/routes/conversations.py:345</small>"]
  backend_src_api_routes_conversations_py__chat_response["_chat_response<br/><small>backend/src/api/routes/conversations.py:425</small>"]
  backend_src_api_routes_conversations_py__in_one_context["_in_one_context<br/><small>backend/src/api/routes/conversations.py:371</small>"]
  backend_src_api_routes_conversations_py__message_response["_message_response<br/><small>backend/src/api/routes/conversations.py:439</small>"]
  backend_src_api_routes_conversations_py__not_found["_not_found<br/><small>backend/src/api/routes/conversations.py:92</small>"]
  backend_src_api_routes_conversations_py__server_sent_events["_server_sent_events<br/><small>backend/src/api/routes/conversations.py:393</small>"]
  backend_src_api_routes_conversations_py__sse["_sse<br/><small>backend/src/api/routes/conversations.py:421</small>"]
  backend_src_api_routes_conversations_py_chat_with_assistant_stream["chat_with_assistant_stream<br/><small>backend/src/api/routes/conversations.py:292</small>"]
  backend_src_api_schemas_conversations_py_ChatResponse["ChatResponse<br/><small>backend/src/api/schemas/conversations.py:71</small>"]
  backend_src_api_schemas_conversations_py_CitationResponse["CitationResponse<br/><small>backend/src/api/schemas/conversations.py:42</small>"]
  backend_src_api_schemas_conversations_py_MessageResponse["MessageResponse<br/><small>backend/src/api/schemas/conversations.py:55</small>"]
  backend_src_application_dto_conversation_dto_py_ChatStreamEvent["ChatStreamEvent<br/><small>backend/src/application/dto/conversation_dto.py:118</small>"]
  backend_src_application_dto_conversation_dto_py_ChatTurnResult["ChatTurnResult<br/><small>backend/src/application/dto/conversation_dto.py:103</small>"]
  backend_src_application_dto_conversation_dto_py_CitationDTO_from_entity["from_entity<br/><small>backend/src/application/dto/conversation_dto.py:54</small>"]
  backend_src_application_dto_conversation_dto_py_MessageDTO_from_entity["from_entity<br/><small>backend/src/application/dto/conversation_dto.py:83</small>"]
  backend_src_application_services_access_control_py_AccessControl__deny["_deny<br/><small>backend/src/application/services/access_control.py:195</small>"]
  backend_src_application_services_access_control_py_AccessControl_audit["audit<br/><small>backend/src/application/services/access_control.py:78</small>"]
  backend_src_application_services_access_control_py_AccessControl_owns_conversati["owns_conversation<br/><small>backend/src/application/services/access_control.py:116</small>"]
  backend_src_application_services_access_control_py_AccessControl_require_assista["require_assistant_access<br/><small>backend/src/application/services/access_control.py:172</small>"]
  backend_src_application_services_access_control_py_AuditTrail_record["record<br/><small>backend/src/application/services/access_control.py:36</small>"]
  backend_src_application_services_usage_py_UsageGovernance_check["check<br/><small>backend/src/application/services/usage.py:68</small>"]
  backend_src_application_services_usage_py_UsageGovernance_current_limits["current_limits<br/><small>backend/src/application/services/usage.py:65</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantInput["ChatWithAssistantInput<br/><small>backend/src/application/use_cases/chat_with_assistant.py:65</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["ChatWithAssistantUseCase<br/><small>backend/src/application/use_cases/chat_with_assistant.py:104</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_audit_failure<br/><small>backend/src/application/use_cases/chat_with_assistant.py:386</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_audit_question<br/><small>backend/src/application/use_cases/chat_with_assistant.py:409</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_check_usage_limit<br/><small>backend/src/application/use_cases/chat_with_assistant.py:194</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_finish_failure<br/><small>backend/src/application/use_cases/chat_with_assistant.py:306</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_finish_success<br/><small>backend/src/application/use_cases/chat_with_assistant.py:274</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_initial_state<br/><small>backend/src/application/use_cases/chat_with_assistant.py:363</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_record_usage<br/><small>backend/src/application/use_cases/chat_with_assistant.py:336</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_start<br/><small>backend/src/application/use_cases/chat_with_assistant.py:165</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_stream_answer<br/><small>backend/src/application/use_cases/chat_with_assistant.py:243</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_stream_events<br/><small>backend/src/application/use_cases/chat_with_assistant.py:220</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["_top_n<br/><small>backend/src/application/use_cases/chat_with_assistant.py:428</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas["start_stream<br/><small>backend/src/application/use_cases/chat_with_assistant.py:155</small>"]
  backend_src_application_use_cases_chat_with_assistant_py_ConversationNotFoundErr["ConversationNotFoundError<br/><small>backend/src/application/use_cases/chat_with_assistant.py:57</small>"]
  backend_src_application_use_cases_chat_with_assistant_py__retrieved["_retrieved<br/><small>backend/src/application/use_cases/chat_with_assistant.py:768</small>"]
  backend_src_application_use_cases_chat_with_assistant_py__turn_attributes["_turn_attributes<br/><small>backend/src/application/use_cases/chat_with_assistant.py:784</small>"]
  backend_src_domain_access_py_AccessPolicy_can_access_assistant["can_access_assistant<br/><small>backend/src/domain/access.py:88</small>"]
  backend_src_domain_access_py_AccessPolicy_owns_conversation["owns_conversation<br/><small>backend/src/domain/access.py:121</small>"]
  backend_src_domain_audit_py_AuditEvent["AuditEvent<br/><small>backend/src/domain/audit.py:61</small>"]
  backend_src_domain_errors_py_AccessDeniedError["AccessDeniedError<br/><small>backend/src/domain/errors.py:20</small>"]
  backend_src_domain_errors_py_UsageLimitExceededError["UsageLimitExceededError<br/><small>backend/src/domain/errors.py:55</small>"]
  backend_src_domain_interfaces_py_AssistantPermissionRepository_get_assistant_gro["get_assistant_groups<br/><small>backend/src/domain/interfaces.py:529</small>"]
  backend_src_domain_interfaces_py_AssistantRepository_get_by_id["get_by_id<br/><small>backend/src/domain/interfaces.py:44</small>"]
  backend_src_domain_interfaces_py_AuditLogRepository_append["append<br/><small>backend/src/domain/interfaces.py:572</small>"]
  backend_src_domain_interfaces_py_UsageSettingsRepository_get_limits["get_limits<br/><small>backend/src/domain/interfaces.py:603</small>"]
  backend_src_domain_observability_py_MetricsRecorder_increment["increment<br/><small>backend/src/domain/observability.py:34</small>"]
  backend_src_domain_observability_py_MetricsRecorder_observe["observe<br/><small>backend/src/domain/observability.py:41</small>"]
  backend_src_domain_observability_py_NoopTracer_span["span<br/><small>backend/src/domain/observability.py:61</small>"]
  backend_src_domain_observability_py__NoopSpan["_NoopSpan<br/><small>backend/src/domain/observability.py:49</small>"]
  backend_src_domain_usage_py_TokenUsage["TokenUsage<br/><small>backend/src/domain/usage.py:28</small>"]
  backend_src_domain_value_objects_py_ConversationId["ConversationId<br/><small>backend/src/domain/value_objects.py:40</small>"]
  backend_src_api_routes_conversations_py__chat_error --> backend_src_api_routes_conversations_py__not_found
  backend_src_api_routes_conversations_py__chat_input --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantInput
  backend_src_api_routes_conversations_py__chat_response --> backend_src_api_routes_conversations_py__message_response
  backend_src_api_routes_conversations_py__chat_response --> backend_src_api_schemas_conversations_py_ChatResponse
  backend_src_api_routes_conversations_py__message_response --> backend_src_api_schemas_conversations_py_CitationResponse
  backend_src_api_routes_conversations_py__message_response --> backend_src_api_schemas_conversations_py_MessageResponse
  backend_src_api_routes_conversations_py__server_sent_events --> backend_src_api_routes_conversations_py__chat_error
  backend_src_api_routes_conversations_py__server_sent_events --> backend_src_api_routes_conversations_py__chat_response
  backend_src_api_routes_conversations_py__server_sent_events --> backend_src_api_routes_conversations_py__in_one_context
  backend_src_api_routes_conversations_py__server_sent_events --> backend_src_api_routes_conversations_py__sse
  backend_src_api_routes_conversations_py_chat_with_assistant_stream --> backend_src_api_routes_conversations_py__chat_error
  backend_src_api_routes_conversations_py_chat_with_assistant_stream --> backend_src_api_routes_conversations_py__chat_input
  backend_src_api_routes_conversations_py_chat_with_assistant_stream --> backend_src_api_routes_conversations_py__server_sent_events
  backend_src_api_routes_conversations_py_chat_with_assistant_stream --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_api_routes_conversations_py_chat_with_assistant_stream --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_dto_conversation_dto_py_MessageDTO_from_entity --> backend_src_application_dto_conversation_dto_py_CitationDTO_from_entity
  backend_src_application_services_access_control_py_AccessControl__deny --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AccessControl__deny --> backend_src_domain_errors_py_AccessDeniedError
  backend_src_application_services_access_control_py_AccessControl_audit --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_services_access_control_py_AccessControl_owns_conversati --> backend_src_domain_access_py_AccessPolicy_owns_conversation
  backend_src_application_services_access_control_py_AccessControl_require_assista --> backend_src_application_services_access_control_py_AccessControl__deny
  backend_src_application_services_access_control_py_AccessControl_require_assista --> backend_src_domain_access_py_AccessPolicy_can_access_assistant
  backend_src_application_services_access_control_py_AccessControl_require_assista --> backend_src_domain_interfaces_py_AssistantPermissionRepository_get_assistant_gro
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_audit_py_AuditEvent
  backend_src_application_services_access_control_py_AuditTrail_record --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_services_usage_py_UsageGovernance_check --> backend_src_application_services_usage_py_UsageGovernance_check
  backend_src_application_services_usage_py_UsageGovernance_check --> backend_src_application_services_usage_py_UsageGovernance_current_limits
  backend_src_application_services_usage_py_UsageGovernance_check --> backend_src_domain_errors_py_UsageLimitExceededError
  backend_src_application_services_usage_py_UsageGovernance_check --> backend_src_domain_observability_py_MetricsRecorder_increment
  backend_src_application_services_usage_py_UsageGovernance_current_limits --> backend_src_domain_interfaces_py_UsageSettingsRepository_get_limits
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py__retrieved
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py__retrieved
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_access_control_py_AccessControl_audit
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_usage_py_UsageGovernance_check
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_observability_py_MetricsRecorder_increment
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_dto_conversation_dto_py_ChatTurnResult
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_dto_conversation_dto_py_MessageDTO_from_entity
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_observability_py_MetricsRecorder_increment
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_usage_py_TokenUsage
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_access_control_py_AuditTrail_record
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_access_control_py_AccessControl_owns_conversati
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_services_access_control_py_AccessControl_require_assista
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ConversationNotFoundErr
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_interfaces_py_AssistantRepository_get_by_id
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_usage_py_TokenUsage
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_value_objects_py_ConversationId
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_api_dependencies_py_UnconfiguredLLMGateway_generate_stream
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_dto_conversation_dto_py_ChatStreamEvent
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_interfaces_py_AuditLogRepository_append
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_observability_py_MetricsRecorder_observe
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_observability_py_NoopTracer_span
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_usage_py_TokenUsage
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_dto_conversation_dto_py_ChatStreamEvent
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py__turn_attributes
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_domain_observability_py_NoopTracer_span
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas --> backend_src_application_use_cases_chat_with_assistant_py_ChatWithAssistantUseCas
  backend_src_domain_observability_py_NoopTracer_span --> backend_src_domain_observability_py__NoopSpan
  backend_src_api_routes_conversations_py_chat_with_assistant_stream:::entry
classDef entry fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Internal modules touched
| File | Symbols touched |
|------|------------------|
| `backend/src/application/use_cases/chat_with_assistant.py` | 17 |
| `backend/src/api/routes/conversations.py` | 9 |
| `backend/src/application/services/access_control.py` | 5 |
| `backend/src/application/dto/conversation_dto.py` | 4 |
| `backend/src/domain/interfaces.py` | 4 |
| `backend/src/domain/observability.py` | 4 |
| `backend/src/api/schemas/conversations.py` | 3 |
| `backend/src/application/services/usage.py` | 2 |
| `backend/src/domain/access.py` | 2 |
| `backend/src/domain/errors.py` | 2 |
| `backend/src/api/dependencies.py` | 1 |
| `backend/src/domain/audit.py` | 1 |
| `backend/src/domain/usage.py` | 1 |
| `backend/src/domain/value_objects.py` | 1 |

## External dependencies (top 15)
_None or all internal._

## Cross-endpoint reuse
Symbols this endpoint shares with other endpoints (top 20):

| Symbol | Also called from |
|--------|------------------|
| `_deny` (`backend/src/application/services/access_control.py:195`) | `POST /api-key/test` |
| `append` (`backend/src/domain/interfaces.py:572`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `from_entity` (`backend/src/application/dto/conversation_dto.py:83`) | `GET /{conversation_id}` |
| `from_entity` (`backend/src/application/dto/conversation_dto.py:54`) | `GET /{conversation_id}` |
| `MessageResponse` (`backend/src/api/schemas/conversations.py:55`) | `GET /{conversation_id}`, `POST /{conversation_id}/chat`, `POST /{conversation_id}/messages` |
| `AuditEvent` (`backend/src/domain/audit.py:61`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `get_by_id` (`backend/src/domain/interfaces.py:44`) | `GET /index-status`, `GET /{assistant_id}/conversations`, `GET /{conversation_id}`, `POST /reindex` |
| `audit` (`backend/src/application/services/access_control.py:78`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `increment` (`backend/src/domain/observability.py:34`) | `GET /ping` |
| `_message_response` (`backend/src/api/routes/conversations.py:439`) | `GET /{conversation_id}`, `POST /{conversation_id}/chat`, `POST /{conversation_id}/messages` |
| `record` (`backend/src/application/services/access_control.py:36`) | `DELETE /{assistant_id}`, `DELETE /{conversation_id}`, `DELETE /{document_id}`, `GET /api-key/status`, `GET /audit-events`, `GET /feedback`, … (+24) |
| `ChatWithAssistantInput` (`backend/src/application/use_cases/chat_with_assistant.py:65`) | `POST /{conversation_id}/chat` |
| `_NoopSpan` (`backend/src/domain/observability.py:49`) | `GET /ping` |
| `_chat_response` (`backend/src/api/routes/conversations.py:425`) | `POST /{conversation_id}/chat` |
| `CitationResponse` (`backend/src/api/schemas/conversations.py:42`) | `GET /{conversation_id}`, `POST /{conversation_id}/chat`, `POST /{conversation_id}/messages` |
| `AccessDeniedError` (`backend/src/domain/errors.py:20`) | `POST /api-key/test` |
| `ChatWithAssistantUseCase` (`backend/src/application/use_cases/chat_with_assistant.py:104`) | `POST /{conversation_id}/chat` |
| `_not_found` (`backend/src/api/routes/conversations.py:92`) | `DELETE /{conversation_id}`, `GET /{conversation_id}`, `POST /{conversation_id}/chat`, `POST /{conversation_id}/messages` |
| `_chat_error` (`backend/src/api/routes/conversations.py:358`) | `POST /{conversation_id}/chat` |
| `observe` (`backend/src/domain/observability.py:41`) | `GET /ping` |
