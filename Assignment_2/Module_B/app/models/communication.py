"""
Communication Models
Campus Trading Application - Module B

Models:
- MessageThread: Conversation threads between buyers and sellers
- Message: Individual messages within threads
- Notification: User alerts and notifications
- Report: User/listing reports for admin review
- WishRequest: Items users are looking for
- Watchlist: Listings users are watching
"""

from datetime import datetime
from app import db


class MessageThread(db.Model):
    """
    Message thread model.
    Represents a conversation between buyer and seller about a listing.
    """
    __tablename__ = 'MessageThread'

    ThreadID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID'), nullable=False)
    BuyerID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    OfferID = db.Column(db.Integer, db.ForeignKey('Offer.OfferID'), nullable=False)
    CreatedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    IsActive = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    messages = db.relationship('Message', backref='thread', lazy='dynamic',
                               cascade='all, delete-orphan', order_by='Message.SentDate')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('ListingID', 'BuyerID', name='UQ_MessageThread_Listing_Buyer'),
    )

    def __repr__(self):
        return f'<MessageThread {self.ThreadID}>'

    def to_dict(self, include_messages=False, include_participants=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.ThreadID,
            'listing_id': self.ListingID,
            'buyer_id': self.BuyerID,
            'offer_id': self.OfferID,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None,
            'is_active': self.IsActive,
            'message_count': self.messages.count()
        }
        if include_messages:
            data['messages'] = [msg.to_dict() for msg in self.messages.all()]
        if include_participants:
            data['buyer'] = {
                'id': self.buyer.MemberID,
                'name': self.buyer.Name
            } if self.buyer else None
            data['listing'] = {
                'id': self.listing.ListingID,
                'title': self.listing.Title,
                'seller_id': self.listing.SellerID,
                'seller_name': self.listing.seller.Name if self.listing.seller else None
            } if self.listing else None
        return data

    @property
    def last_message(self):
        """Get the most recent message."""
        return self.messages.order_by(Message.SentDate.desc()).first()


class Message(db.Model):
    """
    Message model.
    Individual messages within a thread.
    """
    __tablename__ = 'Message'

    MessageID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ThreadID = db.Column(db.Integer, db.ForeignKey('MessageThread.ThreadID', onupdate='CASCADE', ondelete='CASCADE'),
                         nullable=False)
    SenderID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    MessageText = db.Column(db.String(2000), nullable=False)
    SentDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message {self.MessageID}>'

    def to_dict(self, include_sender=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.MessageID,
            'thread_id': self.ThreadID,
            'sender_id': self.SenderID,
            'message': self.MessageText,
            'sent_date': self.SentDate.isoformat() if self.SentDate else None
        }
        if include_sender and self.sender:
            data['sender'] = {
                'id': self.sender.MemberID,
                'name': self.sender.Name,
                'image': self.sender.Image
            }
        return data


class Notification(db.Model):
    """
    Notification model.
    User alerts for various platform activities.
    """
    __tablename__ = 'Notification'

    NotificationID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    RecipientID = db.Column(db.Integer, db.ForeignKey('Member.MemberID', onupdate='CASCADE', ondelete='CASCADE'),
                            nullable=False)
    NotificationType = db.Column(db.String(50), nullable=False)
    Title = db.Column(db.String(200))
    Message = db.Column(db.String(1000), nullable=False)
    RelatedListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID'))
    RelatedOfferID = db.Column(db.Integer, db.ForeignKey('Offer.OfferID'))
    RelatedTransactionID = db.Column(db.Integer, db.ForeignKey('Transaction.TransactionID'))
    IsRead = db.Column(db.Boolean, nullable=False, default=False)
    CreatedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ReadDate = db.Column(db.DateTime)

    # Valid notification types
    NOTIFICATION_TYPES = [
        'OfferReceived', 'OfferAccepted', 'OfferDeclined', 'OfferWithdrawn', 'OfferExpired',
        'PriceDropped', 'StatusChanged', 'MeetingReminder', 'TransactionCompleted',
        'RatingReceived', 'WishRequestMatched', 'ListingExpiring', 'General'
    ]

    def __repr__(self):
        return f'<Notification {self.NotificationID}: {self.NotificationType}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.NotificationID,
            'recipient_id': self.RecipientID,
            'type': self.NotificationType,
            'title': self.Title,
            'message': self.Message,
            'related_listing_id': self.RelatedListingID,
            'related_offer_id': self.RelatedOfferID,
            'related_transaction_id': self.RelatedTransactionID,
            'is_read': self.IsRead,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None,
            'read_date': self.ReadDate.isoformat() if self.ReadDate else None
        }

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.IsRead:
            self.IsRead = True
            self.ReadDate = datetime.utcnow()


