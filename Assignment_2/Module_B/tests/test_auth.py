"""
Authentication Tests
Campus Trading Application - Module B (Phase 7)

Tests for:
- User registration
- Login / logout
- JWT token generation & verification
- Session management
- Password hashing
"""
import pytest
import json


@pytest.fixture
def client(app):
    return app.test_client()


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


class TestRegistration:
    def test_register_success(self, client):
        """Register a new user successfully."""
        res = client.post('/api/register', json={
            'username': 'testuser',
            'email': 'test@iitgn.ac.in',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data['user']['username'] == 'testuser'

    def test_register_duplicate_username(self, client):
        """Duplicate username returns 409."""
        payload = {
            'username': 'dupuser', 'email': 'a@iitgn.ac.in',
            'password': 'password123', 'confirm_password': 'password123'
        }
        client.post('/api/register', json=payload)
        payload['email'] = 'b@iitgn.ac.in'
        res = client.post('/api/register', json=payload)
        assert res.status_code == 409

    def test_register_short_password(self, client):
        """Password < 8 chars is rejected."""
        res = client.post('/api/register', json={
            'username': 'shortpw', 'email': 'short@iitgn.ac.in',
            'password': '123', 'confirm_password': '123'
        })
        assert res.status_code == 400

    def test_register_missing_fields(self, client):
        """Missing required fields returns 400."""
        res = client.post('/api/register', json={'username': 'noemail'})
        assert res.status_code == 400


class TestLogin:
    def _register(self, client, username='logintest', email='login@iitgn.ac.in', pw='password123'):
        client.post('/api/register', json={
            'username': username, 'email': email,
            'password': pw, 'confirm_password': pw
        })

    def test_login_success(self, client):
        self._register(client)
        res = client.post('/api/login', json={'user': 'logintest', 'password': 'password123'})
        assert res.status_code == 200
        data = json.loads(res.data)
        assert 'session_token' in data

    def test_login_wrong_password(self, client):
        self._register(client)
        res = client.post('/api/login', json={'user': 'logintest', 'password': 'wrongpassword'})
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        res = client.post('/api/login', json={'user': 'nobody', 'password': 'test'})
        assert res.status_code == 401

    def test_login_with_email(self, client):
        self._register(client)
        res = client.post('/api/login', json={'user': 'login@iitgn.ac.in', 'password': 'password123'})
        assert res.status_code == 200


class TestSession:
    def _register_and_login(self, client):
        client.post('/api/register', json={
            'username': 'sesstest', 'email': 'sess@iitgn.ac.in',
            'password': 'password123', 'confirm_password': 'password123'
        })
        res = client.post('/api/login', json={'user': 'sesstest', 'password': 'password123'})
        return json.loads(res.data)['session_token']

    def test_is_auth_with_valid_token(self, client):
        token = self._register_and_login(client)
        res = client.get('/api/isAuth', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200

    def test_is_auth_no_token(self, client):
        res = client.get('/api/isAuth')
        assert res.status_code == 401

    def test_is_auth_invalid_token(self, client):
        res = client.get('/api/isAuth', headers={'Authorization': 'Bearer invalid.token.here'})
        assert res.status_code == 401

    def test_logout(self, client):
        token = self._register_and_login(client)
        res = client.post('/api/logout', headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200
        # Token should be revoked
        res2 = client.get('/api/isAuth', headers={'Authorization': f'Bearer {token}'})
        assert res2.status_code == 401
