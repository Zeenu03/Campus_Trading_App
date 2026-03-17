"""
Flask Application Factory
Campus Trading Application - Module B
"""

import os
import logging
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

from .config import get_config

db = SQLAlchemy()


def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    initialize_extensions(app)
    register_blueprints(app)
    configure_logging(app)
    register_error_handlers(app)

    register_debug_routes(app)

    with app.app_context():
        from . import models

    return app


def initialize_extensions(app):
    db.init_app(app)

    # supports_credentials=True is required so the browser sends the
    # access_token cookie on same-origin AJAX requests without being
    # blocked by Flask-CORS middleware.
    CORS(
        app,
        origins=app.config.get('CORS_ORIGINS', ['http://localhost:5000',
                                                  'http://127.0.0.1:5000']),
        supports_credentials=True
    )


def register_blueprints(app):
    from .routes import auth, members, listings, offers, transactions, admin, portfolio, views

    app.register_blueprint(auth.bp,         url_prefix='/api')
    app.register_blueprint(members.bp,      url_prefix='/api')
    app.register_blueprint(listings.bp,     url_prefix='/api')
    app.register_blueprint(offers.bp,       url_prefix='/api')
    app.register_blueprint(transactions.bp, url_prefix='/api')
    app.register_blueprint(admin.bp,        url_prefix='/api/admin')
    app.register_blueprint(portfolio.bp,    url_prefix='/api')
    app.register_blueprint(views.bp)


def configure_logging(app):
    log_dir = os.path.dirname(app.config.get('AUDIT_LOG_PATH', 'logs/audit.log'))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))

    file_handler = RotatingFileHandler(
        'logs/app.log', maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    ))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    app.logger.info('Campus Trading API started')


def register_error_handlers(app):

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required'
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource'
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Server Error: {error}')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        db.session.rollback()
        app.logger.error(f'Unhandled Exception: {error}', exc_info=True)
        return jsonify({
            'error': 'Server Error',
            'message': str(error) if app.debug else 'An unexpected error occurred'
        }), 500


def register_debug_routes(app):
    """Debug-only routes — auto-removed when DEBUG=False."""
    if not app.debug:
        return

    from flask import jsonify, request, g
    from .middleware.auth import require_auth, get_current_user

    @app.route('/api/debug/auth')
    @require_auth
    def debug_auth():
        user = get_current_user()
        return jsonify({
            'authenticated': True,
            'user_id':   user.UserID,
            'username':  user.Username,
            'role':      user.Role,
            'member_id': user.MemberID,
            'cookie_present': bool(request.cookies.get('access_token')),
        })

    @app.route('/api/debug/cookie')
    def debug_cookie():
        """Check what cookies the server sees — no auth required."""
        return jsonify({
            'access_token_present': bool(request.cookies.get('access_token')),
            'all_cookies': list(request.cookies.keys()),
        })
