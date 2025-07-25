import os
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   Response, session, abort, make_response)
from flask_login import (LoginManager, UserMixin, login_user, login_required,
                         logout_user, current_user)
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

# --- APPLICATION SETUP ---
app = Flask(__name__)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
db = SQLAlchemy()

app.secret_key = os.environ.get('SECRET_KEY', 'a_secure_random_secret_key_for_development')

# --- DATABASE CONFIGURATION ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mydatabase.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager.login_view = "login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"

# --- DECORATEUR DE ROLE ---
def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403) # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

hebergement_employee_association = db.Table('hebergement_employee_association',
    db.Column('hebergement_id', db.Integer, db.ForeignKey('hebergement.id'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employee.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")
    # LIGNE À AJOUTER :
    documents = db.relationship('Document', backref='owner', lazy=True)
# ... etc pour tous vos modèles ...
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), default='Prospect')
    last_contact_date = db.Column(db.DateTime, default=datetime.utcnow)
    quotes = db.relationship('Quote', backref='client', lazy=True, cascade="all, delete-orphan")
    chantiers = db.relationship('Chantier', backref='client', lazy=True)
    factures = db.relationship('Facture', backref='client', lazy=True)
    sav_tickets = db.relationship('SavTicket', backref='client', lazy=True)
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    brand = db.Column(db.String(80))
    model = db.Column(db.String(80))
    serial_number = db.Column(db.String(120), unique=True)
    last_maintenance_date = db.Column(db.Date)
    next_maintenance_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='In Service')
class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    details = db.Column(db.Text)
    price = db.Column(db.Float)
    vat_rate = db.Column(db.Float, default=0.20)
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def total_price(self):
        return self.price * (1 + self.vat_rate) if self.price and self.vat_rate is not None else 0
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    hire_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    salary = db.Column(db.Float, nullable=True)
    leave_requests = db.relationship('LeaveRequest', backref='employee', lazy='dynamic')
    hebergements = db.relationship('Hebergement', secondary=hebergement_employee_association, back_populates='employees')
class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False, default='Annual Leave')
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending')
class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    position_applied_for = db.Column(db.String(100), nullable=False)
    application_date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Applied')
