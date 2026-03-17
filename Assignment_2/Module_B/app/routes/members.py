"""
Members Routes
Campus Trading Application - Module B

Endpoints:
- GET /api/members - List all members
- GET /api/members/<id> - Get single member
- POST /api/members - Create new member
- PUT /api/members/<id> - Update member
- DELETE /api/members/<id> - Delete member (admin only)
"""

from datetime import datetime
from flask import Blueprint, request, jsonify

from app import db
from app.models import Member
from app.middleware import require_auth, require_ownership, require_admin, get_current_user
from app.services import log_crud_operation

bp = Blueprint('members', __name__)


@bp.route('/members', methods=['GET'])
@require_auth
def get_members():
    """
    Get all members with optional filtering.

    Query Parameters:
        - department: Filter by department
        - hostel: Filter by hostel
        - year: Filter by year of study
        - status: Filter by account status (default: Active)
        - search: Search by name or email
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)

    Returns:
        200: List of members with pagination
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Member.query

    # Filters
    department = request.args.get('department')
    if department:
        query = query.filter(Member.Department.ilike(f'%{department}%'))

    hostel = request.args.get('hostel')
    if hostel:
        query = query.filter(Member.Hostel.ilike(f'%{hostel}%'))

    year = request.args.get('year', type=int)
    if year:
        query = query.filter(Member.YearOfStudy == year)

    status = request.args.get('status', 'Active')
    if status:
        query = query.filter(Member.AccountStatus == status)

    search = request.args.get('search')
    if search:
        query = query.filter(
            (Member.Name.ilike(f'%{search}%')) |
            (Member.Email.ilike(f'%{search}%'))
        )

    pagination = query.order_by(Member.Name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'members': [m.to_dict() for m in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@bp.route('/members/<int:id>', methods=['GET'])
@require_auth
def get_member(id):
    """
    Get a single member by ID.

    Returns:
        200: Member details
        404: Member not found
    """
    member = Member.query.get_or_404(id)

    user = get_current_user()
    include_sensitive = (user.MemberID == id) or user.is_admin

    return jsonify({
        'member': member.to_dict(include_sensitive=include_sensitive)
    }), 200


@bp.route('/members', methods=['POST'])
@require_auth
def create_member():
    """
    Create a new member profile.

    Request Body:
        {
            "name": "John Doe",
            "email": "john@iitgn.ac.in",
            "contact_number": "0771234567",
            "department": "Computer Science",
            "year_of_study": 3,
            "hostel": "Hostel A",
            "room_number": "A-101",
            "bio": "Student looking for textbooks"
        }

    Returns:
        201: Member created
        400: Validation error
        409: Member already exists
    """
    user = get_current_user()

    if user.MemberID:
        return jsonify({
            'error': 'Conflict',
            'message': 'You already have a member profile'
        }), 409

    data = request.get_json()
    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    errors = []
    if not data.get('name'):
        errors.append('Name is required')
    if not data.get('email'):
        errors.append('Email is required')
    if not data.get('contact_number'):
        errors.append('Contact number is required')

    if errors:
        return jsonify({
            'error': 'Validation Error',
            'message': errors
        }), 400

    if Member.query.filter_by(Email=data.get('email')).first():
        return jsonify({
            'error': 'Conflict',
            'message': 'Email already registered'
        }), 409

    member = Member(
        Name=data.get('name'),
        Email=data.get('email'),
        PasswordHash=user.PasswordHash,
        ContactNumber=data.get('contact_number'),
        Department=data.get('department'),
        YearOfStudy=data.get('year_of_study'),
        Hostel=data.get('hostel'),
        RoomNumber=data.get('room_number'),
        Image=data.get('image'),
        Bio=data.get('bio')
    )

    db.session.add(member)
    db.session.flush()

    user.MemberID = member.MemberID
    db.session.commit()

    log_crud_operation('CREATE', 'Member', member.MemberID, new_values=member.to_dict())

    return jsonify({
        'message': 'Member profile created',
        'member': member.to_dict()
    }), 201


@bp.route('/members/<int:id>', methods=['PUT'])
@require_auth
@require_ownership('member')
def update_member(id):
    """
    Update a member profile. Only owner or admin can update.

    Returns:
        200: Member updated
        400: Validation error
        403: Not authorized
        404: Member not found
    """
    member = Member.query.get_or_404(id)
    old_values = member.to_dict(include_sensitive=True)

    data = request.get_json()
    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    if 'name' in data:
        member.Name = data['name']
    if 'contact_number' in data:
        member.ContactNumber = data['contact_number']
    if 'department' in data:
        member.Department = data['department']
    if 'year_of_study' in data:
        member.YearOfStudy = data['year_of_study']
    if 'hostel' in data:
        member.Hostel = data['hostel']
    if 'room_number' in data:
        member.RoomNumber = data['room_number']
    if 'image' in data:
        member.Image = data['image']
    if 'bio' in data:
        member.Bio = data['bio']

    db.session.commit()

    log_crud_operation('UPDATE', 'Member', id, old_values, member.to_dict(include_sensitive=True))

    return jsonify({
        'message': 'Member updated',
        'member': member.to_dict(include_sensitive=True)
    }), 200


@bp.route('/members/<int:id>', methods=['DELETE'])
@require_auth
@require_admin
def delete_member(id):
    """
    Delete a member (admin only). Soft-deletes by setting status.

    Returns:
        200: Member deleted
        403: Not authorized
        404: Member not found
    """
    member = Member.query.get_or_404(id)
    old_values = member.to_dict(include_sensitive=True)

    member.AccountStatus = 'Deleted'
    db.session.commit()

    log_crud_operation('DELETE', 'Member', id, old_values)

    return jsonify({'message': 'Member deleted'}), 200


@bp.route('/members/<int:id>/suspend', methods=['POST'])
@require_auth
@require_admin
def suspend_member(id):
    """Suspend a member account (admin only)."""
    member = Member.query.get_or_404(id)
    member.AccountStatus = 'Suspended'
    db.session.commit()

    log_crud_operation('UPDATE', 'Member', id, new_values={'status': 'Suspended'})

    return jsonify({'message': 'Member suspended'}), 200


@bp.route('/members/<int:id>/activate', methods=['POST'])
@require_auth
@require_admin
def activate_member(id):
    """Activate a member account (admin only)."""
    member = Member.query.get_or_404(id)
    member.AccountStatus = 'Active'
    db.session.commit()

    log_crud_operation('UPDATE', 'Member', id, new_values={'status': 'Active'})

    return jsonify({'message': 'Member activated'}), 200


@bp.route('/members/<int:id>/verify', methods=['POST'])
@require_auth
@require_admin
def verify_member(id):
    """Verify a member account (admin only)."""
    member = Member.query.get_or_404(id)
    member.IsVerified = True
    member.VerificationDate = datetime.utcnow()
    db.session.commit()

    log_crud_operation('UPDATE', 'Member', id, new_values={'is_verified': True})

    return jsonify({'message': 'Member verified'}), 200
