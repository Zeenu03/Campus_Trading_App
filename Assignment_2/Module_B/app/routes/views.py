"""
Web UI Views — Campus Trading Application (Module B)

Architecture: server-side rendered MVC.
- GET  routes  → query DB, render template
- POST routes  → write to DB directly, then redirect  (no JWT needed)
- The REST /api/* endpoints remain available for external/Postman use
- Flask session (set on login) is the auth mechanism for the web UI
"""

from functools import wraps
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, abort)

from app.services.auth_service import AuthService
from app.services.audit_service import log_crud_operation
from app.models import (User, Listing, ListingImage, Member, Transaction,
                        Offer, Category, Rating, AuditLog, Report)
from app import db

bp = Blueprint('views', __name__)


# ── Auth decorators ─────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('views.login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('views.login_page'))
        if session['user'].get('role') != 'Admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('views.dashboard'))
        return f(*args, **kwargs)
    return decorated


def current_user_id():
    return session.get('user', {}).get('id')

def current_member_id():
    return session.get('user', {}).get('member_id')

def is_admin():
    return session.get('user', {}).get('role') == 'Admin'


# ── Auth pages ──────────────────────────────────────────────────────

@bp.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('views.dashboard'))
    return redirect(url_for('views.login_page'))


@bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user' in session:
        return redirect(url_for('views.dashboard'))

    error = None
    if request.method == 'POST':
        identifier = request.form.get('user', '').strip()
        password   = request.form.get('password', '')

        user = AuthService.authenticate_user(identifier, password)
        if user:
            session.permanent = True
            session['user'] = {
                'id':        user.UserID,
                'username':  user.Username,
                'email':     user.Email,
                'role':      user.Role,
                'member_id': user.MemberID,
                'admin_id':  user.AdminID,
            }
            return redirect(url_for('views.dashboard'))
        else:
            error = 'Invalid username or password.'

    return render_template('login.html', error=error)


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('views.login_page'))


# ── Dashboard ───────────────────────────────────────────────────────

@bp.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'active_listings':        Listing.query.filter_by(Status='Listed').count(),
        'completed_transactions': Transaction.query.filter_by(Status='Completed').count(),
        'pending_offers':         Offer.query.filter_by(OfferStatus='Submitted').count(),
        'total_members':          Member.query.filter_by(AccountStatus='Active').count(),
    }
    recent_listings = [l.to_dict(include_seller=True)
                       for l in Listing.query.filter_by(Status='Listed')
                       .order_by(Listing.CreatedDate.desc()).limit(6).all()]
    return render_template('dashboard.html', stats=stats, recent_listings=recent_listings)


# ── Listings ────────────────────────────────────────────────────────