class Report(db.Model):
    """
    Report model.
    User reports against members or listings for admin review.
    """
    __tablename__ = 'Report'

    ReportID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ReporterID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'), nullable=False)
    ReportedMemberID = db.Column(db.Integer, db.ForeignKey('Member.MemberID'))
    ReportedListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID'))
    ReportType = db.Column(db.String(50), nullable=False)
    Description = db.Column(db.String(2000), nullable=False)
    Status = db.Column(db.String(20), nullable=False, default='Submitted')
    SubmittedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ResolvedDate = db.Column(db.DateTime)
    ResolvedByAdminID = db.Column(db.Integer, db.ForeignKey('Administrator.AdminID', onupdate='CASCADE',
                                                            ondelete='SET NULL'))
    Resolution = db.Column(db.String(1000))

    # Relationship for reported member
    reported_member = db.relationship('Member', foreign_keys=[ReportedMemberID],
                                      backref='reports_against')

    # Valid report types
    REPORT_TYPES = [
        'Misleading Description', 'Scam', 'No-Show', 'Inappropriate Content',
        'Price Manipulation', 'Fake Offers', 'Other'
    ]

    def __repr__(self):
        return f'<Report {self.ReportID}: {self.ReportType}>'

    def to_dict(self, include_details=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.ReportID,
            'reporter_id': self.ReporterID,
            'reported_member_id': self.ReportedMemberID,
            'reported_listing_id': self.ReportedListingID,
            'type': self.ReportType,
            'status': self.Status,
            'submitted_date': self.SubmittedDate.isoformat() if self.SubmittedDate else None
        }
        if include_details:
            data['description'] = self.Description
            data['resolved_date'] = self.ResolvedDate.isoformat() if self.ResolvedDate else None
            data['resolved_by'] = self.ResolvedByAdminID
            data['resolution'] = self.Resolution
        return data

    @property
    def is_pending(self):
        """Check if report is pending review."""
        return self.Status in ['Submitted', 'UnderReview']

    @property
    def is_resolved(self):
        """Check if report is resolved."""
        return self.Status == 'Resolved'


class WishRequest(db.Model):
    """
    Wish request model.
    Items that users are looking for.
    """
    __tablename__ = 'WishRequest'

    WishRequestID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    RequesterID = db.Column(db.Integer, db.ForeignKey('Member.MemberID', onupdate='CASCADE'), nullable=False)
    ItemDescription = db.Column(db.String(500), nullable=False)
    MinBudget = db.Column(db.Numeric(10, 2))
    MaxBudget = db.Column(db.Numeric(10, 2))
    PreferredCondition = db.Column(db.String(20))
    NeededByDate = db.Column(db.Date)
    AdditionalDetails = db.Column(db.String(1000))
    Status = db.Column(db.String(20), nullable=False, default='Active')
    CreatedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    FulfilledDate = db.Column(db.DateTime)

    # Relationships
    matching_listings = db.relationship('Listing', backref='wish_request', lazy='dynamic')

    def __repr__(self):
        return f'<WishRequest {self.WishRequestID}: {self.ItemDescription[:50]}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.WishRequestID,
            'requester_id': self.RequesterID,
            'description': self.ItemDescription,
            'min_budget': float(self.MinBudget) if self.MinBudget else None,
            'max_budget': float(self.MaxBudget) if self.MaxBudget else None,
            'preferred_condition': self.PreferredCondition,
            'needed_by': self.NeededByDate.isoformat() if self.NeededByDate else None,
            'additional_details': self.AdditionalDetails,
            'status': self.Status,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None,
            'fulfilled_date': self.FulfilledDate.isoformat() if self.FulfilledDate else None
        }

    @property
    def is_active(self):
        """Check if wish request is active."""
        return self.Status == 'Active'

    @property
    def budget_range(self):
        """Get budget range as string."""
        if self.MinBudget and self.MaxBudget:
            return f"${self.MinBudget} - ${self.MaxBudget}"
        elif self.MaxBudget:
            return f"Up to ${self.MaxBudget}"
        elif self.MinBudget:
            return f"From ${self.MinBudget}"
        return "No budget specified"


class Watchlist(db.Model):
    """
    Watchlist model.
    Listings that users are watching for updates.
    """
    __tablename__ = 'Watchlist'

    WatchlistID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    MemberID = db.Column(db.Integer, db.ForeignKey('Member.MemberID', ondelete='CASCADE'), nullable=False)
    ListingID = db.Column(db.Integer, db.ForeignKey('Listing.ListingID', ondelete='CASCADE'), nullable=False)
    AddedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    NotifyOnPriceChange = db.Column(db.Boolean, nullable=False, default=True)
    NotifyOnStatusChange = db.Column(db.Boolean, nullable=False, default=True)

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('MemberID', 'ListingID', name='UQ_Watchlist_Member_Listing'),
    )

    def __repr__(self):
        return f'<Watchlist Member:{self.MemberID} -> Listing:{self.ListingID}>'

    def to_dict(self, include_listing=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.WatchlistID,
            'member_id': self.MemberID,
            'listing_id': self.ListingID,
            'added_date': self.AddedDate.isoformat() if self.AddedDate else None,
            'notify_price_change': self.NotifyOnPriceChange,
            'notify_status_change': self.NotifyOnStatusChange
        }
        if include_listing and self.listing:
            data['listing'] = self.listing.to_summary_dict()
        return data
