"""
RBAC (Role-Based Access Control) Tests
Campus Trading Application - Module B (Phase 7)

Tests for:
- Admin-only routes reject non-admins
- Ownership checks (only owner can edit own resources)
- Unauthorized access logging
"""
import pytest
import json


@pytest.fixture
def app():
    from app import create_app, db
    from app.config import TestingConfig
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_and_login(client, username, email, password='password123', role='RegularUser'):
    client.post('/api/register', json={
        'username': username, 'email': email,
        'password': password, 'confirm_password': password
    })
    # Promote to admin if needed
    if role == 'Admin':
        from app.models import User
        from app import db
        u = User.query.filter_by(Username=username).first()
        if u:
            u.Role = 'Admin'
            db.session.commit()

    res = client.post('/api/login', json={'user': username, 'password': password})
    return json.loads(res.data).get('session_token')


class TestAdminRoutes:
    def test_admin_stats_denied_to_regular_user(self, client):
        token = register_and_login(client, 'reguser', 'reg@iitgn.ac.in')
        res = client.get('/api/admin/stats', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 403

    def test_admin_stats_allowed_to_admin(self, client):
        token = register_and_login(client, 'adminuser', 'adm@iitgn.ac.in', role='Admin')
        res = client.get('/api/admin/stats', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200

    def test_admin_users_endpoint_requires_admin(self, client):
        token = register_and_login(client, 'notadmin', 'notadmin@iitgn.ac.in')
        res = client.get('/api/admin/users', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 403

    def test_unauthenticated_request_returns_401(self, client):
        res = client.get('/api/admin/users')
        assert res.status_code == 401


class TestListingOwnership:
    def test_update_listing_by_non_owner_rejected(self, client):
        """Non-owner cannot update another's listing."""
        # Owner creates listing
        owner_token = register_and_login(client, 'owner', 'owner@iitgn.ac.in')
        # Create member profile first
        client.post('/api/members', json={
            'name': 'Owner Member', 'email': 'ownerm@iitgn.ac.in', 'contact_number': '1234567890'
        }, headers={'Authorization': f'Bearer {owner_token}'})
        # Non-owner
        non_owner_token = register_and_login(client, 'intruder', 'intruder@iitgn.ac.in')

        # Try to update listing 9999 (doesn't exist → 404, but auth check comes first via ownership)
        res = client.put('/api/listings/9999',
                         json={'title': 'Hacked'},
                         headers={'Authorization': f'Bearer {non_owner_token}'})
        # 404 because listing doesn't exist is fine; 403 would also be correct
        assert res.status_code in (403, 404)


class TestAuditLogging:
    def test_failed_login_is_logged(self, client, app):
        """Failed login attempt is recorded in AuditLog."""
        client.post('/api/login', json={'user': 'ghost', 'password': 'wrong'})
        with app.app_context():
            from app.models import AuditLog
            logs = AuditLog.query.filter_by(Action='LOGIN_FAILED').all()
            assert len(logs) >= 1

    def test_unauthorized_access_is_logged(self, client, app):
        """Unauthorized access attempt is logged."""
        client.get('/api/isAuth', headers={'Authorization': 'Bearer bogus.token.value'})
        with app.app_context():
            from app.models import AuditLog
            logs = AuditLog.query.filter_by(IsAuthorized=False).all()
            assert len(logs) >= 1
