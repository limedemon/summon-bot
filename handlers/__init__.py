from aiogram import Router

from . import (
    admin_admins,
    admin_cards,
    admin_menu,
    admin_rarities,
    admin_summons,
    common,
    inline,
)


def get_root_router() -> Router:
    root = Router(name="root")
    # Inline handlers first (narrow update types, cheap to check).
    root.include_router(inline.router)
    # Admin sub-panels before the generic fallback in common.
    root.include_router(admin_menu.router)
    root.include_router(admin_summons.router)
    root.include_router(admin_rarities.router)
    root.include_router(admin_cards.router)
    root.include_router(admin_admins.router)
    # Common/user-facing + fallback catch-all last.
    root.include_router(common.router)
    return root
