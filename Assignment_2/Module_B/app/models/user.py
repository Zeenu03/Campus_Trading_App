"""
User and Authentication Models
Campus Trading Application - Module B

Models:
- User: Core authentication
- Session: JWT token tracking
- UserGroup: Role groups
- UserGroupMapping: User-group assignments
- AuditLog: Security logging
"""

from datetime import datetime
from app import db


class User(db.Model):
    """
    Core authentication table.
    Stores user credentials and links to Member/Administrator profiles.
    """
    __tablename__ = 'User'

    UserID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Username = db.Column(db.String(50), unique=True, nullable=False)
    Email = db.Column(db.String(150), unique=True, nullable=False)
    PasswordHash = db.Column(db.String(256), nullable=False)
    Role = db.Column(db.Enum('Admin', 'RegularUser'), nullable=False, default='RegularUser')
    IsActive = db.Column(db.Boolean, nullable=False, default=True)
    CreatedAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    UpdatedAt = db.Column(db.DateTime, onupdate=datetime.utcnow)
    LastLoginAt = db.Column(db.DateTime)

    # Foreign keys to Member and Administrator
    MemberID = db.Column(db.Integer, db.ForeignKey('Member.MemberID', ondelete='SET NULL'))
    AdminID = db.Column(db.Integer, db.ForeignKey('Administrator.AdminID', ondelete='SET NULL'))

    # Relationships
    sessions = db.relationship(
        'Session',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # UserGroupMapping has TWO foreign keys pointing to User:
    #   UserID    → the member of the group
    #   AssignedBy → who granted the role (can be NULL)
    # We must tell SQLAlchemy which FK represents the "parent" side of this relationship.
    group_mappings = db.relationship(
        'UserGroupMapping',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='[UserGroupMapping.UserID]'
    )

    def __repr__(self):
        return f'<User {self.Username}>'

    def to_dict(self, include_sensitive=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.UserID,
            'username': self.Username,
            'email': self.Email,
            'role': self.Role,
            'is_active': self.IsActive,
            'created_at': self.CreatedAt.isoformat() if self.CreatedAt else None,
            'member_id': self.MemberID,
            'admin_id': self.AdminID
        }
        if include_sensitive:
            data['last_login'] = self.LastLoginAt.isoformat() if self.LastLoginAt else None
        return data

    @property
    def is_admin(self):
        """Check if user has admin role."""
        return self.Role == 'Admin'


class Session(db.Model):
    """
    JWT token tracking table.
    Allows token revocation and session management.
    """
    __tablename__ = 'Session'

    SessionID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    UserID = db.Column(db.Integer, db.ForeignKey('User.UserID', ondelete='CASCADE'), nullable=False)
    Token = db.Column(db.String(512), nullable=False)
    TokenJTI = db.Column(db.String(64), unique=True, nullable=False)  # JWT ID
    IssuedAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ExpiresAt = db.Column(db.DateTime, nullable=False)
    IsRevoked = db.Column(db.Boolean, nullable=False, default=False)
    RevokedAt = db.Column(db.DateTime)
    IPAddress = db.Column(db.String(45))
    UserAgent = db.Column(db.String(512))

    def __repr__(self):
        return f'<Session {self.SessionID} for User {self.UserID}>'

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'session_id': self.SessionID,
            'user_id': self.UserID,
            'issued_at': self.IssuedAt.isoformat() if self.IssuedAt else None,
            'expires_at': self.ExpiresAt.isoformat() if self.ExpiresAt else None,
            'is_revoked': self.IsRevoked,
            'ip_address': self.IPAddress
        }

    @property
    def is_expired(self):
        """Check if session is expired."""
        return datetime.utcnow() > self.ExpiresAt

    @property
    def is_valid(self):
        """Check if session is valid (not expired and not revoked)."""
        return not self.is_expired and not self.IsRevoked


