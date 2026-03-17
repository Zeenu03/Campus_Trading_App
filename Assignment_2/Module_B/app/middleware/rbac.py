"""
Role-Based Access Control (RBAC) Middleware
Campus Trading Application - Module B

Provides decorators for role and ownership-based access control:
- @require_role: Require specific role(s)
- @require_ownership: Require resource ownership or admin
- @require_admin: Shortcut for admin-only routes
"""

from functools import wraps
from typing import Callable, List, Union

from flask import request, jsonify, g

from app.middleware.auth import get_current_user
from app.models import AuditLog, Listing, Offer, Member, Transaction, Report


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator to require specific role(s) for a route.

    Args:
        *allowed_roles: Role names that are allowed (e.g., 'Admin', 'RegularUser')

    Usage:
        @app.route('/admin/users')
        @require_auth
        @require_role('Admin')
        def admin_users():
            return jsonify({'users': []})

        @app.route('/moderate')
        @require_auth
        @require_role('Admin', 'Moderator')
        def moderate():
            return jsonify({'message': 'OK'})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()

            if not user:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Authentication required'
                }), 401

            if user.Role not in allowed_roles:
                # Log unauthorized access attempt
                _log_access_denied(
                    user=user,
                    reason=f'Role {user.Role} not in allowed roles: {allowed_roles}'
                )
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'Insufficient permissions'
                }), 403

            return f(*args, **kwargs)

        return decorated
    return decorator


def require_admin(f: Callable) -> Callable:
    """
    Shortcut decorator to require Admin role.

    Usage:
        @app.route('/admin/dashboard')
        @require_auth
        @require_admin
        def admin_dashboard():
            return jsonify({'stats': {}})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()

        if not user:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication required'
            }), 401

        if not user.is_admin:
            _log_access_denied(
                user=user,
                reason='Admin access required'
            )
            return jsonify({
                'error': 'Forbidden',
                'message': 'Admin access required'
            }), 403

        return f(*args, **kwargs)

    return decorated


def require_ownership(resource_type: str, id_param: str = 'id') -> Callable:
    """
    Decorator to require resource ownership or admin role.

    Checks if the current user owns the specified resource or is an admin.

    Args:
        resource_type: Type of resource ('listing', 'offer', 'member', 'transaction', 'report')
        id_param: Name of the URL parameter containing the resource ID

    Usage:
        @app.route('/api/listings/<int:id>', methods=['PUT'])
        @require_auth
        @require_ownership('listing')
        def update_listing(id):
            # Only listing owner or admin can reach here
            pass

        @app.route('/api/members/<int:member_id>/profile', methods=['PUT'])
        @require_auth
        @require_ownership('member', id_param='member_id')
        def update_profile(member_id):
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()

            if not user:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Authentication required'
                }), 401

            # Admins can access anything
            if user.is_admin:
                return f(*args, **kwargs)

            # Get resource ID from URL parameters
            resource_id = kwargs.get(id_param)
            if resource_id is None:
                return jsonify({
                    'error': 'Bad Request',
                    'message': f'Resource ID parameter "{id_param}" not found'
                }), 400

            # Check ownership based on resource type
            is_owner = _check_ownership(user, resource_type, resource_id)

            if not is_owner:
                _log_access_denied(
                    user=user,
                    reason=f'Not owner of {resource_type} {resource_id}'
                )
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'You do not have permission to access this resource'
                }), 403

            return f(*args, **kwargs)

        return decorated
    return decorator


def require_ownership_or_role(resource_type: str, allowed_roles: List[str],
                               id_param: str = 'id') -> Callable:
    """
    Decorator to require resource ownership OR specific role(s).

    Args:
        resource_type: Type of resource
        allowed_roles: List of roles that can access without ownership
        id_param: URL parameter name for resource ID

    Usage:
        @app.route('/api/listings/<int:id>', methods=['DELETE'])
        @require_auth
        @require_ownership_or_role('listing', ['Admin', 'Moderator'])
        def delete_listing(id):
            # Owner, Admin, or Moderator can delete
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()

            if not user:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Authentication required'
                }), 401

            # Check if user has an allowed role
            if user.Role in allowed_roles:
                return f(*args, **kwargs)

            # Otherwise, check ownership
            resource_id = kwargs.get(id_param)
            if resource_id is None:
                return jsonify({
                    'error': 'Bad Request',
                    'message': f'Resource ID parameter "{id_param}" not found'
                }), 400

            is_owner = _check_ownership(user, resource_type, resource_id)

            if not is_owner:
                _log_access_denied(
                    user=user,
                    reason=f'Not owner of {resource_type} {resource_id} and role {user.Role} not allowed'
                )
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'You do not have permission to access this resource'
                }), 403

            return f(*args, **kwargs)

        return decorated
    return decorator


def _check_ownership(user, resource_type: str, resource_id: int) -> bool:
    """
    Check if user owns a specific resource.

    Args:
        user: Current User object
        resource_type: Type of resource
        resource_id: ID of the resource

    Returns:
        True if user owns the resource, False otherwise
    """
    if resource_type == 'listing':
        listing = Listing.query.get(resource_id)
        if listing and listing.SellerID == user.MemberID:
            return True

    elif resource_type == 'offer':
        offer = Offer.query.get(resource_id)
        if offer:
            # Buyer owns the offer
            if offer.BuyerID == user.MemberID:
                return True
            # Seller owns the listing the offer is on
            if offer.listing and offer.listing.SellerID == user.MemberID:
                return True

    elif resource_type == 'member':
        # User owns their own member profile
        if resource_id == user.MemberID:
            return True

    elif resource_type == 'transaction':
        transaction = Transaction.query.get(resource_id)
        if transaction:
            # Both buyer and seller can access transaction
            if transaction.BuyerID == user.MemberID or transaction.SellerID == user.MemberID:
                return True

    elif resource_type == 'report':
        report = Report.query.get(resource_id)
        if report and report.ReporterID == user.MemberID:
            return True

    elif resource_type == 'user':
        # User owns their own User record
        if resource_id == user.UserID:
            return True

    return False


def _log_access_denied(user, reason: str):
    """
    Log an access denied event.

    Args:
        user: User who was denied
        reason: Reason for denial
    """
    try:
        AuditLog.log(
            action='ACCESS_DENIED',
            user_id=user.UserID if user else None,
            username=user.Username if user else None,
            request=request,
            is_authorized=False,
            error_message=reason
        )
    except Exception:
        # Don't let logging errors break the RBAC flow
        pass


def check_can_modify_listing(user, listing) -> bool:
    """
    Check if user can modify a listing.

    Args:
        user: Current user
        listing: Listing object

    Returns:
        True if user can modify, False otherwise
    """
    if user.is_admin:
        return True
    if listing.SellerID == user.MemberID:
        return True
    return False


def check_can_respond_to_offer(user, offer) -> bool:
    """
    Check if user can respond to an offer.

    Only the listing seller can accept/decline offers.

    Args:
        user: Current user
        offer: Offer object

    Returns:
        True if user can respond, False otherwise
    """
    if user.is_admin:
        return True
    if offer.listing and offer.listing.SellerID == user.MemberID:
        return True
    return False


def check_can_cancel_offer(user, offer) -> bool:
    """
    Check if user can cancel/withdraw an offer.

    Only the buyer who made the offer can withdraw it.

    Args:
        user: Current user
        offer: Offer object

    Returns:
        True if user can cancel, False otherwise
    """
    if user.is_admin:
        return True
    if offer.BuyerID == user.MemberID:
        return True
    return False
