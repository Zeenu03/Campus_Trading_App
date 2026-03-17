"""
Trading Models
Campus Trading Application - Module B

Models:
- Offer: Price negotiations between buyers and sellers
- Transaction: Completed trades
- Rating: User reviews after transactions
"""

from datetime import datetime
from app import db


class Offer(db.Model):
    """
    Offer model.
    Represents a buyer's offer on a listing.
    """
    __tablename__ = 'Offer'

    OfferID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID', onupdate='CASCADE'), nullable=False)
    BuyerID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    OfferedPrice = db.Column(db.Numeric(10, 2), nullable=False)
    AgreedPrice = db.Column(db.Numeric(10, 2))
    OfferMessage = db.Column(db.String(500))
    OfferStatus = db.Column(db.String(20), nullable=False, default='Submitted')
    SubmittedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ResponseDate = db.Column(db.DateTime)
    ExpiryDate = db.Column(db.DateTime)

    # Relationships
    transactions = db.relationship('Transaction', backref='offer', lazy='dynamic')
    notifications = db.relationship('Notification', backref='related_offer', lazy='dynamic',
                                    foreign_keys='Notification.RelatedOfferID')
    message_threads = db.relationship('MessageThread', backref='offer', lazy='dynamic')

    def __repr__(self):
        return f'<Offer {self.OfferID}: ${self.OfferedPrice} on Listing {self.ListingID}>'

    def to_dict(self, include_buyer=False, include_listing=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.OfferID,
            'listing_id': self.ListingID,
            'buyer_id': self.BuyerID,
            'offered_price': float(self.OfferedPrice) if self.OfferedPrice else 0,
            'agreed_price': float(self.AgreedPrice) if self.AgreedPrice else None,
            'message': self.OfferMessage,
            'status': self.OfferStatus,
            'submitted_date': self.SubmittedDate.isoformat() if self.SubmittedDate else None,
            'response_date': self.ResponseDate.isoformat() if self.ResponseDate else None,
            'expiry_date': self.ExpiryDate.isoformat() if self.ExpiryDate else None
        }
        if include_buyer and self.buyer:
            data['buyer'] = {
                'id': self.buyer.MemberID,
                'name': self.buyer.Name,
                'image': self.buyer.Image
            }
        if include_listing and self.listing:
            data['listing'] = {
                'id': self.listing.ListingID,
                'title': self.listing.Title,
                'asking_price': float(self.listing.AskingPrice) if self.listing.AskingPrice else 0
            }
        return data

    @property
    def is_pending(self):
        """Check if offer is pending response."""
        return self.OfferStatus == 'Submitted'

    @property
    def is_accepted(self):
        """Check if offer was accepted."""
        return self.OfferStatus == 'Accepted'

    @property
    def is_expired(self):
        """Check if offer has expired."""
        if self.ExpiryDate:
            return datetime.utcnow() > self.ExpiryDate
        return False


class Transaction(db.Model):
    """
    Transaction model.
    Records completed trades between members.
    """
    __tablename__ = 'Transaction'

    TransactionID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID'), nullable=False)
    SellerID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    BuyerID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    OfferID = db.Column(db.Integer, db.ForeignKey('Offer.OfferID'))
    AgreedPrice = db.Column(db.Numeric(10, 2), nullable=False)
    TransactionDate = db.Column(db.DateTime)
    SellerConfirmed = db.Column(db.Boolean, nullable=False, default=False)
    BuyerConfirmed = db.Column(db.Boolean, nullable=False, default=False)
    Status = db.Column(db.String(20), nullable=False, default='Scheduled')
    CreatedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    ratings = db.relationship('Rating', backref='transaction', lazy='dynamic')
    notifications = db.relationship('Notification', backref='related_transaction', lazy='dynamic',
                                    foreign_keys='Notification.RelatedTransactionID')

    def __repr__(self):
        return f'<Transaction {self.TransactionID}: ${self.AgreedPrice}>'

    def to_dict(self, include_parties=False, include_listing=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.TransactionID,
            'listing_id': self.ListingID,
            'seller_id': self.SellerID,
            'buyer_id': self.BuyerID,
            'offer_id': self.OfferID,
            'agreed_price': float(self.AgreedPrice) if self.AgreedPrice else 0,
            'transaction_date': self.TransactionDate.isoformat() if self.TransactionDate else None,
            'seller_confirmed': self.SellerConfirmed,
            'buyer_confirmed': self.BuyerConfirmed,
            'status': self.Status,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None
        }
        if include_parties:
            data['seller'] = {
                'id': self.seller_member.MemberID,
                'name': self.seller_member.Name
            } if self.seller_member else None
            data['buyer'] = {
                'id': self.buyer_member.MemberID,
                'name': self.buyer_member.Name
            } if self.buyer_member else None
        if include_listing and self.listing:
            data['listing'] = {
                'id': self.listing.ListingID,
                'title': self.listing.Title
            }
        return data

    @property
    def is_completed(self):
        """Check if transaction is completed."""
        return self.Status == 'Completed'

    @property
    def is_cancelled(self):
        """Check if transaction was cancelled."""
        return self.Status == 'Cancelled'

    @property
    def is_confirmed_by_both(self):
        """Check if both parties have confirmed."""
        return self.SellerConfirmed and self.BuyerConfirmed


class Rating(db.Model):
    """
    Rating model.
    Stores user reviews after completed transactions.
    """
    __tablename__ = 'Rating'

    RatingID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TransactionID = db.Column(db.Integer, db.ForeignKey('Transaction.TransactionID', onupdate='CASCADE'),
                              nullable=False)
    RaterID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    RatedID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    Stars = db.Column(db.Integer, nullable=False)  # 1-5
    ReviewText = db.Column(db.String(1000))
    RatingDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Unique constraint - one rating per rater per transaction
    __table_args__ = (
        db.UniqueConstraint('TransactionID', 'RaterID', name='UQ_Rating_Transaction_Rater'),
    )

    def __repr__(self):
        return f'<Rating {self.RatingID}: {self.Stars} stars>'

    def to_dict(self, include_users=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.RatingID,
            'transaction_id': self.TransactionID,
            'rater_id': self.RaterID,
            'rated_id': self.RatedID,
            'stars': self.Stars,
            'review': self.ReviewText,
            'rating_date': self.RatingDate.isoformat() if self.RatingDate else None
        }
        if include_users:
            data['rater'] = {
                'id': self.rater.MemberID,
                'name': self.rater.Name
            } if self.rater else None
            data['rated'] = {
                'id': self.rated.MemberID,
                'name': self.rated.Name
            } if self.rated else None
        return data

    @property
    def is_positive(self):
        """Check if rating is positive (4-5 stars)."""
        return self.Stars >= 4

    @property
    def is_negative(self):
        """Check if rating is negative (1-2 stars)."""
        return self.Stars <= 2
