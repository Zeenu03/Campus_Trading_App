"""
Offers Routes
Campus Trading Application - Module B

Endpoints:
- GET  /api/offers               - Get offers (filtered by user or listing)
- GET  /api/offers/<id>          - Get single offer
- POST /api/offers               - Make an offer
- PUT  /api/offers/<id>/accept   - Accept offer (seller)
- PUT  /api/offers/<id>/decline  - Decline offer (seller)
- PUT  /api/offers/<id>/withdraw - Withdraw offer (buyer)
- DELETE /api/offers/<id>        - Delete offer (admin)
"""

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from app import db
from app.models import Offer, Listing, Transaction
from app.middleware import require_auth, require_admin, get_current_user
from app.middleware.rbac import check_can_respond_to_offer, check_can_cancel_offer
from app.services import log_crud_operation

bp = Blueprint('offers', __name__)


@bp.route('/offers', methods=['GET'])
@require_auth
def get_offers():
    """
    Get offers. Regular users see only their own; admins see all.

    Query Parameters:
        - listing_id: Filter by listing
        - role: 'buyer' or 'seller' perspective
        - status: Filter by offer status
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Offer.query

    listing_id = request.args.get('listing_id', type=int)
    if listing_id:
        query = query.filter(Offer.ListingID == listing_id)

    status = request.args.get('status')
    if status:
        query = query.filter(Offer.OfferStatus == status)

    # Non-admins can only see offers where they are buyer or their listings have the offer
    if not user.is_admin and user.MemberID:
        role = request.args.get('role', 'buyer')
        if role == 'seller':
            # Offers on listings owned by this user
            my_listing_ids = [l.ListingID for l in
                              Listing.query.filter_by(SellerID=user.MemberID).all()]
            query = query.filter(Offer.ListingID.in_(my_listing_ids))
        else:
            query = query.filter(Offer.BuyerID == user.MemberID)

    pagination = query.order_by(Offer.SubmittedDate.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'offers': [o.to_dict(include_buyer=True, include_listing=True) for o in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@bp.route('/offers/<int:id>', methods=['GET'])
@require_auth
def get_offer(id):
    """Get a single offer by ID."""
    user = get_current_user()
    offer = Offer.query.get_or_404(id)

    # Only buyer, seller, or admin can view
    if not user.is_admin:
        if offer.BuyerID != user.MemberID:
            if not (offer.listing and offer.listing.SellerID == user.MemberID):
                return jsonify({'error': 'Forbidden', 'message': 'Not authorized'}), 403

    return jsonify({'offer': offer.to_dict(include_buyer=True, include_listing=True)}), 200


@bp.route('/offers', methods=['POST'])
@require_auth
def create_offer():
    """
    Make an offer on a listing.

    Request Body:
        {
            "listing_id": 1,
            "offered_price": 450.00,
            "message": "Can you do 450?",
            "expiry_days": 3
        }
    """
    user = get_current_user()

    if not user.MemberID:
        return jsonify({'error': 'Forbidden', 'message': 'Member profile required'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Request body required'}), 400

    errors = []
    if not data.get('listing_id'):
        errors.append('Listing ID is required')
    if data.get('offered_price') is None:
        errors.append('Offered price is required')
    if errors:
        return jsonify({'error': 'Validation Error', 'message': errors}), 400

    listing = Listing.query.get(data['listing_id'])
    if not listing:
        return jsonify({'error': 'Not Found', 'message': 'Listing not found'}), 404

    if listing.Status != 'Listed':
        return jsonify({'error': 'Bad Request', 'message': 'Listing is not active'}), 400

    if listing.SellerID == user.MemberID:
        return jsonify({'error': 'Bad Request', 'message': 'Cannot make an offer on your own listing'}), 400

    expiry_days = data.get('expiry_days', 3)
    expiry_date = datetime.utcnow() + timedelta(days=expiry_days)

    offer = Offer(
        ListingID=data['listing_id'],
        BuyerID=user.MemberID,
        OfferedPrice=data['offered_price'],
        OfferMessage=data.get('message'),
        OfferStatus='Submitted',
        ExpiryDate=expiry_date
    )
    db.session.add(offer)
    db.session.commit()

    log_crud_operation('CREATE', 'Offer', offer.OfferID, new_values=offer.to_dict())

    return jsonify({'message': 'Offer submitted', 'offer': offer.to_dict()}), 201


@bp.route('/offers/<int:id>/accept', methods=['PUT'])
@require_auth
def accept_offer(id):
    """Accept an offer (seller only). Creates a Transaction."""
    user = get_current_user()
    offer = Offer.query.get_or_404(id)

    if not check_can_respond_to_offer(user, offer):
        return jsonify({'error': 'Forbidden', 'message': 'Only the seller can accept offers'}), 403

    if offer.OfferStatus != 'Submitted':
        return jsonify({'error': 'Bad Request', 'message': f'Cannot accept an offer with status {offer.OfferStatus}'}), 400

    data = request.get_json() or {}
    agreed_price = data.get('agreed_price', offer.OfferedPrice)

    offer.OfferStatus = 'Accepted'
    offer.AgreedPrice = agreed_price
    offer.ResponseDate = datetime.utcnow()

    # Decline all other pending offers on the same listing
    other_offers = Offer.query.filter(
        Offer.ListingID == offer.ListingID,
        Offer.OfferID != offer.OfferID,
        Offer.OfferStatus == 'Submitted'
    ).all()
    for o in other_offers:
        o.OfferStatus = 'Declined'
        o.ResponseDate = datetime.utcnow()

    # Mark listing as Pending
    offer.listing.Status = 'Pending'

    # Create Transaction
    transaction = Transaction(
        ListingID=offer.ListingID,
        SellerID=offer.listing.SellerID,
        BuyerID=offer.BuyerID,
        OfferID=offer.OfferID,
        AgreedPrice=agreed_price,
        Status='Scheduled'
    )
    db.session.add(transaction)
    db.session.commit()

    log_crud_operation('UPDATE', 'Offer', id, new_values={'status': 'Accepted'})
    log_crud_operation('CREATE', 'Transaction', transaction.TransactionID, new_values=transaction.to_dict())

    return jsonify({
        'message': 'Offer accepted',
        'offer': offer.to_dict(),
        'transaction': transaction.to_dict()
    }), 200


@bp.route('/offers/<int:id>/decline', methods=['PUT'])
@require_auth
def decline_offer(id):
    """Decline an offer (seller only)."""
    user = get_current_user()
    offer = Offer.query.get_or_404(id)

    if not check_can_respond_to_offer(user, offer):
        return jsonify({'error': 'Forbidden', 'message': 'Only the seller can decline offers'}), 403

    if offer.OfferStatus != 'Submitted':
        return jsonify({'error': 'Bad Request', 'message': f'Cannot decline an offer with status {offer.OfferStatus}'}), 400

    offer.OfferStatus = 'Declined'
    offer.ResponseDate = datetime.utcnow()
    db.session.commit()

    log_crud_operation('UPDATE', 'Offer', id, new_values={'status': 'Declined'})

    return jsonify({'message': 'Offer declined', 'offer': offer.to_dict()}), 200


@bp.route('/offers/<int:id>/withdraw', methods=['PUT'])
@require_auth
def withdraw_offer(id):
    """Withdraw an offer (buyer only)."""
    user = get_current_user()
    offer = Offer.query.get_or_404(id)

    if not check_can_cancel_offer(user, offer):
        return jsonify({'error': 'Forbidden', 'message': 'Only the buyer can withdraw their offer'}), 403

    if offer.OfferStatus != 'Submitted':
        return jsonify({'error': 'Bad Request', 'message': f'Cannot withdraw an offer with status {offer.OfferStatus}'}), 400

    offer.OfferStatus = 'Withdrawn'
    offer.ResponseDate = datetime.utcnow()
    db.session.commit()

    log_crud_operation('UPDATE', 'Offer', id, new_values={'status': 'Withdrawn'})

    return jsonify({'message': 'Offer withdrawn', 'offer': offer.to_dict()}), 200


@bp.route('/offers/<int:id>', methods=['DELETE'])
@require_auth
@require_admin
def delete_offer(id):
    """Delete an offer (admin only)."""
    offer = Offer.query.get_or_404(id)
    old_values = offer.to_dict()
    db.session.delete(offer)
    db.session.commit()
    log_crud_operation('DELETE', 'Offer', id, old_values)
    return jsonify({'message': 'Offer deleted'}), 200
