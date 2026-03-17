"""
Models Package
Campus Trading Application - Module B

This package contains all SQLAlchemy models for the database tables.
"""

# Auth models
from .user import User, Session, UserGroup, UserGroupMapping, AuditLog

# Core models
from .member import Member
from .admin import Administrator, Category

# Listing models
from .listing import Listing, ListingImage

# Trading models
from .trading import Offer, Transaction, Rating

# Communication models
from .communication import (
    MessageThread, Message, Notification,
    Report, WishRequest, Watchlist
)

__all__ = [
    # Auth
    'User',
    'Session',
    'UserGroup',
    'UserGroupMapping',
    'AuditLog',
    # Core
    'Member',
    'Administrator',
    'Category',
    # Listings
    'Listing',
    'ListingImage',
    # Trading
    'Offer',
    'Transaction',
    'Rating',
    # Communication
    'MessageThread',
    'Message',
    'Notification',
    'Report',
    'WishRequest',
    'Watchlist',
]
