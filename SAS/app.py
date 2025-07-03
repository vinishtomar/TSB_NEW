import os
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   Response, session, abort, make_response)
from flask_login import (LoginManager, UserMixin, login_user, login_required,
                         logout_user, current_user)
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

# --- APPLICATION SETUP ---
app = Flask(__name__)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"

app.secret_key = os.environ.get('SECRET_KEY', 'a_secure_random_secret_key_for_development')

# --- DATABASE CONFIGURATION (UPDATED FOR POSTGRESQL) ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://tsb_jilz_user:WQuuirqxSdknwZjsvldYzD0DbhcOBzQ7@dpg-d0jjegmmcj7s73836lp0-a/tsb_jilz'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- DATABASE MODELS ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), default='Prospect')
    last_contact_date = db.Column(db.DateTime, default=datetime.utcnow)
    quotes = db.relationship('Quote', backref='client', lazy=True, cascade="all, delete-orphan")

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    brand = db.Column(db.String(80))
    model = db.Column(db.String(80))
    serial_number = db.Column(db.String(120), unique=True)
    last_maintenance_date = db.Column(db.Date)
    next_maintenance_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='In Service')
    assigned_client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    assigned_client = db.relationship('Client', backref='equipment')

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    service_type = db.Column(db.String(100))
    details = db.Column(db.Text)
    price = db.Column(db.Float)
    vat_rate = db.Column(db.Float, default=0.20)
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))

    @property
    def total_price(self):
        return self.price * (1 + self.vat_rate) if self.price and self.vat_rate is not None else 0

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False) # Maintenance, Quote, Client
    related_id = db.Column(db.Integer)
    due_date = db.Column(db.DateTime)
    is_dismissed = db.Column(db.Boolean, default=False)

# --- UTILITY FUNCTIONS ---

def generate_alerts():
    """Checks for conditions and creates alerts."""
    today = datetime.utcnow().date()
    Alert.query.delete()
    
    maintenance_due = Equipment.query.filter(Equipment.next_maintenance_date <= today + timedelta(days=30)).all()
    for item in maintenance_due:
        db.session.add(Alert(message=f"Maintenance for {item.name} ({item.brand})", category="Maintenance", related_id=item.id, due_date=item.next_maintenance_date))

    quotes_expiring = Quote.query.filter(Quote.expires_at <= datetime.utcnow() + timedelta(days=7), Quote.status == 'Pending').all()
    for quote in quotes_expiring:
        db.session.add(Alert(message=f"Quote #{quote.quote_number} for {quote.client.name} expires soon", category="Quote", related_id=quote.id, due_date=quote.expires_at))

    db.session.commit()

# --- AUTHENTICATION ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Login failed. Check username and password.", "danger")
    return render_template('main_template.html', view='login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- CORE APPLICATION ROUTES ---

## Main Dashboard
@app.route('/')
@login_required
def dashboard():
    generate_alerts()
    clients = Client.query.order_by(Client.last_contact_date.desc()).limit(5).all()
    quotes = Quote.query.filter_by(status='Pending').order_by(Quote.created_at.desc()).limit(5).all()
    alerts = Alert.query.filter_by(is_dismissed=False).order_by(Alert.due_date.asc()).all()
    return render_template('main_template.html', view='dashboard', clients=clients, quotes=quotes, alerts=alerts)

## Client Routes
@app.route('/clients')
@login_required
def list_clients():
    clients = Client.query.order_by(Client.name).all()
    return render_template('main_template.html', view='clients_list', clients=clients)

@app.route('/client/<int:client_id>')
@login_required
def client_profile(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('main_template.html', view='client_profile', client=client)

@app.route('/client/add', methods=['GET', 'POST'])
@login_required
def add_client():
    if request.method == 'POST':
        new_client = Client(name=request.form['name'], email=request.form['email'], phone=request.form['phone'], address=request.form['address'], status=request.form['status'])
        db.session.add(new_client)
        db.session.commit()
        flash('Client added successfully!', 'success')
        return redirect(url_for('list_clients'))
    return render_template('main_template.html', view='client_form', form_title="Ajouter un Client")

@app.route('/client/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.name, client.email, client.phone, client.address, client.status, client.last_contact_date = request.form['name'], request.form['email'], request.form['phone'], request.form['address'], request.form['status'], datetime.utcnow()
        db.session.commit()
        flash('Client updated successfully!', 'success')
        return redirect(url_for('client_profile', client_id=client.id))
    return render_template('main_template.html', view='client_form', form_title="Modifier le Client", client=client)

## Equipment Routes
@app.route('/equipment')
@login_required
def list_equipment():
    status_filter = request.args.get('status')
    query = Equipment.query
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    equipment_list = query.all()
    return render_template('main_template.html', view='equipment_list', equipment=equipment_list, current_filter=status_filter or 'all')

@app.route('/equipment/add', methods=['GET', 'POST'])
@login_required
def add_equipment():
    if request.method == 'POST':
        new_equip = Equipment(name=request.form['name'], brand=request.form['brand'], model=request.form['model'], serial_number=request.form['serial_number'], status=request.form['status'], last_maintenance_date=datetime.strptime(request.form['last_maintenance_date'], '%Y-%m-%d').date() if request.form['last_maintenance_date'] else None, next_maintenance_date=datetime.strptime(request.form['next_maintenance_date'], '%Y-%m-%d').date() if request.form['next_maintenance_date'] else None)
        db.session.add(new_equip)
        db.session.commit()
        flash('Equipment added successfully!', 'success')
        return redirect(url_for('list_equipment'))
    return render_template('main_template.html', view='equipment_form')


## Quote Routes
@app.route('/quotes')
@login_required
def list_quotes():
    quotes = Quote.query.order_by(Quote.created_at.desc()).all()
    return render_template('main_template.html', view='quote_list', quotes=quotes)

@app.route('/quote/add', methods=['GET', 'POST'])
@login_required
def add_quote():
    if request.method == 'POST':
        last_quote = Quote.query.order_by(Quote.id.desc()).first()
        new_id = (last_quote.id + 1) if last_quote else 1
        quote_number = f"DEV-{datetime.now().year}-{new_id:04d}"
        new_quote = Quote(quote_number=quote_number, client_id=request.form['client_id'], service_type=request.form['service_type'], details=request.form['details'], price=float(request.form['price']), vat_rate=float(request.form['vat_rate']))
        db.session.add(new_quote)
        db.session.commit()
        flash(f'Quote {quote_number} created successfully!', 'success')
        return redirect(url_for('list_quotes'))
    clients = Client.query.all()
    return render_template('main_template.html', view='quote_form', clients=clients)

@app.route('/quote/<int:quote_id>/pdf')
@login_required
def generate_quote_pdf(quote_id):
    try:
        from weasyprint import HTML
    except ImportError:
        flash("Error: WeasyPrint is not installed. Run 'pip install WeasyPrint'", "danger")
        return redirect(url_for('list_quotes'))
    quote = Quote.query.get_or_404(quote_id)
    rendered_html = render_template('quote_pdf_template.html', quote=quote)
    pdf = HTML(string=rendered_html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Quote_{quote.quote_number}.pdf'
    return response

# --- DATABASE AND APP INITIALIZATION ---
# This block runs when the app starts, ensuring the DB is created.
with app.app_context():
    db.create_all()
    # Create a default admin user if one doesn't exist
    if not User.query.filter_by(username='admin').first():
        hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
        db.session.add(User(username='admin', password_hash=hashed_password, role='admin'))
        db.session.commit()

# This part is now only for running the app locally
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=True)
