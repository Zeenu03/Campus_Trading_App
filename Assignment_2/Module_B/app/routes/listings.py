"""
Listings Routes
Campus Trading Application - Module B

Endpoints:
- GET  /api/listings          - List/search listings
- GET  /api/listings/<id>     - Get single listing
- POST /api/listings          - Create listing
- PUT  /api/listings/<id>     - Update listing (owner/admin)
- DELETE /api/listings/<id>   - Delete listing (admin only)
"""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Listing, ListingImage, Category
from app.middleware import require_auth, require_admin, get_current_user
from app.middleware.rbac import check_can_modify_listing
from app.services import log_crud_operation

bp = Blueprint('listings', __name__)


@bp.route('/listings', methods=['GET'])
@require_auth
def get_listings():
    """Get all listings with optional filtering and pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Listing.query

    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter(Listing.CategoryID == category_id)

    seller_id = request.args.get('seller_id', type=int)
    if seller_id:
        query = query.filter(Listing.SellerID == seller_id)

    status = request.args.get('status', 'Listed')
    if status and status != 'all':
        query = query.filter(Listing.Status == status)

    condition = request.args.get('condition')
    if condition:
        query = query.filter(Listing.Condition == condition)

    min_price = request.args.get('min_price', type=float)
    if min_price is not None:
        query = query.filter(Listing.AskingPrice >= min_price)

    max_price = request.args.get('max_price', type=float)
    if max_price is not None:
        query = query.filter(Listing.AskingPrice <= max_price)

    is_donation = request.args.get('is_donation')
    if is_donation is not None:
        query = query.filter(Listing.IsDonation == (is_donation.lower() == 'true'))

    search = request.args.get('search')
    if search:
        query = query.filter(
            (Listing.Title.ilike(f'%{search}%')) |
            (Listing.Description.ilike(f'%{search}%'))
        )

    pagination = query.order_by(Listing.CreatedDate.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'listings': [l.to_dict(include_seller=True, include_images=True) for l in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@bp.route('/listings/<int:id>', methods=['GET'])
@require_auth
def get_listing(id):
    """Get a single listing by ID."""
    listing = Listing.query.get_or_404(id)
    return jsonify({'listing': listing.to_dict(include_seller=True, include_images=True)}), 200


@bp.route('/listings', methods=['POST'])
@require_auth
def create_listing():
    """Create a new listing."""
    user = get_current_user()

    if not user.MemberID:
        return jsonify({'error': 'Forbidden', 'message': 'Member profile required to create listings'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Request body required'}), 400

    errors = []
    if not data.get('title'):
        errors.append('Title is required')
    if data.get('asking_price') is None:
        errors.append('Asking price is required')
    if not data.get('category_id'):
        errors.append('Category is required')
    if errors:
        return jsonify({'error': 'Validation Error', 'message': errors}), 400

    if not Category.query.get(data.get('category_id')):
        return jsonify({'error': 'Bad Request', 'message': 'Invalid category'}), 400

    listing = Listing(
        SellerID=user.MemberID,
        CategoryID=data['category_id'],
        Title=data['title'],
        Description=data.get('description'),
        AskingPrice=data['asking_price'],
        IsNegotiable=data.get('is_negotiable', True),
        Condition=data.get('condition'),
        CourseCode=data.get('course_code'),
        IsDonation=data.get('is_donation', False),
        PreferredMeetingLocation=data.get('preferred_meeting_location'),
        Status='Listed'
    )
    db.session.add(listing)
    db.session.flush()

    for idx, img in enumerate(data.get('images', [])):
        db.session.add(ListingImage(
            ListingID=listing.ListingID,
            ImageURL=img.get('url', ''),
            ImageOrder=img.get('order', idx + 1)
        ))

    db.session.commit()
    log_crud_operation('CREATE', 'Listing', listing.ListingID, new_values=listing.to_dict())

    return jsonify({'message': 'Listing created', 'listing': listing.to_dict(include_images=True)}), 201


@bp.route('/listings/<int:id>', methods=['PUT'])
@require_auth
def update_listing(id):
    """Update a listing (owner or admin)."""
    user = get_current_user()
    listing = Listing.query.get_or_404(id)

    if not check_can_modify_listing(user, listing):
        return jsonify({'error': 'Forbidden', 'message': 'Only the seller or admin can update this listing'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Request body required'}), 400

    old_values = listing.to_dict()

    updatable = ['title', 'description', 'asking_price', 'is_negotiable',
                 'condition', 'course_code', 'is_donation', 'preferred_meeting_location', 'category_id']
    field_map = {
        'title': 'Title', 'description': 'Description', 'asking_price': 'AskingPrice',
        'is_negotiable': 'IsNegotiable', 'condition': 'Condition', 'course_code': 'CourseCode',
        'is_donation': 'IsDonation', 'preferred_meeting_location': 'PreferredMeetingLocation',
        'category_id': 'CategoryID'
    }
    for key, attr in field_map.items():
        if key in data:
            setattr(listing, attr, data[key])

    if 'status' in data and user.is_admin:
        listing.Status = data['status']

    db.session.commit()
    log_crud_operation('UPDATE', 'Listing', id, old_values, listing.to_dict())

    return jsonify({'message': 'Listing updated', 'listing': listing.to_dict(include_images=True)}), 200


@bp.route('/listings/<int:id>', methods=['DELETE'])
@require_auth
@require_admin
def delete_listing(id):
    """Delete (soft-delete) a listing — admin only."""
    listing = Listing.query.get_or_404(id)
    old_values = listing.to_dict()
    listing.Status = 'Deleted'
    db.session.commit()
    log_crud_operation('DELETE', 'Listing', id, old_values)
    return jsonify({'message': 'Listing deleted'}), 200


@bp.route('/listings/<int:id>/close', methods=['POST'])
@require_auth
def close_listing(id):
    """Close a listing (seller or admin)."""
    user = get_current_user()
    listing = Listing.query.get_or_404(id)
    if not check_can_modify_listing(user, listing):
        return jsonify({'error': 'Forbidden', 'message': 'Not authorized'}), 403
    listing.Status = 'Closed'
    db.session.commit()
    log_crud_operation('UPDATE', 'Listing', id, new_values={'status': 'Closed'})
    return jsonify({'message': 'Listing closed'}), 200


@bp.route('/listings/<int:id>/relist', methods=['POST'])
@require_auth
def relist_listing(id):
    """Re-list a closed listing (seller or admin)."""
    user = get_current_user()
    listing = Listing.query.get_or_404(id)
    if not check_can_modify_listing(user, listing):
        return jsonify({'error': 'Forbidden', 'message': 'Not authorized'}), 403
    listing.Status = 'Listed'
    db.session.commit()
    log_crud_operation('UPDATE', 'Listing', id, new_values={'status': 'Listed'})
    return jsonify({'message': 'Listing re-listed'}), 200


@bp.route('/categories', methods=['GET'])
@require_auth
def get_categories():
    """Get all active root categories with children."""
    categories = Category.query.filter_by(IsActive=True, ParentCategoryID=None).all()
    return jsonify({'categories': [c.to_dict(include_children=True) for c in categories]}), 200
