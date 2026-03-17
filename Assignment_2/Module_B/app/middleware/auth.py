"""
Authentication Middleware — @require_auth decorator

Accepts JWT from (in order of priority):
  1. Authorization: Bearer <token>  header  ← used by all AJAX calls (main.js)
  2. access_token                   cookie  ← fallback
"""

from functools import wraps
from typing import Callable

from flask import request, jsonify, g, current_app

from app.services.auth_service import AuthService
from app.models import User, AuditLog


def require_auth(f: Callable) -> Callable:
    @wraps(f)
    def decorated(*args, **kwargs):

        # ── 1. Extract token ─────────────────────────────────────────
        token = None

        auth_header = request.headers.get('Authorization', '')
        if auth_header.lower().startswith('bearer '):
            parts = auth_header.split(None, 1)
            if len(parts) == 2:
                token = parts[1].strip()

        if not token:
            token = request.cookies.get('access_token')

        if not token:
            _log_unauth('No token provided')
            return jsonify({'error': 'Unauthorized', 'message': 'No session found. Please log in.'}), 401

        # ── 2. Verify JWT signature / expiry ─────────────────────────
        payload = AuthService.verify_token(token)
        if not payload:
            _log_unauth('Invalid or expired token')
            return jsonify({'error': 'Unauthorized', 'message': 'Session expired. Please log in again.'}), 401

        # ── 3. Confirm session not revoked ───────────────────────────
        if not AuthService.is_session_valid(token):
            _log_unauth('Session revoked or not in DB')
            return jsonify({'error': 'Unauthorized', 'message': 'Session revoked. Please log in again.'}), 401

        # ── 4. Load user ─────────────────────────────────────────────
        user_id = payload.get('sub')
        user = User.query.get(user_id)
        if not user:
            _log_unauth(f'User {user_id} not found')
            return jsonify({'error': 'Unauthorized', 'message': 'User not found.'}), 401

        if not user.IsActive:
            _log_unauth('Account deactivated', user_id=user.UserID)
            return jsonify({'error': 'Unauthorized', 'message': 'Account deactivated.'}), 401

        # ── 5. Attach to request context ─────────────────────────────
        g.current_user  = user
        g.current_token = token
        g.token_payload = payload

        return f(*args, **kwargs)

    return decorated


# ── Accessors ────────────────────────────────────────────────────────

def get_current_user() -> User:
    return getattr(g, 'current_user', None)

def get_current_user_id():
    u = get_current_user()
    return u.UserID if u else None

def get_current_member_id():
    u = get_current_user()
    return u.MemberID if u else None

def is_admin() -> bool:
    u = get_current_user()
    return u.is_admin if u else False

def extract_token_from_request():
    hdr = request.headers.get('Authorization', '')
    if hdr.lower().startswith('bearer '):
        parts = hdr.split(None, 1)
        if len(parts) == 2:
            return parts[1].strip()
    return request.cookies.get('access_token')


# ── Internal ─────────────────────────────────────────────────────────

def _log_unauth(reason: str, user_id=None):
    try:
        AuditLog.log(
            action='UNAUTHORIZED_ACCESS',
            user_id=user_id,
            request=request,
            is_authorized=False,
            error_message=reason
        )
    except Exception:
        pass
