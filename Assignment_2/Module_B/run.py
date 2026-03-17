"""
Application Entry Point — Campus Trading (Module B)

Run with:
    python run.py

On startup (development mode only), automatically checks and fixes all
user password hashes using the app's own bcrypt library. This guarantees
regular users can always log in with 'password123' without any manual steps.
"""

import os
from app import create_app, db

app = create_app()


def auto_fix_passwords():
    """
    Automatically reset all seed-user passwords on startup.

    Pre-generated bcrypt hashes in SQL files are environment-specific —
    they may not verify correctly with a different OS or bcrypt version.
    This function re-hashes using the running app's own bcrypt, making
    login always work regardless of platform.

    Only runs in development mode and only when the User table exists.
    """
    if os.getenv('FLASK_ENV', 'development') == 'production':
        return

    try:
        import bcrypt as _bcrypt

        SEED_PASSWORDS = {
            'admin':           'admin123',
            'amal.perera':     'password123',
            'nimali.fernando': 'password123',
            'kavindu.silva':   'password123',
            'vikram.mehta':    'password123',
            'ravindu.bandara': 'password123',
        }

        from app.models import User, Member

        fixed = 0
        for username, password in SEED_PASSWORDS.items():
            user = User.query.filter_by(Username=username).first()
            if not user:
                continue

            # Check if the stored hash actually works
            try:
                ok = _bcrypt.checkpw(
                    password.encode('utf-8'),
                    user.PasswordHash.encode('utf-8')
                )
            except Exception:
                ok = False

            if not ok:
                # Hash is wrong — regenerate it
                new_hash = _bcrypt.hashpw(
                    password.encode('utf-8'),
                    _bcrypt.gensalt(12)
                ).decode('utf-8')
                user.PasswordHash = new_hash
                fixed += 1

        if fixed > 0:
            # Also fix Member table hashes
            default_hash = _bcrypt.hashpw(
                b'password123', _bcrypt.gensalt(12)
            ).decode('utf-8')
            for m in Member.query.all():
                m.PasswordHash = default_hash

            db.session.commit()
            print(f'[startup] Fixed {fixed} user password hash(es) '
                  f'— login will now work correctly.')
        else:
            print('[startup] All password hashes verified OK.')

    except Exception as e:
        # Never crash the app over password fixing
        print(f'[startup] Password check skipped: {e}')


# ── Run auto-fix inside app context on startup ───────────────────────
with app.app_context():
    auto_fix_passwords()


@app.shell_context_processor
def make_shell_context():
    from app.models import (
        User, Session, UserGroup, UserGroupMapping, AuditLog,
        Member, Administrator, Category,
        Listing, ListingImage, Offer, Transaction, Rating,
        WishRequest, Watchlist, Report, Notification,
        MessageThread, Message
    )
    return {
        'db': db, 'User': User, 'Session': Session,
        'Member': Member, 'Listing': Listing,
        'Offer': Offer, 'Transaction': Transaction
    }


@app.cli.command('init-db')
def init_db():
    """Initialize the database with tables."""
    db.create_all()
    print('Database tables created.')


@app.cli.command('fix-passwords')
def fix_passwords_cmd():
    """Manually trigger password hash fix for all seed users."""
    auto_fix_passwords()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
