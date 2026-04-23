import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
LISTING_DURATION_DAYS = int(os.environ.get('LISTING_DURATION_DAYS', '7'))
MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', '5'))

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required for the cloud database.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    raise RuntimeError("Cloudinary environment variables are missing.")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key-before-production')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {
        "sslmode": "require",
        "connect_timeout": 10,
    }
}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    whatsapp_number = db.Column(db.String(30), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    is_hidden = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    listings = db.relationship('Listing', backref='seller', lazy=True, foreign_keys='Listing.user_id')
    comments = db.relationship('Comment', backref='author', lazy=True, foreign_keys='Comment.user_id')
    ratings_given = db.relationship('Rating', backref='reviewer', lazy=True, foreign_keys='Rating.reviewer_id')
    ratings_received = db.relationship('Rating', backref='rated_user', lazy=True, foreign_keys='Rating.seller_id')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def average_rating(self):
        active_ratings = [r.stars for r in self.ratings_received if not r.is_hidden and not r.is_deleted]
        if not active_ratings:
            return None
        return round(sum(active_ratings) / len(active_ratings), 1)


class Listing(db.Model):
    __tablename__ = 'listing'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)
    listing_type = db.Column(db.String(10), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_hidden = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    renewed_at = db.Column(db.DateTime, nullable=True)

    comments = db.relationship('Comment', backref='listing', lazy=True, cascade='all, delete-orphan')

    @property
    def status_label(self):
        return 'Gift' if self.listing_type == 'gift' else 'Buy'

    @property
    def is_expired(self):
        return datetime.now(timezone.utc) >= self.expires_at.replace(tzinfo=timezone.utc)


class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Rating(db.Model):
    __tablename__ = 'rating'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    is_hidden = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('seller_id', 'reviewer_id', name='unique_reviewer_per_seller'),
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file_storage):
    if not file_storage or file_storage.filename == '':
        return None

    if not allowed_file(file_storage.filename):
        return None

    try:
        result = cloudinary.uploader.upload(
            file_storage,
            folder="iu_marketplace",
            resource_type="image"
        )
        return result.get("secure_url")
    except Exception as e:
        print("Cloudinary upload error:", e)
        return None


def normalize_whatsapp(number: str) -> str:
    return ''.join(ch for ch in number if ch.isdigit())


def sync_listing_expiry():
    now = datetime.now(timezone.utc)
    active_listings = Listing.query.filter_by(is_deleted=False).all()
    changed = False
    for listing in active_listings:
        if listing.is_active and listing.expires_at.replace(tzinfo=timezone.utc) <= now:
            listing.is_active = False
            changed = True
    if changed:
        db.session.commit()


@app.before_request
def before_request():
    try:
        sync_listing_expiry()
    except Exception:
        pass

    if current_user.is_authenticated and (
        current_user.is_blocked or current_user.is_deleted or current_user.is_hidden
    ):
        logout_user()
        flash('Your account is not allowed to access the platform.', 'danger')
        return redirect(url_for('login'))


@app.context_processor
def inject_now():
    return {'now': datetime.now(timezone.utc)}


@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    listing_type = request.args.get('type', '').strip().lower()

    query = Listing.query.join(User).filter(
        Listing.is_deleted.is_(False),
        Listing.is_hidden.is_(False),
        Listing.is_active.is_(True),
        User.is_deleted.is_(False),
        User.is_hidden.is_(False),
        User.is_blocked.is_(False),
    )

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Listing.title.ilike(like),
                Listing.description.ilike(like)
            )
        )

    if listing_type in {'buy', 'gift'}:
        query = query.filter(Listing.listing_type == listing_type)

    listings = query.order_by(Listing.created_at.desc()).all()
    return render_template('index.html', listings=listings, q=q, listing_type=listing_type)


