from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Log, Parametre
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

MAX_LOGIN_ATTEMPTS = 3

def get_max_attempts():
    param = Parametre.query.filter_by(cle='max_login_attempts').first()
    return int(param.valeur) if param else MAX_LOGIN_ATTEMPTS

def get_lockout_duration():
    param = Parametre.query.filter_by(cle='lockout_duration').first()
    return int(param.valeur) if param else 15

def is_account_locked(user):
    if not user or not user.locked_until:
        return False
    if user.locked_until > datetime.utcnow():
        return True
    user.locked_until = None
    user.failed_attempts = 0
    db.session.commit()
    return False

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        login_input = request.form.get('login')
        password = request.form.get('password')

        user = User.query.filter(
            (User.login == login_input) | 
            ((User.email != None) & (User.email == login_input))
        ).first()

        max_attempts = get_max_attempts()
        lockout_duration = get_lockout_duration()
        
        if user and is_account_locked(user):
            remaining = (user.locked_until - datetime.utcnow()).seconds // 60
            flash(f'Compte verrouillé. Réessayez dans {remaining} minute(s)', 'error')
            return render_template('auth/login.html')

        if user and user.check_password(password) and user.actif:
            if user.failed_attempts:
                user.failed_attempts = 0
                user.locked_until = None
                db.session.commit()
            login_user(user)
            Log.log(user, 'login', f'Connexion depuis {request.remote_addr}')
            flash('Connexion réussie', 'success')
            
            if user.must_change_password:
                flash('Vous devez changer votre mot de passe', 'warning')
                return redirect(url_for('settings.mon_compte'))
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            if user and user.actif:
                user.failed_attempts = (user.failed_attempts or 0) + 1
                if user.failed_attempts >= max_attempts:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_duration)
                    db.session.commit()
                    flash(f'Trop de tentatives. Compte verrouillé {lockout_duration} minutes', 'error')
                else:
                    db.session.commit()
                    flash(f'Identifiants invalides. Tentative {user.failed_attempts}/{max_attempts}', 'error')
            else:
                Log.log(None, 'login_failed', f'Essai de connexion: {login_input} depuis {request.remote_addr}')
                flash('Identifiants invalides', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        action = request.form.get('action')
        
        user = None
        
        if action == 'reset_password':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if not user:
                flash('Erreur. Veuillez recommencer.', 'error')
                return render_template('auth/forgot_password.html')
            
            if request.form.get('answer') and user.security_answer:
                if request.form.get('answer').lower() == user.security_answer.lower():
                    new_password = request.form.get('new_password')
                    confirm = request.form.get('confirm_password')
                    
                    if new_password != confirm:
                        flash('Les mots de passe ne correspondent pas', 'error')
                        return render_template('auth/forgot_password.html', user_id=user.id, step='answer', user=user)
                    
                    if len(new_password) < 4:
                        flash('Le mot de passe doit contenir au moins 4 caractères', 'error')
                        return render_template('auth/forgot_password.html', user_id=user.id, step='answer', user=user)
                    
                    user.set_password(new_password)
                    user.failed_attempts = 0
                    user.locked_until = None
                    db.session.commit()
                    flash('Mot de passe réinitialisé. Vous pouvez vous connecter.', 'success')
                    return redirect(url_for('auth.login'))
                else:
                    flash('Réponse incorrecte', 'error')
                    return render_template('auth/forgot_password.html', user_id=user.id, step='answer', user=user)
            else:
                flash('Erreur', 'error')
                return render_template('auth/forgot_password.html', user_id=user.id, step='answer', user=user)
        
        login_input = request.form.get('login') or request.form.get('email')
        
        if login_input:
            user = User.query.filter(
                (User.login == login_input) | 
                ((User.email != None) & (User.email == login_input))
            ).first()
        
        if not user:
            flash('Utilisateur non trouvé', 'error')
            return render_template('auth/forgot_password.html')
        
        if action == 'check_question':
            if not user.security_question:
                flash('Aucune question de sécurité définie. Contacter l\'administrateur.', 'error')
                return render_template('auth/forgot_password.html')
            
            return render_template('auth/forgot_password.html', user_id=user.id, step='answer', user=user)
    
    return render_template('auth/forgot_password.html')

@auth_bp.route('/logout')
@login_required
def logout():
    Log.log(current_user, 'logout', f'Déconnexion')
    logout_user()
    flash('Déconnexion réussie', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/setup')
def setup():
    if User.query.count() > 0:
        return redirect(url_for('auth.login'))

    user = User(
        nom='Admin',
        prenom='DDFPT',
        login='admin',
        role='ddfpt'
    )
    user.set_password('admin123')
    db.session.add(user)
    db.session.commit()

    flash('Compte admin créé (login: admin, mdp: admin123)', 'success')
    return redirect(url_for('auth.login'))