@bp.route('/listings')
@login_required
def listings_page():
    page     = request.args.get('page', 1, type=int)
    per_page = 12
    query    = Listing.query

    status = request.args.get('status', 'Listed')
    if status and status != 'all':
        query = query.filter(Listing.Status == status)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Listing.Title.ilike(f'%{search}%')) |
            (Listing.Description.ilike(f'%{search}%'))
        )

    min_price = request.args.get('min_price', type=float)
    if min_price is not None:
        query = query.filter(Listing.AskingPrice >= min_price)

    max_price = request.args.get('max_price', type=float)
    if max_price is not None:
        query = query.filter(Listing.AskingPrice <= max_price)

    pagination = query.order_by(Listing.CreatedDate.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    listings = [l.to_dict(include_seller=True, include_images=True)
                for l in pagination.items]
    return render_template('listings/index.html',
                           listings=listings, pagination=pagination)


@bp.route('/listings/create', methods=['GET', 'POST'])
@login_required
def create_listing_page():
    categories = Category.query.filter_by(IsActive=True, ParentCategoryID=None).all()

    if request.method == 'POST':
        mid = current_member_id()
        if not mid:
            flash('You need a member profile to create a listing.', 'error')
            return redirect(url_for('views.create_listing_page'))

        title        = request.form.get('title', '').strip()
        asking_price = request.form.get('asking_price', type=float)
        category_id  = request.form.get('category_id', type=int)

        if not title or asking_price is None or not category_id:
            flash('Title, price and category are required.', 'error')
            return render_template('listings/create.html',
                                   categories=categories)

        listing = Listing(
            SellerID=mid,
            CategoryID=category_id,
            Title=title,
            Description=request.form.get('description', '').strip() or None,
            AskingPrice=asking_price,
            IsNegotiable='is_negotiable' in request.form,
            IsDonation='is_donation' in request.form,
            Condition=request.form.get('condition') or None,
            CourseCode=request.form.get('course_code', '').strip() or None,
            PreferredMeetingLocation=request.form.get('meeting_location', '').strip() or None,
            Status='Listed',
        )
        db.session.add(listing)
        db.session.commit()
        log_crud_operation('CREATE', 'Listing', listing.ListingID,
                           new_values=listing.to_dict())
        flash('Listing created successfully!', 'success')
        return redirect(url_for('views.listing_detail_page', id=listing.ListingID))

    return render_template('listings/create.html', categories=categories)


@bp.route('/listings/<int:id>')
@login_required
def listing_detail_page(id):
    listing = Listing.query.get_or_404(id)
    return render_template('listings/detail.html',
                           listing=listing.to_dict(include_seller=True,
                                                   include_images=True))


@bp.route('/listings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_listing_page(id):
    listing    = Listing.query.get_or_404(id)
    categories = Category.query.filter_by(IsActive=True, ParentCategoryID=None).all()

    # Ownership check
    if listing.SellerID != current_member_id() and not is_admin():
        flash('You can only edit your own listings.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))

    if request.method == 'POST':
        old_values = listing.to_dict()

        listing.Title       = request.form.get('title', listing.Title).strip()
        listing.Description = request.form.get('description', '').strip() or None
        listing.AskingPrice = request.form.get('asking_price', type=float) or listing.AskingPrice
        listing.CategoryID  = request.form.get('category_id', type=int)    or listing.CategoryID
        listing.Condition   = request.form.get('condition') or None
        listing.CourseCode  = request.form.get('course_code', '').strip() or None
        listing.PreferredMeetingLocation = request.form.get('meeting_location', '').strip() or None
        listing.IsNegotiable = 'is_negotiable' in request.form
        listing.IsDonation   = 'is_donation'   in request.form

        db.session.commit()
        log_crud_operation('UPDATE', 'Listing', id, old_values, listing.to_dict())
        flash('Listing updated successfully!', 'success')
        return redirect(url_for('views.listing_detail_page', id=id))

    return render_template('listings/create.html',
                           listing=listing.to_dict(include_images=True),
                           categories=categories, edit_mode=True)


@bp.route('/listings/<int:id>/delete', methods=['POST'])
@login_required
def delete_listing(id):
    if not is_admin():
        flash('Only admins can delete listings.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))
    listing = Listing.query.get_or_404(id)
    old     = listing.to_dict()
    listing.Status = 'Deleted'
    db.session.commit()
    log_crud_operation('DELETE', 'Listing', id, old)
    flash('Listing deleted.', 'success')
    return redirect(url_for('views.listings_page'))


@bp.route('/listings/<int:id>/close', methods=['POST'])
@login_required
def close_listing(id):
    listing = Listing.query.get_or_404(id)
    if listing.SellerID != current_member_id() and not is_admin():
        flash('Not authorized.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))
    listing.Status = 'Closed'
    db.session.commit()
    flash('Listing closed.', 'success')
    return redirect(url_for('views.listing_detail_page', id=id))


@bp.route('/listings/<int:id>/relist', methods=['POST'])
@login_required
def relist_listing(id):
    listing = Listing.query.get_or_404(id)
    if listing.SellerID != current_member_id() and not is_admin():
        flash('Not authorized.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))
    listing.Status = 'Listed'
    db.session.commit()
    flash('Listing re-listed!', 'success')
    return redirect(url_for('views.listing_detail_page', id=id))


# ── Offers ──────────────────────────────────────────────────────────

@bp.route('/listings/<int:id>/offer', methods=['POST'])
@login_required
def make_offer(id):
    listing = Listing.query.get_or_404(id)
    mid     = current_member_id()

    if not mid:
        flash('You need a member profile to make offers.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))

    if listing.SellerID == mid:
        flash("You can't make an offer on your own listing.", 'error')
        return redirect(url_for('views.listing_detail_page', id=id))

    if listing.Status != 'Listed':
        flash('This listing is no longer active.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))

    price = request.form.get('offered_price', type=float)
    if not price or price <= 0:
        flash('Please enter a valid offer price.', 'error')
        return redirect(url_for('views.listing_detail_page', id=id))

    offer = Offer(
        ListingID    = id,
        BuyerID      = mid,
        OfferedPrice = price,
        OfferMessage = request.form.get('message', '').strip() or None,
        OfferStatus  = 'Submitted',
    )
    db.session.add(offer)
    db.session.commit()
    log_crud_operation('CREATE', 'Offer', offer.OfferID, new_values=offer.to_dict())
    flash('Offer submitted successfully!', 'success')
    return redirect(url_for('views.listing_detail_page', id=id))


@bp.route('/offers')
@login_required
def offers_page():
    mid = current_member_id()
    if not mid and not is_admin():
        flash('You need a member profile to view offers.', 'error')
        return redirect(url_for('views.dashboard'))

    if is_admin():
        received = Offer.query.order_by(Offer.SubmittedDate.desc()).limit(50).all()
        sent     = []
    else:
        # Offers on my listings
        my_listing_ids = [l.ListingID for l in Listing.query.filter_by(SellerID=mid).all()]
        received = (Offer.query
                    .filter(Offer.ListingID.in_(my_listing_ids))
                    .order_by(Offer.SubmittedDate.desc()).all())
        # Offers I made
        sent = (Offer.query
                .filter_by(BuyerID=mid)
                .order_by(Offer.SubmittedDate.desc()).all())

    return render_template('offers.html', received=received, sent=sent)


@bp.route('/offers/<int:id>/accept', methods=['POST'])
@login_required
def accept_offer(id):
    offer = Offer.query.get_or_404(id)
    mid   = current_member_id()

    if offer.listing.SellerID != mid and not is_admin():
        flash('Only the seller can accept offers.', 'error')
        return redirect(url_for('views.offers_page'))

    if offer.OfferStatus != 'Submitted':
        flash(f'Cannot accept an offer with status: {offer.OfferStatus}', 'error')
        return redirect(url_for('views.offers_page'))

    offer.OfferStatus  = 'Accepted'
    offer.AgreedPrice  = offer.OfferedPrice
    offer.ResponseDate = datetime.utcnow()

    # Decline all other pending offers on same listing
    Offer.query.filter(
        Offer.ListingID == offer.ListingID,
        Offer.OfferID   != offer.OfferID,
        Offer.OfferStatus == 'Submitted'
    ).update({'OfferStatus': 'Declined', 'ResponseDate': datetime.utcnow()})

    offer.listing.Status = 'Pending'

    # Create transaction
    tx = Transaction(
        ListingID   = offer.ListingID,
        SellerID    = offer.listing.SellerID,
        BuyerID     = offer.BuyerID,
        OfferID     = offer.OfferID,
        AgreedPrice = offer.OfferedPrice,
        Status      = 'Scheduled',
    )
    db.session.add(tx)
    db.session.commit()
    log_crud_operation('UPDATE', 'Offer', id, new_values={'status': 'Accepted'})
    flash('Offer accepted! A transaction has been created.', 'success')
    return redirect(url_for('views.offers_page'))


@bp.route('/offers/<int:id>/decline', methods=['POST'])
@login_required
def decline_offer(id):
    offer = Offer.query.get_or_404(id)
    mid   = current_member_id()

    if offer.listing.SellerID != mid and not is_admin():
        flash('Only the seller can decline offers.', 'error')
        return redirect(url_for('views.offers_page'))

    offer.OfferStatus  = 'Declined'
    offer.ResponseDate = datetime.utcnow()
    db.session.commit()
    flash('Offer declined.', 'success')
    return redirect(url_for('views.offers_page'))


@bp.route('/offers/<int:id>/withdraw', methods=['POST'])
@login_required
def withdraw_offer(id):
    offer = Offer.query.get_or_404(id)
    mid   = current_member_id()

    if offer.BuyerID != mid and not is_admin():
        flash('Only the buyer can withdraw their offer.', 'error')
        return redirect(url_for('views.offers_page'))

    offer.OfferStatus  = 'Withdrawn'
    offer.ResponseDate = datetime.utcnow()
    db.session.commit()
    flash('Offer withdrawn.', 'success')
    return redirect(url_for('views.offers_page'))


# ── Transactions ─────────────────────────────────────────────────────

@bp.route('/transactions')
@login_required
def transactions_page():
    mid = current_member_id()
    if is_admin():
        txs = Transaction.query.order_by(Transaction.CreatedDate.desc()).limit(50).all()
    elif mid:
        txs = (Transaction.query
               .filter((Transaction.SellerID == mid) | (Transaction.BuyerID == mid))
               .order_by(Transaction.CreatedDate.desc()).all())
    else:
        txs = []

    return render_template('transactions.html', transactions=txs)


@bp.route('/transactions/<int:id>/confirm', methods=['POST'])
@login_required
def confirm_transaction(id):
    tx  = Transaction.query.get_or_404(id)
    mid = current_member_id()

    if tx.SellerID == mid or is_admin():
        tx.SellerConfirmed = True
    if tx.BuyerID == mid or is_admin():
        tx.BuyerConfirmed = True

    tx.Status = 'InProgress'
    if tx.SellerConfirmed and tx.BuyerConfirmed:
        tx.Status          = 'Completed'
        tx.TransactionDate = datetime.utcnow()
        if tx.listing:
            tx.listing.Status = 'Sold'
        flash('Transaction completed! Both parties confirmed.', 'success')
    else:
        flash('Your confirmation recorded. Waiting for the other party.', 'success')

    db.session.commit()
    log_crud_operation('UPDATE', 'Transaction', id, new_values={'status': tx.Status})
    return redirect(url_for('views.transactions_page'))


@bp.route('/transactions/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_transaction(id):
    tx  = Transaction.query.get_or_404(id)
    mid = current_member_id()

    if tx.SellerID != mid and tx.BuyerID != mid and not is_admin():
        flash('Not authorized.', 'error')
        return redirect(url_for('views.transactions_page'))

    tx.Status = 'Cancelled'
    if tx.listing and tx.listing.Status == 'Pending':
        tx.listing.Status = 'Listed'
    db.session.commit()
    flash('Transaction cancelled.', 'success')
    return redirect(url_for('views.transactions_page'))


@bp.route('/transactions/<int:id>/rate', methods=['POST'])
@login_required
def rate_transaction(id):
    tx  = Transaction.query.get_or_404(id)
    mid = current_member_id()

    if tx.Status != 'Completed':
        flash('Can only rate completed transactions.', 'error')
        return redirect(url_for('views.transactions_page'))

    existing = Rating.query.filter_by(TransactionID=id, RaterID=mid).first()
    if existing:
        flash('You have already rated this transaction.', 'error')
        return redirect(url_for('views.transactions_page'))

    stars = request.form.get('stars', type=int)
    if not stars or not (1 <= stars <= 5):
        flash('Please select a rating between 1 and 5 stars.', 'error')
        return redirect(url_for('views.transactions_page'))

    rated_id = tx.SellerID if mid == tx.BuyerID else tx.BuyerID

    rating = Rating(
        TransactionID = id,
        RaterID       = mid,
        RatedID       = rated_id,
        Stars         = stars,
        ReviewText    = request.form.get('review', '').strip() or None,
    )
    db.session.add(rating)
    db.session.commit()
    flash('Rating submitted!', 'success')
    return redirect(url_for('views.transactions_page'))


# ── Members ─────────────────────────────────────────────────────────

@bp.route('/members')
@login_required
def members_page():
    page  = request.args.get('page', 1, type=int)
    query = Member.query.filter_by(AccountStatus='Active')

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Member.Name.ilike(f'%{search}%')) |
            (Member.Email.ilike(f'%{search}%'))
        )
    dept = request.args.get('department', '').strip()
    if dept:
        query = query.filter(Member.Department.ilike(f'%{dept}%'))

    pagination = query.order_by(Member.Name).paginate(
        page=page, per_page=12, error_out=False)
    members = [m.to_dict() for m in pagination.items]
    return render_template('members/index.html', members=members, pagination=pagination)


@bp.route('/members/<int:id>/portfolio')
@login_required
def portfolio_page(id):
    member      = Member.query.get_or_404(id)
    all_ratings = Rating.query.filter_by(RatedID=id).all()
    avg_rating  = (round(sum(r.Stars for r in all_ratings) / len(all_ratings), 2)
                   if all_ratings else None)

    portfolio = {
        'member': {
            'id':            member.MemberID,
            'name':          member.Name,
            'department':    member.Department,
            'year_of_study': member.YearOfStudy,
            'hostel':        member.Hostel,
            'room_number':   member.RoomNumber,
            'bio':           member.Bio,
            'is_verified':   member.IsVerified,
            'member_since':  (member.AccountCreationDate.isoformat()
                              if member.AccountCreationDate else None),
        },
        'stats': {
            'active_listings':  Listing.query.filter_by(SellerID=id, Status='Listed').count(),
            'total_sales':      Transaction.query.filter_by(SellerID=id, Status='Completed').count(),
            'total_purchases':  Transaction.query.filter_by(BuyerID=id, Status='Completed').count(),
            'average_rating':   avg_rating,
            'total_ratings':    len(all_ratings),
        },
        'active_listings':  [l.to_dict() for l in
                             Listing.query.filter_by(SellerID=id, Status='Listed')
                             .order_by(Listing.CreatedDate.desc()).limit(10).all()],
        'ratings_received': [r.to_dict(include_users=True) for r in
                             sorted(all_ratings, key=lambda r: r.RatingDate, reverse=True)[:10]],
    }
    return render_template('portfolio.html', portfolio=portfolio)


# ── Admin ────────────────────────────────────────────────────────────

@bp.route('/admin')
@admin_required
def admin_page():
    stats = {
        'users':        {'total': User.query.count(),
                         'active': User.query.filter_by(IsActive=True).count(),
                         'admins': User.query.filter_by(Role='Admin').count()},
        'members':      {'total': Member.query.count(),
                         'active': Member.query.filter_by(AccountStatus='Active').count()},
        'listings':     {'total': Listing.query.count(),
                         'active': Listing.query.filter_by(Status='Listed').count(),
                         'sold':   Listing.query.filter_by(Status='Sold').count()},
        'transactions': {'total': Transaction.query.count(),
                         'completed': Transaction.query.filter_by(Status='Completed').count()},
        'offers':       {'total': Offer.query.count(),
                         'pending': Offer.query.filter_by(OfferStatus='Submitted').count()},
        'reports':      {'total': Report.query.count(),
                         'pending': Report.query.filter_by(Status='Submitted').count()},
        'security':     {'unauthorized_attempts':
                         AuditLog.query.filter_by(IsAuthorized=False).count()},
    }
    users   = User.query.order_by(User.CreatedAt.desc()).limit(100).all()
    reports = Report.query.order_by(Report.SubmittedDate.desc()).limit(50).all()
    logs    = AuditLog.query.order_by(AuditLog.Timestamp.desc()).limit(100).all()
    return render_template('admin/dashboard.html',
                           stats=stats, users=users, reports=reports, logs=logs)


@bp.route('/admin/users/<int:id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_user(id):
    user = User.query.get_or_404(id)
    user.IsActive = not user.IsActive
    db.session.commit()
    status = 'activated' if user.IsActive else 'deactivated'
    flash(f'User {user.Username} {status}.', 'success')
    return redirect(url_for('views.admin_page'))


@bp.route('/admin/reports/<int:id>/resolve', methods=['POST'])
@admin_required
def admin_resolve_report(id):
    report = Report.query.get_or_404(id)
    report.Status       = 'Resolved'
    report.Resolution   = request.form.get('resolution', 'Resolved by admin')
    report.ResolvedDate = datetime.utcnow()
    db.session.commit()
    flash('Report resolved.', 'success')
    return redirect(url_for('views.admin_page'))



# ── Setup / password fix route ───────────────────────────────────────

@bp.route('/setup-passwords', methods=['GET', 'POST'])
def setup_passwords():
    """
    One-time route to reset all seed user passwords using the app's
    own bcrypt implementation. Visit once, then it's done.
    Only works in development mode.
    """
    import os
    if os.getenv('FLASK_ENV', 'development') == 'production':
        abort(404)

    message = None
    if request.method == 'POST':
        try:
            passwords = {
                'admin':           'admin123',
                'amal.perera':     'password123',
                'nimali.fernando': 'password123',
                'kavindu.silva':   'password123',
                'vikram.mehta':    'password123',
            }
            updated = []
            for username, password in passwords.items():
                user = User.query.filter_by(Username=username).first()
                if user:
                    user.PasswordHash = AuthService.hash_password(password)
                    updated.append(username)

            # Also update Member table hashes
            members = Member.query.all()
            default_hash = AuthService.hash_password('password123')
            for m in members:
                m.PasswordHash = default_hash

            db.session.commit()
            message = f'Passwords updated for: {", ".join(updated)}.'
        except Exception as e:
            message = f'Error: {e}'

    # Show all users and their hash prefix for verification
    users = User.query.order_by(User.UserID).all()
    return render_template('setup_passwords.html', users=users, message=message)
