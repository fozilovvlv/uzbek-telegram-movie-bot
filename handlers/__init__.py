from aiogram import Router
from .user import user_router
from .admin import admin_router

def get_handlers_router() -> Router:
    router = Router()
    # Tartib muhim: avval admin buyruqlari tekshiriladi
    router.include_router(admin_router)
    router.include_router(user_router)
    return router
