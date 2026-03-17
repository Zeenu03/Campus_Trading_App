"""
Administrator and Category Models
Campus Trading Application - Module B

Models:
- Administrator: Platform administrators/moderators
- Category: Product categories with hierarchy support
"""

from datetime import datetime
from app import db


class Administrator(db.Model):
    """
    Platform administrator model.
    Manages moderators, support staff, and super admins.
    """
    __tablename__ = 'Administrator'

    AdminID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Name = db.Column(db.String(100), nullable=False)
    Email = db.Column(db.String(150), unique=True, nullable=False)
    PasswordHash = db.Column(db.String(256), nullable=False)
    Role = db.Column(db.String(20), nullable=False)  # SuperAdmin, Moderator, Support
    CreatedDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    LastLoginDate = db.Column(db.DateTime)
    IsActive = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    resolved_reports = db.relationship('Report', backref='resolved_by_admin', lazy='dynamic',
                                       foreign_keys='Report.ResolvedByAdminID')

    def __repr__(self):
        return f'<Administrator {self.AdminID}: {self.Name} ({self.Role})>'

    def to_dict(self, include_sensitive=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.AdminID,
            'name': self.Name,
            'email': self.Email,
            'role': self.Role,
            'is_active': self.IsActive,
            'created_date': self.CreatedDate.isoformat() if self.CreatedDate else None
        }
        if include_sensitive:
            data['last_login'] = self.LastLoginDate.isoformat() if self.LastLoginDate else None
        return data

    @property
    def is_super_admin(self):
        """Check if administrator is a super admin."""
        return self.Role == 'SuperAdmin'

    @property
    def is_moderator(self):
        """Check if administrator is a moderator."""
        return self.Role == 'Moderator'

    @property
    def is_support(self):
        """Check if administrator is support staff."""
        return self.Role == 'Support'


class Category(db.Model):
    """
    Product category model with hierarchical support.
    Categories can have parent categories for nested organization.
    """
    __tablename__ = 'Category'

    CategoryID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CategoryName = db.Column(db.String(100), nullable=False)
    ParentCategoryID = db.Column(db.Integer, db.ForeignKey('Category.CategoryID'))
    Description = db.Column(db.String(500))
    IsActive = db.Column(db.Boolean, nullable=False, default=True)

    # Self-referential relationship for hierarchy
    parent = db.relationship('Category', remote_side=[CategoryID], backref='subcategories')

    # Relationship to listings
    listings = db.relationship('Listing', backref='category', lazy='dynamic')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('CategoryName', 'ParentCategoryID', name='UQ_Category_Name_Parent'),
    )

    def __repr__(self):
        return f'<Category {self.CategoryID}: {self.CategoryName}>'

    def to_dict(self, include_children=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.CategoryID,
            'name': self.CategoryName,
            'parent_id': self.ParentCategoryID,
            'description': self.Description,
            'is_active': self.IsActive
        }
        if include_children:
            data['subcategories'] = [sub.to_dict() for sub in self.subcategories if sub.IsActive]
        return data

    def get_all_subcategories(self):
        """Get all subcategories recursively."""
        result = []
        for sub in self.subcategories:
            if sub.IsActive:
                result.append(sub)
                result.extend(sub.get_all_subcategories())
        return result

    @property
    def full_path(self):
        """Get full category path (e.g., 'Electronics > Computers > Laptops')."""
        if self.parent:
            return f"{self.parent.full_path} > {self.CategoryName}"
        return self.CategoryName

    @property
    def listing_count(self):
        """Count active listings in this category."""
        return self.listings.filter_by(Status='Listed').count()
