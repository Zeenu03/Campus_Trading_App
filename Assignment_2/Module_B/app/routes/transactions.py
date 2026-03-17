"""
Transactions Routes
Campus Trading Application - Module B

Endpoints:
- GET  /api/transactions           - List transactions (own)
- GET  /api/transactions/<id>      - Get single transaction
- PUT  /api/transactions/<id>/confirm - Confirm by buyer/seller
- PUT  /api/transactions/<id>/cancel  - Cancel transaction
- POST /api/transactions/<id>/rate    - Rate after transaction
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from app import db
from app.models import Transaction, Rating, Listing
from app.middleware import require_auth, require_admin, get_current_user
from app.services import log_crud_operation

bp = Blueprint('transactions', __name__)


@bp.route('/transactions', methods=['GET'])
@require_auth
def get_transactions():
    """Get transactions for the current user (as buyer or seller)."""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    if user.is_admin:
        query = Transaction.query
    elif user.MemberID:
        role = request.args.get('role')
        if role == 'seller':
            query = Transaction.query.filter_by(SellerID=user.MemberID)
        elif role == 'buyer':
            query = Transaction.query.filter_by(BuyerID=user.MemberID)
        else:
            query = Transaction.query.filter(
                (Transaction.SellerID == user.MemberID) |
                (Transaction.BuyerID == user.MemberID)
            )
    else:
        return jsonify({'transactions': [], 'pagination': {}}), 200

    status = request.args.get('status')
    if status:
        query = query.filter(Transaction.Status == status)

    pagination = query.order_by(Transaction.CreatedDate.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'transactions': [t.to_dict(include_parties=True, include_listing=True) for t in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    }), 200


@bp.route('/transactions/<int:id>', methods=['GET'])
@require_auth
def get_transaction(id):
    """Get a single transaction."""
    user = get_current_user()
    transaction = Transaction.query.get_or_404(id)

    if not user.is_admin:
        if transaction.BuyerID != user.MemberID and transaction.SellerID != user.MemberID:
            return jsonify({'error': 'Forbidden', 'message': 'Not authorized'}), 403

    return jsonify({'transaction': transaction.to_dict(include_parties=True, include_listing=True)}), 200


@bp.route('/transactions/<int:id>/confirm', methods=['PUT'])
@require_auth
def confirm_transaction(id):
    """
    Confirm a transaction as buyer or seller.
    When both confirm, transaction is marked Complete and listing is marked Sold.
    """
    user = get_current_user()
    transaction = Transaction.query.get_or_404(id)

    if transaction.BuyerID != user.MemberID and transaction.SellerID != user.MemberID and not user.is_admin:
        return jsonify({'error': 'Forbidden', 'message': 'Not a party to this transaction'}), 403

    if transaction.Status not in ('Scheduled', 'InProgress'):
        return jsonify({'error': 'Bad Request', 'message': f'Cannot confirm a {transaction.Status} transaction'}), 400

    data = request.get_json() or {}
    meeting_date = data.get('transaction_date')

    if transaction.SellerID == user.MemberID or user.is_admin:
        transaction.SellerConfirmed = True

    if transaction.BuyerID == user.MemberID or user.is_admin:
        transaction.BuyerConfirmed = True

    if meeting_date:
        transaction.TransactionDate = datetime.fromisoformat(meeting_date)

    transaction.Status = 'InProgress'

    # Both confirmed — complete the transaction
    if transaction.SellerConfirmed and transaction.BuyerConfirmed:
        transaction.Status = 'Completed'
        transaction.TransactionDate = transaction.TransactionDate or datetime.utcnow()
        # Mark listing as Sold
        if transaction.listing:
            transaction.listing.Status = 'Sold'

    db.session.commit()
    log_crud_operation('UPDATE', 'Transaction', id, new_values={'status': transaction.Status})

    return jsonify({
        'message': f'Transaction {transaction.Status.lower()}',
        'transaction': transaction.to_dict(include_parties=True)
    }), 200


@bp.route('/transactions/<int:id>/cancel', methods=['PUT'])
@require_auth
def cancel_transaction(id):
    """Cancel a transaction. Both parties or admin can cancel."""
    user = get_current_user()
    transaction = Transaction.query.get_or_404(id)

    if transaction.BuyerID != user.MemberID and transaction.SellerID != user.MemberID and not user.is_admin:
        return jsonify({'error': 'Forbidden', 'message': 'Not a party to this transaction'}), 403

    if transaction.Status == 'Completed':
        return jsonify({'error': 'Bad Request', 'message': 'Cannot cancel a completed transaction'}), 400

    transaction.Status = 'Cancelled'

    # Re-list the listing
    if transaction.listing and transaction.listing.Status == 'Pending':
        transaction.listing.Status = 'Listed'
        # Re-open the offer
        if transaction.offer:
            transaction.offer.OfferStatus = 'Submitted'

    db.session.commit()
    log_crud_operation('UPDATE', 'Transaction', id, new_values={'status': 'Cancelled'})

    return jsonify({'message': 'Transaction cancelled', 'transaction': transaction.to_dict()}), 200


@bp.route('/transactions/<int:id>/rate', methods=['POST'])
@require_auth
def rate_transaction(id):
    """
    Submit a rating after a completed transaction.

    Request Body:
        {
            "stars": 5,
            "review": "Great seller!"
        }
    """
    user = get_current_user()
    transaction = Transaction.query.get_or_404(id)

    if transaction.BuyerID != user.MemberID and transaction.SellerID != user.MemberID:
        return jsonify({'error': 'Forbidden', 'message': 'Not a party to this transaction'}), 403

    if transaction.Status != 'Completed':
        return jsonify({'error': 'Bad Request', 'message': 'Can only rate completed transactions'}), 400

    # Check for existing rating
    existing = Rating.query.filter_by(
        TransactionID=id,
        RaterID=user.MemberID
    ).first()
    if existing:
        return jsonify({'error': 'Conflict', 'message': 'You have already rated this transaction'}), 409

    data = request.get_json()
    if not data or not data.get('stars'):
        return jsonify({'error': 'Bad Request', 'message': 'Stars rating is required'}), 400

    stars = int(data['stars'])
    if stars < 1 or stars > 5:
        return jsonify({'error': 'Bad Request', 'message': 'Stars must be between 1 and 5'}), 400

    # Rate the other party
    rated_id = transaction.SellerID if user.MemberID == transaction.BuyerID else transaction.BuyerID

    rating = Rating(
        TransactionID=id,
        RaterID=user.MemberID,
        RatedID=rated_id,
        Stars=stars,
        ReviewText=data.get('review')
    )
    db.session.add(rating)
    db.session.commit()

    log_crud_operation('CREATE', 'Rating', rating.RatingID, new_values=rating.to_dict())

    return jsonify({'message': 'Rating submitted', 'rating': rating.to_dict()}), 201
