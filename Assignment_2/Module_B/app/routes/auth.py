"""
Authentication Routes
Campus Trading Application - Module B

Endpoints:
- POST /api/login - Authenticate user and get JWT token
- POST /api/logout - Revoke current session
- GET /api/isAuth - Check if current session is valid
- POST /api/register - Create new user account
"""

from flask import Blueprint, request, jsonify, g, make_response

from app.services.auth_service import AuthService
from app.middleware.auth import require_auth, get_current_user
from app.models import User, AuditLog
from app import db

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT token.

    Request Body:
        {
            "user": "username or email",
            "password": "password"
        }

    Returns:
        200: Login successful with token
        400: Missing credentials
        401: Invalid credentials
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    username_or_email = data.get('user') or data.get('username') or data.get('email')
    password = data.get('password')

    if not username_or_email or not password:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Username/email and password are required'
        }), 400

    # Authenticate user
    user = AuthService.authenticate_user(username_or_email, password)

    if not user:
        # Log failed login attempt
        AuditLog.log(
            action='LOGIN_FAILED',
            table_name='User',
            request=request,
            is_authorized=False,
            error_message=f'Failed login attempt for: {username_or_email}'
        )
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid credentials'
        }), 401

    # Generate JWT token
    token, jti, expires_at = AuthService.generate_token(user)

    # Create session record
    session = AuthService.create_session(
        user=user,
        token=token,
        jti=jti,
        expires_at=expires_at,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )

    # Log successful login
    AuditLog.log(
        action='LOGIN',
        table_name='User',
        record_id=user.UserID,
        user_id=user.UserID,
        username=user.Username,
        request=request,
        response_status=200
    )

    # Prepare response
    response_data = {
        'message': 'Login successful',
        'session_token': token,
        'user': {
            'id': user.UserID,
            'username': user.Username,
            'email': user.Email,
            'role': user.Role,
            'member_id': user.MemberID,
            'admin_id': user.AdminID
        },
        'expires_at': expires_at.isoformat()
    }

    # Create response with cookie for web UI
    response = make_response(jsonify(response_data))
    response.set_cookie(
        'access_token',
        token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite='Lax',
        max_age=int((expires_at - session.IssuedAt).total_seconds())
    )

    return response, 200


@bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    Revoke current session.

    Headers:
        Authorization: Bearer <token>

    Returns:
        200: Logout successful
        401: Not authenticated
    """
    user = get_current_user()
    token = g.current_token

    # Revoke session
    AuthService.revoke_session(token)

    # Log logout
    AuditLog.log(
        action='LOGOUT',
        table_name='Session',
        user_id=user.UserID,
        username=user.Username,
        request=request,
        response_status=200
    )

    # Clear cookie
    response = make_response(jsonify({
        'message': 'Logout successful'
    }))
    response.delete_cookie('access_token')

    return response, 200


@bp.route('/isAuth', methods=['GET'])
@require_auth
def is_auth():
    """
    Check if current session is valid.

    Headers:
        Authorization: Bearer <token>

    Returns:
        200: User is authenticated
        401: Not authenticated
    """
    user = get_current_user()
    payload = g.token_payload

    return jsonify({
        'message': 'User is authenticated',
        'user': {
            'id': user.UserID,
            'username': user.Username,
            'email': user.Email,
            'role': user.Role,
            'member_id': user.MemberID
        },
        'expires_at': payload.get('exp')
    }), 200


@bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user account.

    Request Body:
        {
            "username": "johndoe",
            "email": "john@iitgn.ac.in",
            "password": "securepassword",
            "confirm_password": "securepassword"
        }

    Returns:
        201: User created successfully
        400: Validation error
        409: Username or email already exists
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    # Validate required fields
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    errors = []
    if not username:
        errors.append('Username is required')
    if not email:
        errors.append('Email is required')
    if not password:
        errors.append('Password is required')
    if password and confirm_password and password != confirm_password:
        errors.append('Passwords do not match')
    if password and len(password) < 8:
        errors.append('Password must be at least 8 characters')

    if errors:
        return jsonify({
            'error': 'Validation Error',
            'message': errors
        }), 400

    # Check if username exists
    if User.query.filter_by(Username=username).first():
        return jsonify({
            'error': 'Conflict',
            'message': 'Username already exists'
        }), 409

    # Check if email exists
    if User.query.filter_by(Email=email).first():
        return jsonify({
            'error': 'Conflict',
            'message': 'Email already exists'
        }), 409

    # Create user
    password_hash = AuthService.hash_password(password)
    user = User(
        Username=username,
        Email=email,
        PasswordHash=password_hash,
        Role='RegularUser'
    )

    db.session.add(user)
    db.session.commit()

    # Log registration
    AuditLog.log(
        action='REGISTER',
        table_name='User',
        record_id=user.UserID,
        user_id=user.UserID,
        username=user.Username,
        request=request,
        response_status=201,
        new_values={'username': username, 'email': email}
    )

    return jsonify({
        'message': 'User registered successfully',
        'user': {
            'id': user.UserID,
            'username': user.Username,
            'email': user.Email,
            'role': user.Role
        }
    }), 201


@bp.route('/refresh', methods=['POST'])
@require_auth
def refresh_token():
    """
    Refresh the current JWT token.

    This revokes the old token and creates a new one.

    Returns:
        200: New token generated
        401: Not authenticated
    """
    user = get_current_user()
    old_token = g.current_token

    # Revoke old session
    AuthService.revoke_session(old_token)

    # Generate new token
    token, jti, expires_at = AuthService.generate_token(user)

    # Create new session
    AuthService.create_session(
        user=user,
        token=token,
        jti=jti,
        expires_at=expires_at,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )

    # Log token refresh
    AuditLog.log(
        action='TOKEN_REFRESH',
        table_name='Session',
        user_id=user.UserID,
        username=user.Username,
        request=request,
        response_status=200
    )

    response = make_response(jsonify({
        'message': 'Token refreshed',
        'session_token': token,
        'expires_at': expires_at.isoformat()
    }))

    response.set_cookie(
        'access_token',
        token,
        httponly=True,
        secure=False,
        samesite='Lax',
        max_age=86400
    )

    return response, 200


@bp.route('/me', methods=['GET'])
@require_auth
def get_current_user_info():
    """
    Get current authenticated user's information.

    Returns:
        200: User information
        401: Not authenticated
    """
    user = get_current_user()

    return jsonify({
        'user': user.to_dict(include_sensitive=True)
    }), 200


@bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    """
    Change the current user's password.

    Request Body:
        {
            "current_password": "oldpassword",
            "new_password": "newpassword",
            "confirm_password": "newpassword"
        }

    Returns:
        200: Password changed
        400: Validation error
        401: Current password incorrect
    """
    user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    # Validate
    if not current_password:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Current password is required'
        }), 400

    if not new_password:
        return jsonify({
            'error': 'Bad Request',
            'message': 'New password is required'
        }), 400

    if new_password != confirm_password:
        return jsonify({
            'error': 'Bad Request',
            'message': 'New passwords do not match'
        }), 400

    if len(new_password) < 8:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Password must be at least 8 characters'
        }), 400

    # Verify current password
    if not AuthService.verify_password(current_password, user.PasswordHash):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Current password is incorrect'
        }), 401

    # Update password
    user.PasswordHash = AuthService.hash_password(new_password)
    db.session.commit()

    # Revoke all other sessions (optional security measure)
    AuthService.revoke_all_user_sessions(user.UserID)

    # Log password change
    AuditLog.log(
        action='PASSWORD_CHANGE',
        table_name='User',
        record_id=user.UserID,
        user_id=user.UserID,
        username=user.Username,
        request=request,
        response_status=200
    )

    return jsonify({
        'message': 'Password changed successfully. Please login again.'
    }), 200
