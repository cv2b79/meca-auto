import json
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import Forfait, RecupSurcharge, Consumable, Parametre, Enseignant, Classe, User, Client, Vehicule, OrdreReparation, Log, Fourniture

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    tab = request.args.get('tab', 'general')
    
    # General settings only - other tabs moved to admin
    if tab != 'general':
        return redirect(url_for('settings.admin'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # === UTILISATEURS ===
        if action == 'add_user':
            nom = request.form.get('nom')
            prenom = request.form.get('prenom')
            login = request.form.get('login')
            password = request.form.get('password')
            role = request.form.get('role')
            email = request.form.get('email')
            new_classe_nom = request.form.get('new_classe')
            
            if nom and prenom and login and password and role:
                print(f"Creating user: {login}")  # Debug
                if User.query.filter_by(login=login).first():
                    flash('Login déjà utilisé', 'error')
                else:
                    # Handle new class creation
                    classe_id = request.form.get('classe_id')
                    if new_classe_nom:
                        existing_classe = Classe.query.filter_by(nom=new_classe_nom).first()
                        if existing_classe:
                            classe_id = existing_classe.id
                        else:
                            new_classe = Classe(nom=new_classe_nom)
                            db.session.add(new_classe)
                            db.session.flush()
                            classe_id = new_classe.id
                    
                    user = User(nom=nom, prenom=prenom, login=login, role=role, email=email or None)
                    user.set_password(password)
                    if classe_id:
                        user.classe_id = int(classe_id)
                    db.session.add(user)
                    db.session.commit()
                    print(f"User created: {user.login}")  # Debug
                    flash('Utilisateur créé: ' + login, 'success')
        
        elif action == 'toggle_user':
            user = User.query.get(request.form.get('id'))
            if user and user.id != current_user.id:
                user.actif = not user.actif
                flash(f'Utilisateur {"activé" if user.actif else "désactivé"}', 'success')
        
        elif action == 'edit_user':
            user = User.query.get(request.form.get('id'))
            if user:
                user.nom = request.form.get('nom')
                user.prenom = request.form.get('prenom')
                user.email = request.form.get('email') or None
                user.login = request.form.get('login')
                user.role = request.form.get('role')
                classe_id = request.form.get('classe_id')
                user.classe_id = int(classe_id) if classe_id else None
                db.session.commit()
                flash('Utilisateur modifié', 'success')
        
        elif action == 'delete_user':
            user = User.query.get(request.form.get('id'))
            if user and user.id != current_user.id:
                user_name = f"{user.prenom} {user.nom}"
                db.session.delete(user)
                Log.log(current_user, 'delete_user', f'Utilisateur supprimé: {user_name}', 'User', user.id)
                flash('Utilisateur supprimé', 'success')
        
        # === ENSEIGNANTS ===
        elif action == 'add_enseignant':
            nom = request.form.get('nom')
            prenom = request.form.get('prenom')
            email = request.form.get('email')
            telephone = request.form.get('telephone')
            if nom and prenom:
                ens = Enseignant(nom=nom, prenom=prenom, email=email, telephone=telephone)
                db.session.add(ens)
                flash('Enseignant ajouté', 'success')
        
        elif action == 'toggle_enseignant':
            ens = Enseignant.query.get(request.form.get('id'))
            if ens:
                ens.actif = not ens.actif
                flash(f'Enseignant {"activé" if ens.actif else "désactivé"}', 'success')
        
        elif action == 'delete_enseignant':
            ens = Enseignant.query.get(request.form.get('id'))
            if ens:
                db.session.delete(ens)
                flash('Enseignant supprimé', 'success')
        
        # === CLASSES ===
        elif action == 'add_classe':
            nom = request.form.get('nom')
            niveau = request.form.get('niveau')
            if nom:
                cls = Classe(nom=nom, niveau=niveau)
                db.session.add(cls)
                flash('Classe ajoutée', 'success')
        
        elif action == 'toggle_classe':
            cls = Classe.query.get(request.form.get('id'))
            if cls:
                cls.actif = not cls.actif
                flash(f'Classe {"activée" if cls.actif else "désactivée"}', 'success')
        
        elif action == 'delete_classe':
            cls = Classe.query.get(request.form.get('id'))
            if cls:
                db.session.delete(cls)
                flash('Classe supprimée', 'success')
        
        # === CONFIGURATION EMAIL ===
        elif action == 'save_smtp':
            smtp_settings = {
                'smtp_host': request.form.get('smtp_host'),
                'smtp_port': request.form.get('smtp_port'),
                'smtp_user': request.form.get('smtp_user'),
                'smtp_password': request.form.get('smtp_password'),
                'smtp_from': request.form.get('smtp_from'),
                'email_notifications': request.form.get('email_notifications', '')
            }
            for key, value in smtp_settings.items():
                param = Parametre.query.filter_by(cle=key).first()
                if param:
                    param.valeur = value
                else:
                    param = Parametre(cle=key, valeur=value)
                    db.session.add(param)
            flash('Configuration email enregistrée', 'success')
        
        db.session.commit()
        return redirect(url_for('settings.index'))
    
    forfaits = Forfait.query.filter_by(actif=True).all()
    surcharges = RecupSurcharge.query.filter_by(actif=True).all()
    consommables = Consumable.query.filter_by(actif=True).all()
    enseignants = User.query.filter_by(role='enseignant').order_by(User.nom).all()
    classes = Classe.query.order_by(Classe.nom).all()
    users = User.query.order_by(User.nom).all()
    
    smtp_config = {}
    for key in ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from', 'email_notifications']:
        param = Parametre.query.filter_by(cle=key).first()
        smtp_config[key] = param.valeur if param else ''
    
    from app.models import ChecklistItem
    checklist_items = ChecklistItem.query.order_by(ChecklistItem.ordre).all()
    
    return render_template('settings/index.html', 
        forfaits=forfaits, 
        surcharges=surcharges, 
        consommables=consommables,
        enseignants=enseignants,
        smtp_config=smtp_config,
        classes=classes,
        users=users,
        tab=tab,
        checklist_items=checklist_items)

# === MON COMPTE - CHANGEMENT MOT DE PASSE ===
@settings_bp.route('/mon-compte', methods=['GET', 'POST'])
@login_required
def mon_compte():
    # Eleves cannot change password
    if current_user.role == 'eleve':
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            security_question = request.form.get('security_question')
            security_answer = request.form.get('security_answer')
            
            if not current_user.check_password(current_password):
                flash('Mot de passe actuel incorrect', 'error')
            elif new_password != confirm_password:
                flash('Les mots de passe ne correspondent pas', 'error')
            elif len(new_password) < 4:
                flash('Le mot de passe doit contenir au moins 4 caractères', 'error')
            else:
                current_user.set_password(new_password)
                current_user.must_change_password = False
                if security_question:
                    if security_answer and security_question.lower() in security_answer.lower():
                        flash('La réponse ne peut pas contenir la question', 'error')
                        return redirect(url_for('settings.mon_compte'))
                    current_user.security_question = security_question
                    current_user.security_answer = security_answer
                db.session.commit()
                Log.log(current_user, 'change_password', 'Mot de passe modifié', 'User', current_user.id)
                flash('Mot de passe modifié avec succès', 'success')
    
    return render_template('settings/mon_compte.html')

# === FORFAITS ===
@settings_bp.route('/forfait/new', methods=['POST'])
@login_required
def forfait_new():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    forfait = Forfait(
        nom=request.form.get('nom'),
        description=request.form.get('description'),
        montant=request.form.get('montant')
    )
    db.session.add(forfait)
    db.session.commit()
    flash('Forfait créé', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/forfait/<int:id>/edit', methods=['POST'])
@login_required
def forfait_edit(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    forfait = Forfait.query.get_or_404(id)
    forfait.nom = request.form.get('nom')
    forfait.description = request.form.get('description')
    forfait.montant = request.form.get('montant')
    db.session.commit()
    flash('Forfait modifié', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/forfait/<int:id>/delete', methods=['POST'])
@login_required
def forfait_delete(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    forfait = Forfait.query.get_or_404(id)
    forfait.actif = False
    db.session.commit()
    flash('Forfait supprimé', 'success')
    return redirect(url_for('settings.index'))

# === FOURNITURES ===
@settings_bp.route('/fourniture/new', methods=['POST'])
@login_required
def fourniture_new():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    fourniture = Fourniture(
        nom=request.form.get('nom'),
        prix_unitaire=request.form.get('prix_unitaire') or 0
    )
    db.session.add(fourniture)
    db.session.commit()
    flash('Fourniture créée', 'success')
    return redirect(url_for('settings.admin', tab='fournitures') + '#fournitures')

@settings_bp.route('/fourniture/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def fourniture_edit(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    fourniture = Fourniture.query.get_or_404(id)
    
    if request.method == 'POST':
        fourniture.nom = request.form.get('nom')
        fourniture.prix_unitaire = request.form.get('prix_unitaire') or 0
        db.session.commit()
        flash('Fourniture modifiée', 'success')
        return redirect(url_for('settings.admin', tab='fournitures') + '#fournitures')
    
    return render_template('settings/fourniture_edit.html', fourniture=fourniture)

@settings_bp.route('/fourniture/<int:id>/delete', methods=['POST'])
@login_required
def fourniture_delete(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    fourniture = Fourniture.query.get_or_404(id)
    fourniture.actif = False
    db.session.commit()
    flash('Fourniture supprimée', 'success')
    return redirect(url_for('settings.admin', tab='fournitures') + '#fournitures')

# === IMPORT ÉLÈVES ===
@settings_bp.route('/import_eleves', methods=['POST'])
@login_required
def import_eleves():
    print("DEBUG: import_eleves called")
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    if 'file' not in request.files:
        print("DEBUG: No file in request")
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('settings.admin', tab='import'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('settings.admin', tab='import'))
    
    if not file.filename.endswith('.csv'):
        flash('Le fichier doit être au format CSV', 'error')
        return redirect(url_for('settings.admin', tab='import'))
    
    import csv
    content = file.read().decode('utf-8').splitlines()
    # Auto-detect delimiter (comma or semicolon)
    first_line = content[0] if content else ''
    delimiter = ';' if ';' in first_line else ','
    
    # Clean headers (remove BOM if present)
    content[0] = content[0].replace('\ufeff', '')
    reader = csv.DictReader(content, delimiter=delimiter)
    
    print(f"DEBUG: Delimiter detected: {delimiter}")
    print(f"DEBUG: Headers: {reader.fieldnames}")
    
    count = 0
    errors = []
    for i, row in enumerate(reader, 1):
        print(f"DEBUG: Row {i}: {row}")
        try:
            # Handle various column name formats
            nom = row.get('nom', '') or row.get('Nom', '') or row.get('NOM', '')
            prenom = row.get('prénom', '') or row.get('prenom', '') or row.get('Prénom', '') or row.get('Prenom', '') or row.get('PRÉNOM', '')
            ddn = row.get('date de naissance', '') or row.get('ddn', '') or row.get('Date de naissance', '') or row.get('DDN', '')
            classe_nom = row.get('classe', '') or row.get('Classe', '') or row.get('CLASSE', '')
            email = row.get('adresse e-mail', '') or row.get('adresse email', '') or row.get('email', '') or row.get('Email', '') or row.get('Adresse E-mail', '')
            
            nom = nom.strip()
            prenom = prenom.strip()
            ddn = ddn.strip()
            classe_nom = classe_nom.strip()
            email = email.strip()
            
            print(f"DEBUG: nom='{nom}', prenom='{prenom}', classe='{classe_nom}', email='{email}'")
            
            if not nom or not prenom:
                errors.append(f"Ligne {i}: Nom ou Prénom manquant")
                continue
            
            # Create class if it doesn't exist and get its ID
            classe_id = None
            if classe_nom:
                classe = Classe.query.filter_by(nom=classe_nom).first()
                if not classe:
                    classe = Classe(nom=classe_nom, actif=True)
                    db.session.add(classe)
                    db.session.flush()
                classe_id = classe.id
            
            # Generate login from first name + first letter of last name
            login = (prenom.split()[0][:3] + nom[:3]).lower().replace(' ', '')
            
            # Check if user already exists
            existing = User.query.filter_by(login=login).first()
            if existing:
                errors.append(f"Ligne {i}: Login '{login}' existe déjà")
                continue
            
            # Generate password from date of birth if provided
            if ddn:
                # Remove separators and use DDMMYYYY format
                password = ddn.replace('-', '').replace('/', '').replace('.', '')
                if len(password) == 8:  # Valid format DDMMYYYY
                    password = password  # Keep as is
                else:
                    password = login  # Fallback to login
            else:
                password = login  # Default password = login if no DDN
            
            # Create user
            user = User(
                nom=nom,
                prenom=prenom,
                login=login,
                email=email if email else None,
                role='eleve',
                actif=True,
                classe_id=classe_id
            )
            user.set_password(password)
            db.session.add(user)
            count += 1
            
        except Exception as e:
            errors.append(f"Ligne {i}: Erreur - {str(e)}")
    
    db.session.commit()
    
    if count > 0:
        flash(f'{count} élève(s) importé(s) avec succès', 'success')
    if errors:
        flash(f'Erreurs: {" | ".join(errors[:5])}', 'warning')
        if len(errors) > 5:
            flash(f'...et {len(errors)-5} autres erreurs', 'warning')
    
    return redirect(url_for('settings.admin', tab='import'))

# === SURCHARGES RECUP ===
@settings_bp.route('/surcharge/new', methods=['POST'])
@login_required
def surcharge_new():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    surcharge = RecupSurcharge(
        nom=request.form.get('nom'),
        description=request.form.get('description'),
        montant=request.form.get('montant')
    )
    db.session.add(surcharge)
    db.session.commit()
    flash('Frais de dépollution créé', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/surcharge/<int:id>/delete', methods=['POST'])
@login_required
def surcharge_delete(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    surcharge = RecupSurcharge.query.get_or_404(id)
    surcharge.actif = False
    db.session.commit()
    flash('Frais supprimé', 'success')
    return redirect(url_for('settings.index'))

# === CONSOMMABLES ===
@settings_bp.route('/consommable/new', methods=['POST'])
@login_required
def consommable_new():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    consommable = Consumable(
        nom=request.form.get('nom'),
        unite=request.form.get('unite', 'pcs'),
        prix_unitaire=request.form.get('prix_unitaire'),
        stock=request.form.get('stock', 0)
    )
    db.session.add(consommable)
    db.session.commit()
    flash('Consommable créé', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/consommable/<int:id>/edit', methods=['POST'])
@login_required
def consommable_edit(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    consommable = Consumable.query.get_or_404(id)
    consommable.nom = request.form.get('nom')
    consommable.unite = request.form.get('unite')
    consommable.prix_unitaire = request.form.get('prix_unitaire')
    consommable.stock = request.form.get('stock')
    db.session.commit()
    flash('Consommable modifié', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/consommable/<int:id>/delete', methods=['POST'])
@login_required
def consommable_delete(id):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    consommable = Consumable.query.get_or_404(id)
    consommable.actif = False
    db.session.commit()
    flash('Consommable supprimé', 'success')
    return redirect(url_for('settings.index'))

# === CHECKLIST - GESTION PAR ENSEIGNANTS ===
@settings_bp.route('/checklist', methods=['GET', 'POST'])
@login_required
def checklist():
    # Only teachers and DDFPT can access
    if current_user.role not in ['ddfpt', 'enseignant']:
        flash('Accès réservé', 'error')
        return redirect(url_for('main.index'))
    
    from app.models import ChecklistItem
    checklist_items = ChecklistItem.query.order_by(ChecklistItem.ordre).all()
    
    return render_template('settings/checklist.html', checklist_items=checklist_items)

# === ADMIN - GESTION COMPLÈTE ===
@settings_bp.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    # Only DDFPT can access admin
    if current_user.role != 'ddfpt':
        flash('Accès réservé au DDFPT', 'error')
        return redirect(url_for('main.index'))
    
    tab = request.args.get('tab', 'general')
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Save etablissement info
        if action == 'save_etablissement':
            for key in ['etab_nom', 'etab_adresse', 'etab_tel', 'etab_email', 'etab_siren']:
                param = Parametre.query.filter_by(cle=key).first()
                value = request.form.get(key, '')
                if param:
                    param.valeur = value
                else:
                    param = Parametre(cle=key, valeur=value)
                    db.session.add(param)
            db.session.commit()
            flash('Informations de l\'établissement enregistrées', 'success')
            return redirect(url_for('settings.admin'))
        
        # === SÉCURITÉ ===
        if action == 'save_security':
            security_settings = {
                'max_login_attempts': request.form.get('max_login_attempts'),
                'lockout_duration': request.form.get('lockout_duration')
            }
            for key, value in security_settings.items():
                param = Parametre.query.filter_by(cle=key).first()
                if param:
                    param.valeur = value
                else:
                    param = Parametre(cle=key, valeur=value)
                    db.session.add(param)
            db.session.commit()
            flash('Configuration sécurité enregistrée', 'success')
            return redirect(url_for('settings.admin'))
        
        # Change password for current user
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            security_question = request.form.get('security_question')
            security_answer = request.form.get('security_answer')
            
            if not current_user.check_password(current_password):
                flash('Mot de passe actuel incorrect', 'error')
            elif new_password != confirm_password:
                flash('Les mots de passe ne correspondent pas', 'error')
            elif len(new_password) < 4:
                flash('Le mot de passe doit contenir au moins 4 caractères', 'error')
            else:
                current_user.set_password(new_password)
                if security_question:
                    if security_answer and security_question.lower() in security_answer.lower():
                        flash('La réponse ne peut pas contenir la question', 'error')
                        return redirect(url_for('settings.admin'))
                    current_user.security_question = security_question
                    current_user.security_answer = security_answer
                db.session.commit()
                Log.log(current_user, 'change_password', 'Mot de passe modifié (admin)', 'User', current_user.id)
                flash('Mot de passe modifié avec succès', 'success')
            return redirect(url_for('settings.admin'))
        
        if action == 'add_user':
            nom = request.form.get('nom')
            prenom = request.form.get('prenom')
            login = request.form.get('login')
            password = request.form.get('password')
            role = request.form.get('role')
            if nom and prenom and login and password and role:
                if User.query.filter_by(login=login).first():
                    flash('Login déjà utilisé', 'error')
                else:
                    user = User(nom=nom, prenom=prenom, login=login, role=role)
                    user.set_password(password)
                    db.session.add(user)
                    db.session.commit()
                    Log.log(current_user, 'create_user', f'Utilisateur créé: {prenom} {nom} ({role})', 'User', user.id)
                    db.session.commit()
                    flash('Utilisateur créé: ' + login, 'success')
        
        elif action == 'save_permissions':
            new_perms = {}
            for role in ['ddfpt', 'magasinier', 'enseignant', 'eleve']:
                perms = request.form.getlist(f'perms_{role}')
                new_perms[role] = perms
            
            param = Parametre.query.filter_by(cle='permissions').first()
            if param:
                param.valeur = json.dumps(new_perms)
            else:
                param = Parametre(cle='permissions', valeur=json.dumps(new_perms))
                db.session.add(param)
            db.session.commit()
            flash('Permissions enregistrées', 'success')
            return redirect(url_for('settings.admin'))
        
        elif action == 'toggle_user':
            user = User.query.get(request.form.get('id'))
            if user and user.id != current_user.id:
                user.actif = not user.actif
                db.session.commit()
                flash(f'Utilisateur {"activé" if user.actif else "désactivé"}', 'success')
        
        elif action == 'delete_user':
            user = User.query.get(request.form.get('id'))
            if user and user.id != current_user.id:
                db.session.delete(user)
                db.session.commit()
                flash('Utilisateur supprimé', 'success')
        
        elif action == 'edit_fourniture':
            f = Fourniture.query.get(request.form.get('id'))
            if f:
                f.nom = request.form.get('nom')
                f.prix_unitaire = request.form.get('prix_unitaire') or 0
                db.session.commit()
                flash('Fourniture modifiée', 'success')
        
        elif action == 'delete_fourniture':
            f = Fourniture.query.get(request.form.get('id'))
            if f:
                db.session.delete(f)
                db.session.commit()
                flash('Fourniture supprimée', 'success')
        
        elif action == 'add_enseignant':
            nom = request.form.get('nom')
            prenom = request.form.get('prenom')
            if nom and prenom:
                ens = Enseignant(nom=nom, prenom=prenom)
                db.session.add(ens)
                db.session.commit()
                flash('Enseignant ajouté', 'success')
        
        elif action == 'toggle_enseignant':
            ens = Enseignant.query.get(request.form.get('id'))
            if ens:
                ens.actif = not ens.actif
                db.session.commit()
                flash(f'Enseignant {"activé" if ens.actif else "désactivé"}', 'success')
        
        elif action == 'delete_enseignant':
            ens = Enseignant.query.get(request.form.get('id'))
            if ens:
                db.session.delete(ens)
                db.session.commit()
                flash('Enseignant supprimé', 'success')
        
        elif action == 'add_classe':
            nom = request.form.get('nom')
            if nom:
                cls = Classe(nom=nom)
                db.session.add(cls)
                db.session.commit()
                flash('Classe ajoutée', 'success')
        
        elif action == 'toggle_classe':
            cls = Classe.query.get(request.form.get('id'))
            if cls:
                cls.actif = not cls.actif
                db.session.commit()
                flash(f'Classe {"activée" if cls.actif else "désactivée"}', 'success')
        
        elif action == 'delete_classe':
            cls = Classe.query.get(request.form.get('id'))
            if cls:
                db.session.delete(cls)
                flash('Classe supprimée', 'success')
        
        elif action == 'delete_client':
            client = Client.query.get(request.form.get('id'))
            if client:
                db.session.delete(client)
                flash('Client supprimé', 'success')
        
        elif action == 'delete_vehicule':
            vehicule = Vehicule.query.get(request.form.get('id'))
            if vehicule:
                db.session.delete(vehicule)
                flash('Véhicule supprimé', 'success')
        
        elif action == 'delete_or':
            or_obj = OrdreReparation.query.get(request.form.get('id'))
            if or_obj:
                db.session.delete(or_obj)
                flash('Ordre de réparation supprimé', 'success')
        
        elif action == 'toggle_facturation':
            or_obj = OrdreReparation.query.get(request.form.get('id'))
            if or_obj:
                or_obj.pas_de_facturation = not or_obj.pas_de_facturation
                flash(f'Facturation {"désactivée" if or_obj.pas_de_facturation else "activée"}', 'success')
        
        db.session.commit()
        return redirect(url_for('settings.admin'))
    
    users = User.query.all()
    clients = Client.query.all()
    vehicules = Vehicule.query.all()
    ordres = OrdreReparation.query.all()
    
    smtp_config = {}
    for key in ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from']:
        param = Parametre.query.filter_by(cle=key).first()
        smtp_config[key] = param.valeur if param else ''
    
    security_config = {
        'max_login_attempts': Parametre.get('max_login_attempts', '3'),
        'lockout_duration': Parametre.get('lockout_duration', '15')
    }
    
    enseignants = User.query.filter_by(role='enseignant').order_by(User.nom).all()
    classes = Classe.query.order_by(Classe.nom).all()
    
    # Logs data for logs tab
    logs = []
    if tab == 'logs':
        logs = Log.query.order_by(Log.created_at.desc()).limit(200).all()
    
    # Permissions data
    permissions_data = None
    if tab == 'permissions':
        # Permissions disabled - using hardcoded defaults in models.py
        pass
    
    # Checklist data
    from app.models import ChecklistItem
    checklist_items = ChecklistItem.query.order_by(ChecklistItem.ordre).all()
    
    # Fournitures data
    fournitures = Fourniture.query.order_by(Fourniture.nom).all()
    
    return render_template('settings/admin.html', 
                          users=users, clients=clients, 
                          vehicules=vehicules, ordres=ordres,
                          smtp_config=smtp_config,
                          enseignants=enseignants,
                          classes=classes,
                          logs=logs,
                          permissions_data=permissions_data,
                          checklist_items=checklist_items,
                          fournitures=fournitures,
                          etab_nom=Parametre.get('etab_nom', ''),
                          etab_adresse=Parametre.get('etab_adresse', ''),
                          etab_tel=Parametre.get('etab_tel', ''),
                          etab_email=Parametre.get('etab_email', ''),
                          etab_siren=Parametre.get('etab_siren', ''),
                          security_config=security_config)

@settings_bp.route('/permissions', methods=['GET', 'POST'])
@login_required
def permissions():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    # Default permissions
    default_perms = {
        'ddfpt': ['create_or', 'edit_or', 'delete_or', 'facturer', 'see_stats', 'manage_settings', 'manage_users', 'manage_clients', 'manage_vehicules'],
        'magasinier': ['facturer', 'manage_settings'],
        'enseignant': ['create_or', 'edit_or', 'manage_clients', 'manage_vehicules'],
        'eleve': ['edit_intervention']
    }
    
    # Load from DB or use defaults
    perms_json = Parametre.get('permissions', json.dumps(default_perms))
    try:
        permissions = json.loads(perms_json)
    except:
        permissions = default_perms
    
    if request.method == 'POST':
        # Update permissions from form
        new_perms = {}
        for role in ['ddfpt', 'magasinier', 'enseignant', 'eleve']:
            perms = request.form.getlist(f'perms_{role}')
            new_perms[role] = perms
        Parametre.set('permissions', json.dumps(new_perms))
        permissions = new_perms
        flash('Permissions enregistrées', 'success')
    
    roles_list = [
        ('ddfpt', 'DDFPT (Responsable)'),
        ('magasinier', 'Magasinier'),
        ('enseignant', 'Enseignant'),
        ('eleve', 'Élève')
    ]
    
    all_perms = [
        ('create_or', 'Créer des OR'),
        ('edit_or', 'Modifier les OR'),
        ('delete_or', 'Supprimer des OR'),
        ('facturer', 'Créer des factures'),
        ('see_stats', 'Voir les statistiques'),
        ('manage_settings', 'Gérer les paramètres'),
        ('manage_users', 'Gérer les utilisateurs'),
        ('manage_clients', 'Gérer les clients'),
        ('manage_vehicules', 'Gérer les véhicules'),
        ('edit_intervention', 'Saisir des interventions')
    ]
    
    return render_template('settings/permissions.html', 
                          permissions=permissions, 
                          roles_list=roles_list,
                          all_perms=all_perms)

@settings_bp.route('/admin/logs')
@login_required
def logs():
    if current_user.role != 'ddfpt':
        flash('Accès réservé au DDFPT', 'error')
        return redirect(url_for('main.index'))
    
    from datetime import datetime, timedelta
    
    # Filters
    action_filter = request.args.get('action', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    user_id = request.args.get('user_id')
    
    query = Log.query
    
    if action_filter:
        query = query.filter(Log.action == action_filter)
    if user_id:
        query = query.filter(Log.user_id == int(user_id))
    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Log.created_at >= d)
        except: pass
    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Log.created_at <= d.replace(hour=23, minute=59))
        except: pass
    
    sort = request.args.get('sort', 'date_desc')
    if sort == 'date_desc':
        query = query.order_by(Log.created_at.desc())
    elif sort == 'date_asc':
        query = query.order_by(Log.created_at.asc())
    elif sort == 'user':
        query = query.order_by(Log.user_id)
    elif sort == 'action':
        query = query.order_by(Log.action)
    else:
        query = query.order_by(Log.created_at.desc())
    
    logs = query.limit(200).all()
    from app.models import User
    users = User.query.all()
    
    return render_template('settings/logs.html', logs=logs, users=users, 
                        action_filter=action_filter, user_id=user_id, 
                        date_from=date_from, date_to=date_to, sort=sort)

# === CHECKLIST ===
@settings_bp.route('/checklist/add', methods=['POST'])
@login_required
def checklist_add():
    if current_user.role not in ['ddfpt', 'enseignant']:
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    from app.models import ChecklistItem
    item = ChecklistItem(nom=request.form.get('nom'), description=request.form.get('description'))
    db.session.add(item)
    db.session.commit()
    flash('Point ajouté à la checklist', 'success')
    return redirect(url_for('settings.checklist'))

@settings_bp.route('/checklist/<int:id>/toggle')
@login_required
def checklist_toggle(id):
    if current_user.role not in ['ddfpt', 'enseignant']:
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    from app.models import ChecklistItem
    item = ChecklistItem.query.get_or_404(id)
    item.actif = not item.actif
    db.session.commit()
    flash(f'Point {"activé" if item.actif else "désactivé"}', 'success')
    return redirect(url_for('settings.checklist'))

@settings_bp.route('/checklist/<int:id>/delete', methods=['POST'])
@login_required
def checklist_delete(id):
    if current_user.role not in ['ddfpt', 'enseignant']:
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    from app.models import ChecklistItem
    item = ChecklistItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Point supprimé', 'success')
    return redirect(url_for('settings.checklist'))

@settings_bp.route('/checklist/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def checklist_edit(id):
    if current_user.role not in ['ddfpt', 'enseignant']:
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    from app.models import ChecklistItem
    item = ChecklistItem.query.get_or_404(id)
    
    if request.method == 'POST':
        item.nom = request.form.get('nom')
        item.description = request.form.get('description')
        db.session.commit()
        flash('Point modifié', 'success')
        return redirect(url_for('settings.checklist'))
    
    return render_template('settings/checklist_edit.html', item=item)