class UserGroup(db.Model):
    """
    User groups for RBAC.
    Stores role definitions and permissions.
    """
    __tablename__ = 'UserGroup'

    GroupID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    GroupName = db.Column(db.String(50), unique=True, nullable=False)
    Description = db.Column(db.String(256))
    Permissions = db.Column(db.JSON)
    IsActive = db.Column(db.Boolean, nullable=False, default=True)
    CreatedAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    UpdatedAt = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # foreign_keys specified here too for the reverse side
    user_mappings = db.relationship(
        'UserGroupMapping',
        backref='group',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='[UserGroupMapping.GroupID]'
    )

    def __repr__(self):
        return f'<UserGroup {self.GroupName}>'

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.GroupID,
            'name': self.GroupName,
            'description': self.Description,
            'permissions': self.Permissions,
            'is_active': self.IsActive
        }


class UserGroupMapping(db.Model):
    """
    Junction table linking users to groups.
    Has two FKs to User: UserID (the member) and AssignedBy (who granted it).
    """
    __tablename__ = 'UserGroupMapping'

    MappingID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    UserID = db.Column(db.Integer, db.ForeignKey('User.UserID', ondelete='CASCADE'), nullable=False)
    GroupID = db.Column(db.Integer, db.ForeignKey('UserGroup.GroupID', ondelete='CASCADE'), nullable=False)
    AssignedAt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    AssignedBy = db.Column(db.Integer, db.ForeignKey('User.UserID', ondelete='SET NULL'))

    # assigned_by_user relationship — separate from the main 'user' backref above
    assigned_by_user = db.relationship(
        'User',
        foreign_keys=[AssignedBy],
        backref='assignments_made'
    )

    __table_args__ = (
        db.UniqueConstraint('UserID', 'GroupID', name='UQ_UserGroup'),
    )

    def __repr__(self):
        return f'<UserGroupMapping User:{self.UserID} -> Group:{self.GroupID}>'


class AuditLog(db.Model):
    """
    Security audit logging table.
    Records all API operations for accountability.
    """
    __tablename__ = 'AuditLog'

    LogID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    UserID = db.Column(db.Integer)
    Username = db.Column(db.String(50))
    Action = db.Column(db.String(20), nullable=False)
    TableName = db.Column(db.String(50))
    RecordID = db.Column(db.Integer)
    OldValues = db.Column(db.JSON)
    NewValues = db.Column(db.JSON)
    IPAddress = db.Column(db.String(45))
    UserAgent = db.Column(db.String(512))
    APIEndpoint = db.Column(db.String(200))
    HTTPMethod = db.Column(db.String(10))
    ResponseStatus = db.Column(db.Integer)
    ResponseTime = db.Column(db.Integer)  # milliseconds
    IsAuthorized = db.Column(db.Boolean, nullable=False, default=True)
    ErrorMessage = db.Column(db.String(500))

    def __repr__(self):
        return f'<AuditLog {self.Action} on {self.TableName} by User:{self.UserID}>'

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.LogID,
            'timestamp': self.Timestamp.isoformat() if self.Timestamp else None,
            'user_id': self.UserID,
            'username': self.Username,
            'action': self.Action,
            'table_name': self.TableName,
            'record_id': self.RecordID,
            'endpoint': self.APIEndpoint,
            'method': self.HTTPMethod,
            'status': self.ResponseStatus,
            'is_authorized': self.IsAuthorized,
            'error': self.ErrorMessage
        }

    @classmethod
    def log(cls, action, table_name=None, record_id=None, user_id=None, username=None,
            old_values=None, new_values=None, request=None, response_status=None,
            response_time=None, is_authorized=True, error_message=None):
        """
        Create and save an audit log entry.
        Silently ignores errors so logging never breaks the main request flow.
        """
        try:
            log_entry = cls(
                UserID=user_id,
                Username=username,
                Action=action,
                TableName=table_name,
                RecordID=record_id,
                OldValues=old_values,
                NewValues=new_values,
                IPAddress=request.remote_addr if request else None,
                UserAgent=(request.headers.get('User-Agent') or '')[:512] if request else None,
                APIEndpoint=request.path if request else None,
                HTTPMethod=request.method if request else None,
                ResponseStatus=response_status,
                ResponseTime=response_time,
                IsAuthorized=is_authorized,
                ErrorMessage=error_message
            )
            db.session.add(log_entry)
            db.session.commit()
            return log_entry
        except Exception:
            db.session.rollback()
            return None