@app.route('/browse-listings')
def browse_listings():
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([full_name, email, whatsapp_number, password, confirm_password]):
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'warning')
            return redirect(url_for('register'))

        user = User(
            full_name=full_name,
            email=email,
            whatsapp_number=normalize_whatsapp(whatsapp_number)
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.is_deleted or user.is_blocked or user.is_hidden:
                flash('This account is blocked or unavailable.', 'danger')
                return redirect(url_for('login'))
            login_user(user)
            flash('Welcome back.', 'success')
            return redirect(url_for('index'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/listing/new', methods=['GET', 'POST'])
@login_required
def create_listing():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        listing_type = request.form.get('listing_type', '').strip().lower()
        price_raw = request.form.get('price', '').strip()
        image = request.files.get('image')

        if not title or not description or listing_type not in {'buy', 'gift'}:
            flash('Please complete all required listing details.', 'warning')
            return redirect(url_for('create_listing'))

        price = None
        if listing_type == 'buy':
            if not price_raw:
                flash('Please enter a price for sale items.', 'warning')
                return redirect(url_for('create_listing'))
            try:
                price = float(price_raw)
            except ValueError:
                flash('Price must be a valid number.', 'warning')
                return redirect(url_for('create_listing'))

        if image and image.filename and not allowed_file(image.filename):
            flash('Please upload a valid image file (png, jpg, jpeg, gif, webp).', 'warning')
            return redirect(url_for('create_listing'))

        image_url = save_image(image)
        if image and image.filename and not image_url:
            flash('Image upload failed. Please try again.', 'danger')
            return redirect(url_for('create_listing'))

        expires_at = datetime.now(timezone.utc) + timedelta(days=LISTING_DURATION_DAYS)
        listing = Listing(
            user_id=current_user.id,
            title=title,
            description=description,
            listing_type=listing_type,
            price=price,
            image_url=image_url,
            expires_at=expires_at,
            is_hidden=False,
            is_deleted=False,
            is_active=True,
        )
        db.session.add(listing)
        db.session.commit()
        flash('Listing created successfully.', 'success')
        return redirect(url_for('listing_detail', listing_id=listing.id))

    return render_template('create_listing.html')


@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if listing.is_deleted or listing.is_hidden:
        abort(404)

    if listing.seller.is_deleted or listing.seller.is_hidden or listing.seller.is_blocked:
        abort(404)

    comments = Comment.query.filter_by(
        listing_id=listing.id,
        is_hidden=False,
        is_deleted=False
    ).order_by(Comment.created_at.desc()).all()

    ratings = Rating.query.filter_by(
        seller_id=listing.user_id,
        is_hidden=False,
        is_deleted=False
    ).order_by(Rating.created_at.desc()).all()

    my_rating = None
    can_view_full = current_user.is_authenticated

    if current_user.is_authenticated:
        my_rating = Rating.query.filter_by(
            seller_id=listing.user_id,
            reviewer_id=current_user.id,
            is_deleted=False
        ).first()

    return render_template(
        'listing_detail.html',
        listing=listing,
        comments=comments,
        ratings=ratings,
        my_rating=my_rating,
        can_view_full=can_view_full
    )


@app.route('/listing/<int:listing_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if listing.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        listing.title = request.form.get('title', '').strip()
        listing.description = request.form.get('description', '').strip()
        listing.listing_type = request.form.get('listing_type', '').strip().lower()
        price_raw = request.form.get('price', '').strip()

        if listing.listing_type not in {'buy', 'gift'} or not listing.title or not listing.description:
            flash('Please provide valid listing details.', 'warning')
            return redirect(url_for('edit_listing', listing_id=listing.id))

        if listing.listing_type == 'buy':
            try:
                listing.price = float(price_raw)
            except ValueError:
                flash('Price must be a valid number.', 'warning')
                return redirect(url_for('edit_listing', listing_id=listing.id))
        else:
            listing.price = None

        image = request.files.get('image')
        if image and image.filename and not allowed_file(image.filename):
            flash('Please upload a valid image file (png, jpg, jpeg, gif, webp).', 'warning')
            return redirect(url_for('edit_listing', listing_id=listing.id))

        new_image = save_image(image)
        if image and image.filename and not new_image:
            flash('Image upload failed. Please try again.', 'danger')
            return redirect(url_for('edit_listing', listing_id=listing.id))

        if new_image:
            listing.image_url = new_image

        db.session.commit()
        flash('Listing updated.', 'success')
        return redirect(url_for('listing_detail', listing_id=listing.id))

    return render_template('edit_listing.html', listing=listing)


@app.route('/listing/<int:listing_id>/delete', methods=['POST'])
@login_required
def delete_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if listing.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    listing.is_deleted = True
    listing.is_active = False
    db.session.commit()
    flash('Listing deleted.', 'success')
    return redirect(url_for('my_listings'))


@app.route('/listing/<int:listing_id>/renew', methods=['POST'])
@login_required
def renew_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if listing.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    listing.is_active = True
    listing.expires_at = datetime.now(timezone.utc) + timedelta(days=LISTING_DURATION_DAYS)
    listing.renewed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Listing renewed for another {LISTING_DURATION_DAYS} days.', 'success')
    return redirect(url_for('my_listings'))


@app.route('/my-listings')
@login_required
def my_listings():
    listings = Listing.query.filter_by(
        user_id=current_user.id,
        is_deleted=False
    ).order_by(Listing.created_at.desc()).all()
    return render_template('my_listings.html', listings=listings)


@app.route('/listing/<int:listing_id>/comment', methods=['POST'])
@login_required
def add_comment(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    content = request.form.get('content', '').strip()

    if not content:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('listing_detail', listing_id=listing_id))

    comment = Comment(listing_id=listing.id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    flash('Comment posted.', 'success')
    return redirect(url_for('listing_detail', listing_id=listing_id))


@app.route('/seller/<int:seller_id>/rate', methods=['POST'])
@login_required
def rate_seller(seller_id):
    seller = User.query.get_or_404(seller_id)

    if seller.id == current_user.id:
        flash('You cannot rate yourself.', 'warning')
        return redirect(request.referrer or url_for('index'))

    stars_raw = request.form.get('stars', '').strip()
    review_text = request.form.get('review_text', '').strip()

    try:
        stars = int(stars_raw)
    except ValueError:
        flash('Please select a valid star rating.', 'warning')
        return redirect(request.referrer or url_for('index'))

    if stars < 1 or stars > 5:
        flash('Stars must be between 1 and 5.', 'warning')
        return redirect(request.referrer or url_for('index'))

    existing = Rating.query.filter_by(
        seller_id=seller.id,
        reviewer_id=current_user.id
    ).first()

    if existing:
        existing.stars = stars
        existing.review_text = review_text
        existing.is_hidden = False
        existing.is_deleted = False
    else:
        db.session.add(
            Rating(
                seller_id=seller.id,
                reviewer_id=current_user.id,
                stars=stars,
                review_text=review_text
            )
        )

    db.session.commit()
    flash('Rating saved.', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return render_template('admin_dashboard.html', users=users, listings=listings, comments=comments)


@app.route('/admin/user/<int:user_id>/<action>', methods=['POST'])
@login_required
@admin_required
def admin_user_action(user_id, action):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id and action in {'block', 'delete'}:
        flash('You cannot block or delete your own admin account.', 'warning')
        return redirect(url_for('admin_dashboard'))

    if action == 'block':
        user.is_blocked = not user.is_blocked
    elif action == 'hide':
        user.is_hidden = not user.is_hidden
    elif action == 'delete':
        user.is_deleted = True
        user.is_blocked = True
        for listing in user.listings:
            listing.is_deleted = True
            listing.is_active = False
    else:
        abort(400)

    db.session.commit()
    flash(f'User action {action} completed.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/listing/<int:listing_id>/<action>', methods=['POST'])
@login_required
@admin_required
def admin_listing_action(listing_id, action):
    listing = Listing.query.get_or_404(listing_id)

    if action == 'hide':
        listing.is_hidden = not listing.is_hidden
    elif action == 'delete':
        listing.is_deleted = True
        listing.is_active = False
    else:
        abort(400)

    db.session.commit()
    flash(f'Listing action {action} completed.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/comment/<int:comment_id>/<action>', methods=['POST'])
@login_required
@admin_required
def admin_comment_action(comment_id, action):
    comment = Comment.query.get_or_404(comment_id)

    if action == 'hide':
        comment.is_hidden = not comment.is_hidden
    elif action == 'delete':
        comment.is_deleted = True
    else:
        abort(400)

    db.session.commit()
    flash(f'Comment action {action} completed.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/init-db')
def init_db():
    db.create_all()

    admin_email = os.environ.get('DEFAULT_ADMIN_EMAIL', 'admin@iu.local')
    admin_password = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin123')

    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(
            full_name='System Admin',
            email=admin_email,
            whatsapp_number='966500000000',
            is_admin=True,
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()

    return f'Database initialized. Admin login: {admin_email} / {admin_password}'


if __name__ == '__main__':
    app.run(debug=True)