"""
Portfolio Routes
Campus Trading Application - Module B

Endpoints:
- GET /api/members/<id>/portfolio - Get member's complete portfolio
"""

from flask import Blueprint, request, jsonify

from app.models import Member, Listing, Transaction, Rating
from app.middleware import require_auth

bp = Blueprint('portfolio', __name__)


@bp.route('/members/<int:id>/portfolio', methods=['GET'])
@require_auth
def get_portfolio(id):
    """
    Get a member's portfolio including listings, transactions, and ratings.

    This provides a comprehensive view of a member's trading activity.

    Returns:
        200: Portfolio data
        404: Member not found
    """
    member = Member.query.get_or_404(id)

    # Get active listings
    active_listings = Listing.query.filter_by(
        SellerID=id,
        Status='Listed'
    ).order_by(Listing.CreatedDate.desc()).limit(10).all()

    # Get recent transactions (as buyer or seller)
    recent_sales = Transaction.query.filter_by(
        SellerID=id,
        Status='Completed'
    ).order_by(Transaction.TransactionDate.desc()).limit(5).all()

    recent_purchases = Transaction.query.filter_by(
        BuyerID=id,
        Status='Completed'
    ).order_by(Transaction.TransactionDate.desc()).limit(5).all()

    # Get ratings received
    ratings_received = Rating.query.filter_by(
        RatedID=id
    ).order_by(Rating.RatingDate.desc()).limit(10).all()

    # Calculate stats
    total_sales = Transaction.query.filter_by(SellerID=id, Status='Completed').count()
    total_purchases = Transaction.query.filter_by(BuyerID=id, Status='Completed').count()
    active_listings_count = Listing.query.filter_by(SellerID=id, Status='Listed').count()

    # Calculate average rating
    all_ratings = Rating.query.filter_by(RatedID=id).all()
    avg_rating = None
    if all_ratings:
        avg_rating = round(sum(r.Stars for r in all_ratings) / len(all_ratings), 2)

    return jsonify({
        'member': {
            'id': member.MemberID,
            'name': member.Name,
            'department': member.Department,
            'year_of_study': member.YearOfStudy,
            'hostel': member.Hostel,
            'room_number': member.RoomNumber,
            'image': member.Image,
            'bio': member.Bio,
            'is_verified': member.IsVerified,
            'member_since': member.AccountCreationDate.isoformat() if member.AccountCreationDate else None
        },
        'stats': {
            'active_listings': active_listings_count,
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'total_transactions': total_sales + total_purchases,
            'average_rating': avg_rating,
            'total_ratings': len(all_ratings)
        },
        'active_listings': [
            {
                'id': l.ListingID,
                'title': l.Title,
                'asking_price': float(l.AskingPrice) if l.AskingPrice else 0,
                'condition': l.Condition,
                'created_date': l.CreatedDate.isoformat() if l.CreatedDate else None,
                'image': l.images.first().ImageURL if l.images.first() else None
            }
            for l in active_listings
        ],
        'recent_sales': [
            {
                'id': t.TransactionID,
                'listing_title': t.listing.Title if t.listing else None,
                'buyer_name': t.buyer_member.Name if t.buyer_member else None,
                'agreed_price': float(t.AgreedPrice) if t.AgreedPrice else 0,
                'transaction_date': t.TransactionDate.isoformat() if t.TransactionDate else None
            }
            for t in recent_sales
        ],
        'recent_purchases': [
            {
                'id': t.TransactionID,
                'listing_title': t.listing.Title if t.listing else None,
                'seller_name': t.seller_member.Name if t.seller_member else None,
                'agreed_price': float(t.AgreedPrice) if t.AgreedPrice else 0,
                'transaction_date': t.TransactionDate.isoformat() if t.TransactionDate else None
            }
            for t in recent_purchases
        ],
        'ratings_received': [
            {
                'id': r.RatingID,
                'stars': r.Stars,
                'review': r.ReviewText,
                'rater_name': r.rater.Name if r.rater else None,
                'rating_date': r.RatingDate.isoformat() if r.RatingDate else None
            }
            for r in ratings_received
        ]
    }), 200
