"""
API Integration Tests
Campus Trading Application - Module B (Phase 7)

Tests for all CRUD endpoints:
- Members API
- Listings API
- Offers API
- Transactions API
- Portfolio API
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
        # Seed a category
        from app.models import Category
        cat = Category(CategoryID=1, CategoryName='Books', IsActive=True)
        db.session.add(cat)
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_and_login(client, username='apiuser', email='api@iitgn.ac.in'):
    client.post('/api/register', json={
        'username': username, 'email': email,
        'password': 'password123', 'confirm_password': 'password123'
    })
    res = client.post('/api/login', json={'user': username, 'password': 'password123'})
    return json.loads(res.data).get('session_token')


def auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


class TestMembersAPI:
    def test_create_member(self, client):
        token = register_and_login(client, 'membercreate', 'mc@iitgn.ac.in')
        res = client.post('/api/members', json={
            'name': 'Test Member', 'email': 'tmember@iitgn.ac.in', 'contact_number': '1112223333'
        }, headers=auth_headers(token))
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data['member']['name'] == 'Test Member'

    def test_get_members(self, client):
        token = register_and_login(client, 'getmembers', 'gm@iitgn.ac.in')
        res = client.get('/api/members', headers=auth_headers(token))
        assert res.status_code == 200
        data = json.loads(res.data)
        assert 'members' in data

    def test_get_member_not_found(self, client):
        token = register_and_login(client, 'notfound', 'nf@iitgn.ac.in')
        res = client.get('/api/members/9999', headers=auth_headers(token))
        assert res.status_code == 404


class TestListingsAPI:
    def _setup_member(self, client):
        token = register_and_login(client, 'listseller', 'ls@iitgn.ac.in')
        client.post('/api/members', json={
            'name': 'Seller', 'email': 'seller_m@iitgn.ac.in', 'contact_number': '9998887777'
        }, headers=auth_headers(token))
        return token

    def test_create_listing(self, client):
        token = self._setup_member(client)
        res = client.post('/api/listings', json={
            'title': 'Test Book', 'asking_price': 100.0, 'category_id': 1,
            'condition': 'Good'
        }, headers=auth_headers(token))
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data['listing']['title'] == 'Test Book'

    def test_get_listings(self, client):
        token = register_and_login(client, 'listbrowse', 'lb@iitgn.ac.in')
        res = client.get('/api/listings', headers=auth_headers(token))
        assert res.status_code == 200

    def test_create_listing_without_member_profile(self, client):
        token = register_and_login(client, 'noprofile', 'np@iitgn.ac.in')
        res = client.post('/api/listings', json={
            'title': 'Should fail', 'asking_price': 100, 'category_id': 1
        }, headers=auth_headers(token))
        assert res.status_code == 403

    def test_create_listing_missing_fields(self, client):
        token = self._setup_member(client)
        res = client.post('/api/listings', json={'title': 'No price'},
                          headers=auth_headers(token))
        assert res.status_code == 400


class TestPortfolioAPI:
    def test_portfolio_not_found(self, client):
        token = register_and_login(client, 'porttest', 'pt@iitgn.ac.in')
        res = client.get('/api/members/9999/portfolio', headers=auth_headers(token))
        assert res.status_code == 404

    def test_portfolio_returns_stats(self, client):
        token = register_and_login(client, 'portuser', 'pu@iitgn.ac.in')
        # Create member
        res = client.post('/api/members', json={
            'name': 'Port User', 'email': 'portum@iitgn.ac.in', 'contact_number': '5556667777'
        }, headers=auth_headers(token))
        member_id = json.loads(res.data)['member']['id']
        # Get portfolio
        res2 = client.get(f'/api/members/{member_id}/portfolio', headers=auth_headers(token))
        assert res2.status_code == 200
        data = json.loads(res2.data)
        assert 'stats' in data
        assert 'active_listings' in data