class Chantier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    status = db.Column(db.String(50), default='Planifié')
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    documents = db.relationship('Document', backref='chantier', lazy=True)
class Facture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Brouillon')
    due_date = db.Column(db.Date)
    pdf_filename = db.Column(db.String(300), nullable=True) 

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # Renommé de 'filename' à 'name'
    url = db.Column(db.String(500), nullable=False)   # Nouveau champ pour le lien
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    chantier_id = db.Column(db.Integer, db.ForeignKey('chantier.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
class SavTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Ouvert')
class PlanningEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
class Hebergement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(300), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    employees = db.relationship('Employee', secondary=hebergement_employee_association, back_populates='hebergements')

# --- AUTHENTICATION & CORE ROUTES ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            # On vérifie le rôle pour la redirection
            if current_user.role == 'CEO':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('bienvenue'))
    return render_template('main_template.html', view='login')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
@role_required(['CEO'])
def dashboard():
    clients = Client.query.order_by(Client.last_contact_date.desc()).limit(5).all()
    quotes = Quote.query.filter_by(status='Pending').order_by(Quote.created_at.desc()).limit(5).all()
    return render_template('main_template.html', view='dashboard', clients=clients, quotes=quotes)

# --- ROUTES "AUTRES" (Accès: Tous les utilisateurs connectés) ---
@app.route('/clients')
@login_required
@role_required(['CEO', 'RH']) # <-- AJOUTÉ
def list_clients():
    clients = Client.query.order_by(Client.name).all()
    return render_template('main_template.html', view='clients_list', clients=clients)

@app.route('/planning')
@login_required
def list_planning():
    events = PlanningEvent.query.all()
    return render_template('main_template.html', view='planning_list', events=events)

@app.route('/documents')
@login_required
def list_documents():
     # Le CEO voit tous les documents
    if current_user.role == 'CEO':
        documents = Document.query.order_by(Document.upload_date.desc()).all()
    # Les autres utilisateurs ne voient que les leurs
    else:
        documents = Document.query.filter_by(user_id=current_user.id).order_by(Document.upload_date.desc()).all()
        
    return render_template('main_template.html', view='documents_list', documents=documents)

@app.route('/documents/add', methods=['GET', 'POST'])
@login_required
def add_document():
    if request.method == 'POST':
        filename = request.form.get('filename')
        if not filename:
            flash("Le nom du fichier est requis.", "danger")
        else:
            # On associe le document à l'utilisateur actuellement connecté
            new_doc = Document(filename=filename, owner=current_user)
            db.session.add(new_doc)
            db.session.commit()
            flash("Document ajouté avec succès.", "success")
            return redirect(url_for('list_documents'))

    # Affiche un simple formulaire (pour l'exemple)
    return render_template('main_template.html', view='document_form')

@app.route('/client/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'RH'])
def add_client():

    if request.method == 'POST':
        new_client = Client(
            name=request.form['name'], 
            email=request.form['email'], 
            phone=request.form['phone'], 
            address=request.form['address'], 
            status=request.form['status']
        )
        db.session.add(new_client)
        db.session.commit()
        flash('Client ajouté avec succès !', 'success')
        return redirect(url_for('list_clients'))
    return render_template('main_template.html', view='client_form', form_title="Ajouter un Client", client=None)

@app.route('/client/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'RH'])
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.name = request.form['name']
        client.email = request.form['email']
        client.phone = request.form['phone']
        client.address = request.form['address']
        client.status = request.form['status']
        client.last_contact_date = datetime.utcnow()
        db.session.commit()
        flash('Client mis à jour avec succès !', 'success')
        return redirect(url_for('client_profile', client_id=client.id))
    return render_template('main_template.html', view='client_form', form_title="Modifier le Client", client=client)

@app.route('/Bienvenue')
@login_required
def bienvenue():
    # Cette page sert de portail pour les utilisateurs non-CEO
    return render_template('main_template.html', view='bienvenue_page')

@app.route('/client/<int:client_id>')
@login_required
@role_required(['CEO', 'RH'])
def client_profile(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('main_template.html', view='client_profile', client=client)

# --- ROUTES "OPÉRATIONS" (Accès: CEO, Chef de projet) ---
@app.route('/equipment')
@login_required
@role_required(['CEO', 'Chef de projet'])
def list_equipment():
    equipment_list = Equipment.query.all()
    return render_template('main_template.html', view='equipment_list', equipment=equipment_list)

@app.route('/chantiers')
@login_required
@role_required(['CEO', 'Chef de projet'])
def list_chantiers():
    chantiers = Chantier.query.all()
    return render_template('main_template.html', view='chantiers_list', chantiers=chantiers)

@app.route('/sav')
@login_required
@role_required(['CEO', 'Chef de projet'])
def list_sav():
    tickets = SavTicket.query.all()
    return render_template('main_template.html', view='sav_list', tickets=tickets)


# --- ROUTES "FINANCES" (Accès: CEO, Finance) ---
@app.route('/quotes')
@login_required
@role_required(['CEO', 'Finance'])
def list_quotes():
    quotes = Quote.query.order_by(Quote.created_at.desc()).all()
    return render_template('main_template.html', view='quote_list', quotes=quotes)

@app.route('/factures')
@login_required
@role_required(['CEO', 'Finance'])
def list_factures():
    factures = Facture.query.all()
    return render_template('main_template.html', view='factures_list', factures=factures)


# --- ROUTES "RH" (Accès: CEO, RH) ---
@app.route('/employees')
@login_required
@role_required(['CEO', 'RH'])
def list_employees():
    employees = Employee.query.order_by(Employee.full_name).all()
    return render_template('main_template.html', view='employees_list', employees=employees)

@app.route('/leaves')
@login_required
@role_required(['CEO', 'RH'])
def list_leaves():
    leaves = LeaveRequest.query.order_by(LeaveRequest.start_date.desc()).all()
    return render_template('main_template.html', view='leaves_list', leaves=leaves)

@app.route('/candidates')
@login_required
@role_required(['CEO', 'RH'])
def list_candidates():
    candidates = Candidate.query.order_by(Candidate.application_date.desc()).all()
    return render_template('main_template.html', view='candidates_list', candidates=candidates)

@app.route('/planning/add', methods=['GET', 'POST'])
@login_required
def add_planning_event():
    if request.method == 'POST':
        title = request.form.get('title')
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        description = request.form.get('description')

        if not title or not start_str or not end_str:
            flash("Le titre et les dates de début et de fin sont requis.", "danger")
        else:
            # Conversion des chaînes de caractères en objets datetime
            start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')

            new_event = PlanningEvent(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description
            )
            db.session.add(new_event)
            db.session.commit()
            flash("Nouvel événement ajouté au planning.", "success")
            return redirect(url_for('list_planning'))
    
    return render_template('main_template.html', view='planning_form', form_title="Ajouter un Événement")
# --- ROUTES "ADMINISTRATION" (Accès: CEO Seulement) ---
@app.route('/users')
@login_required
@role_required(['CEO'])
def manage_users():
    users = User.query.all()
    return render_template('main_template.html', view='users_list', users=users)

@app.route('/leaves/request', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'RH'])
def request_leave():
    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        if start_date > end_date:
            flash('La date de début ne peut pas être après la date de fin.', 'danger')
            return redirect(url_for('request_leave'))
        new_request = LeaveRequest(
            employee_id=request.form['employee_id'],
            leave_type=request.form['leave_type'],
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(new_request)
        db.session.commit()
        flash('Demande de congé soumise.', 'success')
        return redirect(url_for('list_leaves'))
    employees = Employee.query.all()
    return render_template('main_template.html', view='leave_request_form', employees=employees, form_title="Demander un Congé")

@app.route('/equipment/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'Chef de projet'])
def add_equipment():
    if request.method == 'POST':
        new_equip = Equipment(
            name=request.form['name'],
            brand=request.form['brand'],
            model=request.form['model'],
            serial_number=request.form['serial_number'],
            status=request.form['status'],
            last_maintenance_date=datetime.strptime(request.form['last_maintenance_date'], '%Y-%m-%d').date() if request.form['last_maintenance_date'] else None,
            next_maintenance_date=datetime.strptime(request.form['next_maintenance_date'], '%Y-%m-%d').date() if request.form['next_maintenance_date'] else None
        )
        db.session.add(new_equip)
        db.session.commit()
        flash('Équipement ajouté.', 'success')
        return redirect(url_for('list_equipment'))
    return render_template('main_template.html', view='equipment_form')

@app.route('/quote/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'Finance'])
def add_quote():
    if request.method == 'POST':
        last_quote = Quote.query.order_by(Quote.id.desc()).first()
        new_id = (last_quote.id + 1) if last_quote else 1
        quote_number = f"DEV-{datetime.now().year}-{new_id:04d}"
        new_quote = Quote(
            quote_number=quote_number,
            client_id=request.form['client_id'],
            details=request.form['details'],
            price=float(request.form['price']),
            vat_rate=float(request.form['vat_rate'])
        )
        db.session.add(new_quote)
        db.session.commit()
        flash(f'Devis {quote_number} créé.', 'success')
        return redirect(url_for('list_quotes'))
    clients = Client.query.all()
    return render_template('main_template.html', view='quote_form', clients=clients)

@app.route('/sav/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'Chef de projet'])
def add_sav_ticket():
    if request.method == 'POST':
        last_ticket = SavTicket.query.order_by(SavTicket.id.desc()).first()
        new_id = (last_ticket.id + 1) if last_ticket else 1
        ticket_number = f"TICKET-{datetime.now().year}-{new_id:04d}"
        new_ticket = SavTicket(
            ticket_number=ticket_number,
            client_id=request.form['client_id'],
            description=request.form['description'],
            status='Ouvert'
        )
        db.session.add(new_ticket)
        db.session.commit()
        flash('Ticket SAV créé.', 'success')
        return redirect(url_for('list_sav'))
    clients = Client.query.all()
    return render_template('main_template.html', view='sav_form', clients=clients, form_title="Nouveau Ticket SAV")

@app.route('/facture/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'Finance'])
def add_facture():
    if request.method == 'POST':
        last_invoice = Facture.query.order_by(Facture.id.desc()).first()
        new_id = (last_invoice.id + 1) if last_invoice else 1
        invoice_number = f"FACT-{datetime.now().year}-{new_id:04d}"
        new_facture = Facture(
            invoice_number=invoice_number,
            client_id=request.form['client_id'],
            amount=float(request.form['amount']),
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form['due_date'] else None,
            status='Brouillon'
        )
        pdf_file = request.files.get('pdf_file')
        if pdf_file and pdf_file.filename != '':
            # Sécuriser le nom du fichier
            filename = secure_filename(pdf_file.filename)
            # Sauvegarder le fichier dans notre dossier UPLOAD_FOLDER
            pdf_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Enregistrer le nom du fichier dans la base de données
            new_facture.pdf_filename = filename

        db.session.add(new_facture)
        db.session.commit()
        flash('Facture créée avec succès.', 'success')
        return redirect(url_for('list_factures'))

    clients = Client.query.all()
    return render_template('main_template.html', view='facture_form', clients=clients, form_title="Nouvelle Facture")
@app.route('/users/add', methods=['POST'])
@login_required
@role_required(['CEO'])
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    if User.query.filter_by(username=username).first():
        flash("Ce nom d'utilisateur existe déjà.", "warning")
        return redirect(url_for('manage_users'))
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password_hash=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()
    flash("Nouvel utilisateur ajouté.", "success")
    return redirect(url_for('manage_users'))

@app.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required(['CEO'])
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.role == 'CEO':
        flash("Vous ne pouvez pas supprimer le compte CEO.", "danger")
        return redirect(url_for('manage_users'))
    db.session.delete(user_to_delete)
    db.session.commit()
    flash("Utilisateur supprimé.", "success")
    return redirect(url_for('manage_users'))

@app.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required(['CEO'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'CEO':
        flash("Le rôle du CEO ne peut pas être modifié.", "warning")
        return redirect(url_for('manage_users'))
    if request.method == 'POST':
        user.role = request.form.get('role')
        db.session.commit()
        flash("Rôle mis à jour.", "success")
        return redirect(url_for('manage_users'))
    return render_template('main_template.html', view='user_edit_form', user=user)


@app.route('/hebergements')
@login_required
@role_required(['CEO', 'RH'])
def list_hebergements():
    hebergements = Hebergement.query.order_by(Hebergement.start_date.desc()).all()
    return render_template('main_template.html', view='hebergements_list', hebergements=hebergements)

@app.route('/hebergement/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'RH'])
def add_hebergement():
    if request.method == 'POST':
        # On crée d'abord l'objet hébergement
        new_hebergement = Hebergement(
            address=request.form.get('address'),
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form['end_date'] else None,
            cost=float(request.form.get('cost')) if request.form.get('cost') else None,
            notes=request.form.get('notes')
        )

        # On récupère la liste des IDs d'employés sélectionnés
        employee_ids = request.form.getlist('employee_ids')
        if employee_ids:
            # On trouve les objets Employé correspondants
            selected_employees = Employee.query.filter(Employee.id.in_(employee_ids)).all()
            # On les assigne à l'hébergement
            new_hebergement.employees = selected_employees
        
        db.session.add(new_hebergement)
        db.session.commit()
        flash("Hébergement ajouté avec succès.", "success")
        return redirect(url_for('list_hebergements'))

    employees = Employee.query.all()
    return render_template('main_template.html', view='hebergement_form', form_title="Ajouter un Hébergement", employees=employees)
@app.route('/chantier/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'Chef de projet'])
def add_chantier():
    if request.method == 'POST':
        new_chantier = Chantier(
            name=request.form.get('name'),
            client_id=request.form.get('client_id'),
            status=request.form.get('status'),
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date() if request.form['start_date'] else None,
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form['end_date'] else None
        )
        db.session.add(new_chantier)
        db.session.commit()
        flash('Nouveau chantier créé avec succès.', 'success')
        return redirect(url_for('list_chantiers'))

    clients = Client.query.all()
    return render_template('main_template.html', view='chantier_form', form_title="Créer un Chantier", clients=clients)
@app.route('/employee/add', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'RH'])
def add_employee():
    if request.method == 'POST':
        hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date() if request.form['hire_date'] else datetime.utcnow().date()
        salary = float(request.form['salary']) if request.form['salary'] else None
        
        new_employee = Employee(
            full_name=request.form['full_name'],
            position=request.form['position'],
            email=request.form['email'],
            phone=request.form['phone'],
            hire_date=hire_date,
            salary=salary
        )
        db.session.add(new_employee)
        db.session.commit()
        flash('Employé ajouté avec succès !', 'success')
        return redirect(url_for('list_employees'))
        
    return render_template('main_template.html', view='employee_form', form_title="Ajouter un Employé", employee=None)
@app.route('/employee/edit/<int:employee_id>', methods=['GET', 'POST'])
@login_required
@role_required(['CEO', 'RH'])
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    if request.method == 'POST':
        employee.full_name = request.form['full_name']
        employee.position = request.form['position']
        employee.email = request.form['email']
        employee.phone = request.form['phone']
        employee.hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date() if request.form['hire_date'] else employee.hire_date
        employee.salary = float(request.form['salary']) if request.form['salary'] else employee.salary
        
        db.session.commit()
        flash('Les informations de l\'employé ont été mises à jour !', 'success')
        return redirect(url_for('list_employees'))
        
    return render_template('main_template.html', view='employee_form', form_title="Modifier l'Employé", employee=employee)

@app.route('/chantier/<int:chantier_id>')
@login_required
@role_required(['CEO', 'Chef de projet'])
def chantier_profile(chantier_id):
    chantier = Chantier.query.get_or_404(chantier_id)
    return render_template('main_template.html', view='chantier_profile', chantier=chantier)

@app.route('/chantier/<int:chantier_id>/add_document', methods=['POST'])
@login_required
@role_required(['CEO', 'Chef de projet'])
def add_document_to_chantier(chantier_id):
    chantier = Chantier.query.get_or_404(chantier_id)
    doc_name = request.form.get('doc_name')
    doc_url = request.form.get('doc_url')

    if not doc_name or not doc_url:
        flash("Le nom et le lien du document sont requis.", 'danger')
    else:
        new_document = Document(
            name=doc_name,
            url=doc_url,
            chantier_id=chantier.id,
            owner=current_user 
        )
        db.session.add(new_document)
        db.session.commit()
        flash('Document lié au chantier avec succès.', 'success')

    return redirect(url_for('chantier_profile', chantier_id=chantier_id))
# --- DATABASE AND APP INITIALIZATION ---
if __name__ == '__main__':
    with app.app_context():
        print("--- Initialisation de la base de données... ---")
        db.create_all()
        default_users = {
            'ceo': {'password': 'password', 'role': 'CEO'},
            'rh': {'password': 'password', 'role': 'RH'},
            'finance': {'password': 'password', 'role': 'Finance'},
            'chef': {'password': 'password', 'role': 'Chef de projet'},
        }
        for username, details in default_users.items():
            if not User.query.filter_by(username=username).first():
                hashed_password = bcrypt.generate_password_hash(details['password']).decode('utf-8')
                db.session.add(User(username=username, password_hash=hashed_password, role=details['role']))
        db.session.commit()
        print("--- Base de données prête. ---")
    app.run(debug=True)