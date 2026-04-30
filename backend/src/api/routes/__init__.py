from .admin import router as admin_router
from .assistants import router as assistants_router
from .conversations import router as conversations_router
from .documents import router as documents_router

__all__ = [
    "admin_router",
    "assistants_router",
    "conversations_router",
    "documents_router",
]
