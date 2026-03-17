"""
Flask Application Configuration
Campus Trading Application - Module B
"""

import os
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def _build_db_uri(user, password, host, port, name):
    """
    URL-encode the password so special characters (@, #, %, +, spaces)
    don't break the SQLAlchemy connection string.
    e.g. password 'root@2026' becomes 'root%402026' in the URI.
    """
    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}?charset=utf8mb4"
    )


class Config:
    # ── Flask ────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG   = False
    TESTING = False

    # ── Flask session cookie ─────────────────────────────────────────
    # These prevent the Flask session cookie conflicting with the JWT
    # access_token cookie, and keep sessions alive for 24 hours.
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = 'Lax'
    SESSION_COOKIE_SECURE    = False   # set True in production (HTTPS only)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # ── Database ─────────────────────────────────────────────────────
    DB_HOST     = os.getenv('DB_HOST',     'localhost')
    DB_PORT     = os.getenv('DB_PORT',     '3306')
    DB_NAME     = os.getenv('DB_NAME',     'CampusTrading')
    DB_USER     = os.getenv('DB_USER',     'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    SQLALCHEMY_DATABASE_URI    = _build_db_uri(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO            = False

    # ── JWT ──────────────────────────────────────────────────────────
    JWT_SECRET_KEY             = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ALGORITHM              = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_ACCESS_TOKEN_EXPIRES   = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400)))

    # ── Logging ──────────────────────────────────────────────────────
    LOG_LEVEL       = os.getenv('LOG_LEVEL', 'INFO')
    AUDIT_LOG_PATH  = os.getenv('AUDIT_LOG_PATH', 'logs/audit.log')

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv(
        'CORS_ORIGINS',
        'http://localhost:5000,http://127.0.0.1:5000'
    ).split(',')

    # ── Bcrypt ───────────────────────────────────────────────────────
    BCRYPT_LOG_ROUNDS = 12


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False   # flip to True to log every SQL statement


class TestingConfig(Config):
    TESTING = True
    DEBUG   = True
    _TEST_DB = 'CampusTrading_Test'
    SQLALCHEMY_DATABASE_URI = _build_db_uri(
        os.getenv('DB_USER', 'root'),
        os.getenv('DB_PASSWORD', ''),
        os.getenv('DB_HOST', 'localhost'),
        os.getenv('DB_PORT', '3306'),
        'CampusTrading_Test'
    )


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True   # require HTTPS in production

    @classmethod
    def init_app(cls, app):
        assert os.getenv('SECRET_KEY'),     'SECRET_KEY must be set in production'
        assert os.getenv('JWT_SECRET_KEY'), 'JWT_SECRET_KEY must be set in production'
        assert os.getenv('DB_PASSWORD'),    'DB_PASSWORD must be set in production'


config = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}


def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
