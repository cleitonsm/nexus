from .admin import router as admin_router
from .assistants import router as assistants_router
from .conversations import router as conversations_router
from .documents import router as documents_router
from .index import router as index_router

__all__ = [
    "admin_router",
    "assistants_router",
    "conversations_router",
    "documents_router",
    "index_router",
]
