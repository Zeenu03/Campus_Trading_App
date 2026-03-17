"""
Listing Models
Campus Trading Application - Module B

Models:
- Listing: Items for sale/donation
- ListingImage: Photos attached to listings
"""

from datetime import datetime
from app import db


class Listing(db.Model):
    """
    Item listing model.
    Represents products available for sale or donation.
    """
    __tablename__ = 'Listing'

    ListingID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    SellerID = db.Column(db.Integer, db.ForeignKey('Member.MemberID', onupdate='CASCADE'), nullable=False)
    CategoryID = db.Column(db.Integer, db.ForeignKey('Category.CategoryID', onupdate='CASCADE'), nullable=False)
    Title = db.Column(db.String(200), nullable=False)
    Description = db.Column(db.String(2000))
    AskingPrice = db.Column(db.Numeric(10, 2), nullable=False)
    IsNegotiable = db.Column(db.Boolean, nullable=False, default=True)
    Condition = db.Column(db.String(20))  # New, Like New, Good, Fair, Poor
    CourseCode = db.Column(db.String(20))
    Status = db.Column(db.String(20), nullable=False, default='Listed')
    CreatedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    LastModifiedDate = db.Column(db.DateTime, onupdate=datetime.utcnow)
    ExpiryDate = db.Column(db.DateTime)
    IsDonation = db.Column(db.Boolean, nullable=False, default=False)
    PreferredMeetingLocation = db.Column(db.String(200))
    WishRequestID = db.Column(db.Integer, db.ForeignKey('WishRequest.WishRequestID', ondelete='SET NULL'))

    # Relationships
    images = db.relationship('ListingImage', backref='listing', lazy='dynamic',
                             cascade='all, delete-orphan', order_by='ListingImage.ImageOrder')
    offers = db.relationship('Offer', backref='listing', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='listing', lazy='dynamic')
    watchers = db.relationship('Watchlist', backref='listing', lazy='dynamic',
                               cascade='all, delete-orphan')
    reports = db.relationship('Report', backref='reported_listing', lazy='dynamic',
                              foreign_keys='Report.ReportedListingID')
    notifications = db.relationship('Notification', backref='related_listing', lazy='dynamic',
                                    foreign_keys='Notification.RelatedListingID')
    message_threads = db.relationship('MessageThread', backref='listing', lazy='dynamic')

    def __repr__(self):
        return f'<Listing {self.ListingID}: {self.Title}>'

    def to_dict(self, include_seller=False, include_images=True):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.ListingID,
            'seller_id': self.SellerID,
            'category_id': self.CategoryID,
            'title': self.Title,
            'description': self.Description,
            'asking_price': float(self.AskingPrice) if self.AskingPrice else 0,
            'is_negotiable': self.IsNegotiable,
            'condition': self.Condition,
            'course_code': self.CourseCode,
            'status': self.Status,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None,
            'last_modified': self.LastModifiedDate.isoformat() if self.LastModifiedDate else None,
            'expiry_date': self.ExpiryDate.isoformat() if self.ExpiryDate else None,
            'is_donation': self.IsDonation,
            'meeting_location': self.PreferredMeetingLocation
        }
        if include_seller and self.seller:
            data['seller'] = {
                'id': self.seller.MemberID,
                'name': self.seller.Name,
                'image': self.seller.Image
            }
        if include_images:
            data['images'] = [img.to_dict() for img in self.images.all()]
        return data

    def to_summary_dict(self):
        """Return minimal listing info for listings."""
        first_image = self.images.first()
        return {
            'id': self.ListingID,
            'title': self.Title,
            'asking_price': float(self.AskingPrice) if self.AskingPrice else 0,
            'status': self.Status,
            'condition': self.Condition,
            'is_donation': self.IsDonation,
            'image': first_image.ImageURL if first_image else None,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None
        }

    @property
    def is_active(self):
        """Check if listing is active."""
        return self.Status == 'Listed'

    @property
    def active_offers_count(self):
        """Count pending offers."""
        return self.offers.filter_by(OfferStatus='Submitted').count()

    @property
    def watcher_count(self):
        """Count users watching this listing."""
        return self.watchers.count()


class ListingImage(db.Model):
    """
    Listing image model.
    Stores images associated with listings.
    """
    __tablename__ = 'ListingImage'

    ImageID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID', onupdate='CASCADE', ondelete='CASCADE'),
                          nullable=False)
    ImageURL = db.Column(db.String(500), nullable=False)
    ImageOrder = db.Column(db.Integer, nullable=False)
    UploadedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('ListingID', 'ImageOrder', name='UQ_ListingImage_ListingID_ImageOrder'),
    )

    def __repr__(self):
        return f'<ListingImage {self.ImageID} for Listing {self.ListingID}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.ImageID,
            'listing_id': self.ListingID,
            'url': self.ImageURL,
            'order': self.ImageOrder,
            'uploaded_date': self.UploadedDate.isoformat() if self.UploadedDate else None
        }
