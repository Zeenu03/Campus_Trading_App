"""
Admin Routes
Campus Trading Application - Module B

Admin-only endpoints for platform management.
All routes require @require_auth + @require_admin.

Endpoints:
- GET  /api/admin/users           - List all users
- GET  /api/admin/users/<id>      - Get user details
- PUT  /api/admin/users/<id>      - Update user (role, status)
- DELETE /api/admin/users/<id>    - Deactivate user
- GET  /api/admin/reports         - List all reports
- PUT  /api/admin/reports/<id>    - Resolve/update report
- GET  /api/admin/audit-logs      - View audit logs
- GET  /api/admin/stats           - Platform statistics
- POST /api/admin/users/<id>/toggle-active  - Toggle user active
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Member, Listing, Transaction, Offer, Report, AuditLog
from app.middleware import require_auth, require_admin, get_current_user
from app.services import log_crud_operation, get_audit_logs, get_unauthorized_access_attempts

bp = Blueprint('admin', __name__)


@bp.route('/users', methods=['GET'])
@require_auth
@require_admin
def get_users():
    """List all users with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = User.query

    role = request.args.get('role')
    if role:
        query = query.filter(User.Role == role)

    is_active = request.args.get('is_active')
    if is_active is not None:
        query = query.filter(User.IsActive == (is_active.lower() == 'true'))

    search = request.args.get('search')
    if search:
        query = query.filter(
            (User.Username.ilike(f'%{search}%')) |
            (User.Email.ilike(f'%{search}%'))
        )

    pagination = query.order_by(User.CreatedAt.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'users': [u.to_dict(include_sensitive=True) for u in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@bp.route('/users/<int:id>', methods=['GET'])
@require_auth
@require_admin
def get_user(id):
    """Get a single user's details."""
    user = User.query.get_or_404(id)
    return jsonify({'user': user.to_dict(include_sensitive=True)}), 200


@bp.route('/users/<int:id>', methods=['PUT'])
@require_auth
@require_admin
def update_user(id):
    """Update a user (role, active status, etc.)."""
    target_user = User.query.get_or_404(id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Request body required'}), 400

    old_values = target_user.to_dict(include_sensitive=True)

    if 'role' in data:
        if data['role'] not in ('Admin', 'RegularUser'):
            return jsonify({'error': 'Bad Request', 'message': 'Invalid role'}), 400
        target_user.Role = data['role']
    if 'is_active' in data:
        target_user.IsActive = bool(data['is_active'])

    db.session.commit()
    log_crud_operation('UPDATE', 'User', id, old_values, target_user.to_dict(include_sensitive=True))

    return jsonify({'message': 'User updated', 'user': target_user.to_dict(include_sensitive=True)}), 200


@bp.route('/users/<int:id>', methods=['DELETE'])
@require_auth
@require_admin
def deactivate_user(id):
    """Deactivate (soft-delete) a user account."""
    target_user = User.query.get_or_404(id)
    current_admin = get_current_user()

    if target_user.UserID == current_admin.UserID:
        return jsonify({'error': 'Bad Request', 'message': 'Cannot deactivate your own account'}), 400

    old_values = target_user.to_dict()
    target_user.IsActive = False
    db.session.commit()

    log_crud_operation('DELETE', 'User', id, old_values, {'is_active': False})
    return jsonify({'message': 'User deactivated'}), 200


@bp.route('/users/<int:id>/toggle-active', methods=['POST'])
@require_auth
@require_admin
def toggle_user_active(id):
    """Toggle user active/inactive status."""
    target_user = User.query.get_or_404(id)
    target_user.IsActive = not target_user.IsActive
    db.session.commit()
    status = 'activated' if target_user.IsActive else 'deactivated'
    return jsonify({'message': f'User {status}', 'is_active': target_user.IsActive}), 200


@bp.route('/reports', methods=['GET'])
@require_auth
@require_admin
def get_reports():
    """Get all user/listing reports."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Report.query

    status = request.args.get('status')
    if status:
        query = query.filter(Report.Status == status)

    pagination = query.order_by(Report.SubmittedDate.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'reports': [r.to_dict(include_details=True) for r in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@bp.route('/reports/<int:id>', methods=['PUT'])
@require_auth
@require_admin
def update_report(id):
    """Update/resolve a report."""
    report = Report.query.get_or_404(id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Request body required'}), 400

    if 'status' in data:
        report.Status = data['status']
    if 'resolution' in data:
        report.Resolution = data['resolution']
    if data.get('status') == 'Resolved':
        report.ResolvedDate = datetime.utcnow()
        admin = get_current_user()
        report.ResolvedByAdminID = admin.AdminID

    db.session.commit()
    log_crud_operation('UPDATE', 'Report', id, new_values={'status': report.Status})

    return jsonify({'message': 'Report updated', 'report': report.to_dict(include_details=True)}), 200


@bp.route('/audit-logs', methods=['GET'])
@require_auth
@require_admin
def get_audit_log_entries():
    """View audit logs with filtering."""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action')
    table_name = request.args.get('table')
    unauthorized_only = request.args.get('unauthorized_only', 'false').lower() == 'true'

    is_authorized = False if unauthorized_only else None

    logs = get_audit_logs(
        user_id=user_id,
        action=action,
        table_name=table_name,
        is_authorized=is_authorized,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'audit_logs': [log.to_dict() for log in logs],
        'count': len(logs)
    }), 200


@bp.route('/audit-logs/unauthorized', methods=['GET'])
@require_auth
@require_admin
def get_unauthorized_attempts():
    """Get recent unauthorized access attempts."""
    limit = request.args.get('limit', 50, type=int)
    logs = get_unauthorized_access_attempts(limit=limit)
    return jsonify({'unauthorized_attempts': [log.to_dict() for log in logs]}), 200


@bp.route('/stats', methods=['GET'])
@require_auth
@require_admin
def get_stats():
    """Get platform-wide statistics."""
    stats = {
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(IsActive=True).count(),
            'admins': User.query.filter_by(Role='Admin').count(),
        },
        'members': {
            'total': Member.query.count(),
            'active': Member.query.filter_by(AccountStatus='Active').count(),
            'suspended': Member.query.filter_by(AccountStatus='Suspended').count(),
        },
        'listings': {
            'total': Listing.query.count(),
            'active': Listing.query.filter_by(Status='Listed').count(),
            'sold': Listing.query.filter_by(Status='Sold').count(),
            'pending': Listing.query.filter_by(Status='Pending').count(),
        },
        'transactions': {
            'total': Transaction.query.count(),
            'completed': Transaction.query.filter_by(Status='Completed').count(),
            'scheduled': Transaction.query.filter_by(Status='Scheduled').count(),
            'cancelled': Transaction.query.filter_by(Status='Cancelled').count(),
        },
        'offers': {
            'total': Offer.query.count(),
            'pending': Offer.query.filter_by(OfferStatus='Submitted').count(),
            'accepted': Offer.query.filter_by(OfferStatus='Accepted').count(),
        },
        'reports': {
            'total': Report.query.count(),
            'pending': Report.query.filter_by(Status='Submitted').count(),
            'resolved': Report.query.filter_by(Status='Resolved').count(),
        },
        'security': {
            'unauthorized_attempts': AuditLog.query.filter_by(IsAuthorized=False).count(),
        }
    }

    return jsonify({'stats': stats}), 200
