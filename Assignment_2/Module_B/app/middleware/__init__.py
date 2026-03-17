"""
Middleware Package
Campus Trading Application - Module B

This package contains middleware for authentication, RBAC, and logging.
"""

# Authentication middleware
from .auth import (
    require_auth,
    get_current_user,
    get_current_user_id,
    get_current_member_id,
    is_admin,
    extract_token_from_request
)

# RBAC middleware
from .rbac import (
    require_role,
    require_admin,
    require_ownership,
    require_ownership_or_role,
    check_can_modify_listing,
    check_can_respond_to_offer,
    check_can_cancel_offer
)

__all__ = [
    # Auth
    'require_auth',
    'get_current_user',
    'get_current_user_id',
    'get_current_member_id',
    'is_admin',
    'extract_token_from_request',
    # RBAC
    'require_role',
    'require_admin',
    'require_ownership',
    'require_ownership_or_role',
    'check_can_modify_listing',
    'check_can_respond_to_offer',
    'check_can_cancel_offer',
]
