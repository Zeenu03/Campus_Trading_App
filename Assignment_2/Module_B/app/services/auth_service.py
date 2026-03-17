"""
Authentication Service
Campus Trading Application - Module B

Provides:
- Password hashing with bcrypt
- JWT token generation and verification
- Session management

Key fix: is_session_valid() now looks up by TokenJTI (short UUID with a
proper UNIQUE index) instead of the full Token string (VARCHAR 512 with
only a 255-char prefix index), which caused missed matches on longer tokens.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
import jwt
from flask import current_app

from app import db
from app.models import User, Session


class AuthService:

    # ── Password ─────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        rounds = current_app.config.get('BCRYPT_LOG_ROUNDS', 12)
        salt   = bcrypt.gensalt(rounds=rounds)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception:
            return False

    # ── Token ────────────────────────────────────────────────────────

    @staticmethod
    def generate_token(user: User) -> Tuple[str, str, datetime]:
        """
        Generate a signed JWT for the user.
        Returns (token_string, jti, expires_at_datetime).
        """
        jti          = str(uuid.uuid4())
        expires_delta = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=24))
        expires_at   = datetime.utcnow() + expires_delta

        payload = {
            'sub':       user.UserID,
            'username':  user.Username,
            'email':     user.Email,
            'role':      user.Role,
            'member_id': user.MemberID,
            'admin_id':  user.AdminID,
            'iat':       datetime.utcnow(),
            'exp':       expires_at,
            'jti':       jti,
        }

        token = jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm=current_app.config.get('JWT_ALGORITHM', 'HS256')
        )
        return token, jti, expires_at

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Decode and verify a JWT. Returns payload dict or None."""
        try:
            return jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=[current_app.config.get('JWT_ALGORITHM', 'HS256')]
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ── Session ──────────────────────────────────────────────────────

    @staticmethod
    def create_session(user: User, token: str, jti: str, expires_at: datetime,
                       ip_address: str = None, user_agent: str = None) -> Session:
        session = Session(
            UserID    = user.UserID,
            Token     = token,
            TokenJTI  = jti,
            ExpiresAt = expires_at,
            IPAddress = ip_address,
            UserAgent = (user_agent or '')[:512],
        )
        db.session.add(session)
        db.session.commit()
        return session

    @staticmethod
    def is_session_valid(token: str) -> bool:
        """
        Check whether a session is still active (not revoked, not expired).

        IMPORTANT: we look up by TokenJTI (a short UUID with a UNIQUE index),
        NOT by the full Token string.  The Token column is VARCHAR(512) with
        only a 255-char prefix index, so filter_by(Token=...) can silently
        miss a 300-char JWT.  TokenJTI is always 36 chars and fully indexed.
        """
        try:
            # Decode without signature verification just to read the jti claim
            payload = jwt.decode(
                token,
                options={'verify_signature': False},
                algorithms=['HS256']
            )
            jti = payload.get('jti')
            if not jti:
                return False

            session = Session.query.filter_by(TokenJTI=jti).first()
            return session.is_valid if session else False
        except Exception:
            return False

    @staticmethod
    def revoke_session(token: str) -> bool:
        """Revoke a session by its token string."""
        try:
            payload = jwt.decode(
                token,
                options={'verify_signature': False},
                algorithms=['HS256']
            )
            jti = payload.get('jti')
            if not jti:
                return False

            session = Session.query.filter_by(TokenJTI=jti, IsRevoked=False).first()
            if session:
                session.IsRevoked = True
                session.RevokedAt = datetime.utcnow()
                db.session.commit()
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def revoke_all_user_sessions(user_id: int) -> int:
        sessions = Session.query.filter_by(UserID=user_id, IsRevoked=False).all()
        for s in sessions:
            s.IsRevoked = True
            s.RevokedAt = datetime.utcnow()
        db.session.commit()
        return len(sessions)

    @staticmethod
    def get_session_by_token(token: str) -> Optional[Session]:
        return Session.query.filter_by(Token=token).first()

    # ── Authentication ───────────────────────────────────────────────

    @staticmethod
    def authenticate_user(username_or_email: str, password: str) -> Optional[User]:
        user = User.query.filter(
            (User.Username == username_or_email) | (User.Email == username_or_email)
        ).first()

        if not user or not user.IsActive:
            return None

        if not AuthService.verify_password(password, user.PasswordHash):
            return None

        user.LastLoginAt = datetime.utcnow()
        db.session.commit()
        return user

    @staticmethod
    def cleanup_expired_sessions() -> int:
        expired = Session.query.filter(Session.ExpiresAt < datetime.utcnow()).all()
        for s in expired:
            db.session.delete(s)
        db.session.commit()
        return len(expired)
