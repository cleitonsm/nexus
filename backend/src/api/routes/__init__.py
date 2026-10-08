from .admin import router as admin_router
from .assistants import router as assistants_router
from .conversations import router as conversations_router
from .documents import document_router as document_access_router
from .documents import router as documents_router
from .feedback import router as feedback_router
from .index import router as index_router
from .me import router as me_router

__all__ = [
    "admin_router",
    "assistants_router",
    "conversations_router",
    "document_access_router",
    "documents_router",
    "feedback_router",
    "index_router",
    "me_router",
]
