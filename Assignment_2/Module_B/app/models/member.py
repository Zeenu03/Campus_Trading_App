"""
Member Model
Campus Trading Application - Module B

Represents campus members who can buy and sell items.
"""

from datetime import datetime
from app import db


class Member(db.Model):
    """
    Campus Trading member model.
    Stores user profile information for trading platform users.
    """
    __tablename__ = 'Member'

    MemberID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Name = db.Column(db.String(100), nullable=False)
    Email = db.Column(db.String(150), unique=True, nullable=False)
    PasswordHash = db.Column(db.String(256), nullable=False)
    ContactNumber = db.Column(db.String(20), nullable=False)
    Department = db.Column(db.String(100))
    YearOfStudy = db.Column(db.Integer)
    Hostel = db.Column(db.String(100))
    RoomNumber = db.Column(db.String(20))
    Image = db.Column(db.String(500))
    Bio = db.Column(db.String(500))
    IsVerified = db.Column(db.Boolean, default=False)
    VerificationDate = db.Column(db.DateTime)
    AccountCreationDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    AccountStatus = db.Column(db.String(20), nullable=False, default='Active')

    # Relationships
    listings = db.relationship('Listing', backref='seller', lazy='dynamic',
                               foreign_keys='Listing.SellerID')
    offers_made = db.relationship('Offer', backref='buyer', lazy='dynamic',
                                  foreign_keys='Offer.BuyerID')
    sales = db.relationship('Transaction', backref='seller_member', lazy='dynamic',
                            foreign_keys='Transaction.SellerID')
    purchases = db.relationship('Transaction', backref='buyer_member', lazy='dynamic',
                                foreign_keys='Transaction.BuyerID')
    ratings_given = db.relationship('Rating', backref='rater', lazy='dynamic',
                                    foreign_keys='Rating.RaterID')
    ratings_received = db.relationship('Rating', backref='rated', lazy='dynamic',
                                       foreign_keys='Rating.RatedID')
    wish_requests = db.relationship('WishRequest', backref='requester', lazy='dynamic')
    watchlist_items = db.relationship('Watchlist', backref='member', lazy='dynamic',
                                      cascade='all, delete-orphan')
    reports_submitted = db.relationship('Report', backref='reporter', lazy='dynamic',
                                        foreign_keys='Report.ReporterID')
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic',
                                    cascade='all, delete-orphan')
    message_threads = db.relationship('MessageThread', backref='buyer', lazy='dynamic',
                                      foreign_keys='MessageThread.BuyerID')
    messages_sent = db.relationship('Message', backref='sender', lazy='dynamic')

    def __repr__(self):
        return f'<Member {self.MemberID}: {self.Name}>'

    def to_dict(self, include_sensitive=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.MemberID,
            'name': self.Name,
            'email': self.Email,
            'department': self.Department,
            'year_of_study': self.YearOfStudy,
            'hostel': self.Hostel,
            'room_number': self.RoomNumber,
            'image': self.Image,
            'bio': self.Bio,
            'is_verified': self.IsVerified,
            'account_status': self.AccountStatus,
            'created_at': self.AccountCreationDate.isoformat() if self.AccountCreationDate else None
        }
        if include_sensitive:
            data['contact_number'] = self.ContactNumber
            data['verification_date'] = self.VerificationDate.isoformat() if self.VerificationDate else None
        return data

    def to_portfolio_dict(self):
        """Return portfolio view with stats."""
        return {
            'member': self.to_dict(),
            'stats': {
                'active_listings': self.listings.filter_by(Status='Listed').count(),
                'total_sales': self.sales.filter_by(Status='Completed').count(),
                'total_purchases': self.purchases.filter_by(Status='Completed').count(),
                'average_rating': self.average_rating,
                'total_ratings': self.ratings_received.count()
            }
        }

    @property
    def average_rating(self):
        """Calculate average rating received."""
        ratings = self.ratings_received.all()
        if not ratings:
            return None
        return sum(r.Stars for r in ratings) / len(ratings)

    @property
    def is_active(self):
        """Check if account is active."""
        return self.AccountStatus == 'Active'
