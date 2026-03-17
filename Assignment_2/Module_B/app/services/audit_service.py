"""
Audit Logging Service
Campus Trading Application - Module B

Provides comprehensive logging for:
- API requests/responses
- Database operations (CRUD)
- Security events (login, access denied)
- Direct database modification detection

Logs to both:
- File: logs/audit.log
- Database: AuditLog table
"""

import os
import json
import logging
import time
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
from typing import Callable, Any, Dict, Optional

from flask import request, g, current_app

from app import db
from app.models import AuditLog


# Configure file logger
_audit_logger = None


def _get_audit_logger() -> logging.Logger:
    """Get or create the audit file logger."""
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = logging.getLogger('audit')
        _audit_logger.setLevel(logging.INFO)

        # Ensure logs directory exists
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # File handler with rotation
        file_handler = RotatingFileHandler(
            'logs/audit.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        _audit_logger.addHandler(file_handler)

    return _audit_logger


def audit_log(
    action: str,
    table_name: str = None,
    record_id: int = None,
    user_id: int = None,
    username: str = None,
    old_values: Dict = None,
    new_values: Dict = None,
    is_authorized: bool = True,
    error_message: str = None,
    response_status: int = None,
    response_time: int = None
) -> None:
    """
    Log an action to both file and database.

    Args:
        action: Action type (CREATE, READ, UPDATE, DELETE, LOGIN, etc.)
        table_name: Name of the affected database table
        record_id: ID of the affected record
        user_id: ID of the user performing the action
        username: Username of the user
        old_values: Previous values (for updates)
        new_values: New values (for creates/updates)
        is_authorized: Whether the action was authorized
        error_message: Error message if action failed
        response_status: HTTP response status code
        response_time: Response time in milliseconds
    """
    # Get request context if available
    ip_address = None
    user_agent = None
    endpoint = None
    method = None

    try:
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')[:512]
        endpoint = request.path
        method = request.method
    except RuntimeError:
        # Outside request context
        pass

    # Log to file
    logger = _get_audit_logger()
    log_level = logging.INFO if is_authorized else logging.WARNING

    log_parts = []
    if user_id:
        log_parts.append(f'user_id={user_id}')
    if username:
        log_parts.append(f'user={username}')
    log_parts.append(f'action={action}')
    if table_name:
        log_parts.append(f'table={table_name}')
    if record_id:
        log_parts.append(f'record_id={record_id}')
    if endpoint:
        log_parts.append(f'endpoint={method} {endpoint}')
    if response_status:
        log_parts.append(f'status={response_status}')
    if response_time:
        log_parts.append(f'time={response_time}ms')
    if not is_authorized:
        log_parts.append('UNAUTHORIZED')
    if error_message:
        log_parts.append(f'error="{error_message}"')

    log_message = ' | '.join(log_parts)
    logger.log(log_level, log_message)

    # Log to database
    try:
        log_entry = AuditLog(
            UserID=user_id,
            Username=username,
            Action=action,
            TableName=table_name,
            RecordID=record_id,
            OldValues=old_values,
            NewValues=new_values,
            IPAddress=ip_address,
            UserAgent=user_agent,
            APIEndpoint=endpoint,
            HTTPMethod=method,
            ResponseStatus=response_status,
            ResponseTime=response_time,
            IsAuthorized=is_authorized,
            ErrorMessage=error_message
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        # Log the error but don't break the flow
        logger.error(f'Failed to write audit log to database: {e}')


def log_api_request(f: Callable) -> Callable:
    """
    Decorator to automatically log API requests and responses.

    Usage:
        @app.route('/api/listings', methods=['POST'])
        @require_auth
        @log_api_request
        def create_listing():
            pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        start_time = time.time()

        # Get user info if available
        user_id = None
        username = None
        try:
            user = getattr(g, 'current_user', None)
            if user:
                user_id = user.UserID
                username = user.Username
        except RuntimeError:
            pass

        # Execute the route
        try:
            response = f(*args, **kwargs)
            response_time = int((time.time() - start_time) * 1000)

            # Get status code
            if isinstance(response, tuple):
                status_code = response[1] if len(response) > 1 else 200
            else:
                status_code = getattr(response, 'status_code', 200)

            # Determine action from method
            action = _method_to_action(request.method)

            # Log successful request
            audit_log(
                action=action,
                user_id=user_id,
                username=username,
                response_status=status_code,
                response_time=response_time,
                is_authorized=True
            )

            return response

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)

            # Log failed request
            audit_log(
                action=_method_to_action(request.method),
                user_id=user_id,
                username=username,
                response_status=500,
                response_time=response_time,
                is_authorized=True,
                error_message=str(e)
            )
            raise

    return decorated


def log_crud_operation(
    action: str,
    table_name: str,
    record_id: int = None,
    old_values: Dict = None,
    new_values: Dict = None
) -> None:
    """
    Log a CRUD database operation.

    Args:
        action: CREATE, READ, UPDATE, DELETE
        table_name: Name of the table
        record_id: ID of the affected record
        old_values: Previous values (for UPDATE, DELETE)
        new_values: New values (for CREATE, UPDATE)
    """
    user_id = None
    username = None

    try:
        user = getattr(g, 'current_user', None)
        if user:
            user_id = user.UserID
            username = user.Username
    except RuntimeError:
        pass

    audit_log(
        action=action,
        table_name=table_name,
        record_id=record_id,
        user_id=user_id,
        username=username,
        old_values=old_values,
        new_values=new_values
    )


def log_security_event(
    event_type: str,
    user_id: int = None,
    username: str = None,
    details: str = None,
    is_authorized: bool = False
) -> None:
    """
    Log a security-related event.

    Args:
        event_type: Type of event (LOGIN_FAILED, ACCESS_DENIED, etc.)
        user_id: User ID if known
        username: Username if known
        details: Additional details
        is_authorized: Whether this was an authorized action
    """
    logger = _get_audit_logger()

    if is_authorized:
        logger.info(f'SECURITY | {event_type} | user_id={user_id} | user={username} | {details}')
    else:
        logger.warning(f'SECURITY | {event_type} | user_id={user_id} | user={username} | {details}')

    audit_log(
        action=event_type,
        user_id=user_id,
        username=username,
        is_authorized=is_authorized,
        error_message=details
    )


def log_direct_db_modification(
    table_name: str,
    record_id: int,
    old_values: Dict,
    new_values: Dict
) -> None:
    """
    Log a detected direct database modification (not through API).

    This is called by database triggers or application detection logic.

    Args:
        table_name: Name of the modified table
        record_id: ID of the modified record
        old_values: Previous values
        new_values: New values
    """
    logger = _get_audit_logger()
    logger.warning(
        f'DIRECT_DB_MODIFICATION | table={table_name} | record_id={record_id} | '
        f'old={json.dumps(old_values)} | new={json.dumps(new_values)}'
    )

    audit_log(
        action='DIRECT_MODIFICATION',
        table_name=table_name,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
        is_authorized=False,
        error_message='Direct database modification detected (bypassed API)'
    )


def get_audit_logs(
    user_id: int = None,
    action: str = None,
    table_name: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    is_authorized: bool = None,
    limit: int = 100,
    offset: int = 0
) -> list:
    """
    Query audit logs with filters.

    Args:
        user_id: Filter by user ID
        action: Filter by action type
        table_name: Filter by table name
        start_date: Filter by start date
        end_date: Filter by end date
        is_authorized: Filter by authorization status
        limit: Maximum records to return
        offset: Number of records to skip

    Returns:
        List of AuditLog objects
    """
    query = AuditLog.query

    if user_id is not None:
        query = query.filter(AuditLog.UserID == user_id)
    if action:
        query = query.filter(AuditLog.Action == action)
    if table_name:
        query = query.filter(AuditLog.TableName == table_name)
    if start_date:
        query = query.filter(AuditLog.Timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.Timestamp <= end_date)
    if is_authorized is not None:
        query = query.filter(AuditLog.IsAuthorized == is_authorized)

    return query.order_by(AuditLog.Timestamp.desc()).offset(offset).limit(limit).all()


def get_unauthorized_access_attempts(limit: int = 50) -> list:
    """
    Get recent unauthorized access attempts.

    Args:
        limit: Maximum records to return

    Returns:
        List of AuditLog objects
    """
    return AuditLog.query.filter(
        AuditLog.IsAuthorized == False
    ).order_by(AuditLog.Timestamp.desc()).limit(limit).all()


def _method_to_action(method: str) -> str:
    """Convert HTTP method to action name."""
    mapping = {
        'GET': 'READ',
        'POST': 'CREATE',
        'PUT': 'UPDATE',
        'PATCH': 'UPDATE',
        'DELETE': 'DELETE'
    }
    return mapping.get(method.upper(), method.upper())


def cleanup_old_audit_logs(days: int = 90) -> int:
    """
    Clean up audit logs older than specified days.

    Args:
        days: Number of days to keep

    Returns:
        Number of records deleted
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    count = AuditLog.query.filter(AuditLog.Timestamp < cutoff).delete()
    db.session.commit()

    logger = _get_audit_logger()
    logger.info(f'CLEANUP | Deleted {count} audit logs older than {days} days')

    return count
