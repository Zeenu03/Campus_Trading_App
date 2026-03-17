"""
Services Package
Campus Trading Application - Module B

This package contains business logic services.
"""

from .auth_service import AuthService
from .audit_service import (
    audit_log,
    log_api_request,
    log_crud_operation,
    log_security_event,
    log_direct_db_modification,
    get_audit_logs,
    get_unauthorized_access_attempts,
    cleanup_old_audit_logs
)

__all__ = [
    # Auth
    'AuthService',
    # Audit
    'audit_log',
    'log_api_request',
    'log_crud_operation',
    'log_security_event',
    'log_direct_db_modification',
    'get_audit_logs',
    'get_unauthorized_access_attempts',
    'cleanup_old_audit_logs',
]
