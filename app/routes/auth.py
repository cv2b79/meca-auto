from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Log, Parametre
from datetime import datetime, timedelta
import time

auth_bp = Blueprint('auth', __name__)

MAX_LOGIN_ATTEMPTS = 3
MIN_PASSWORD_LEN = 8
MAX_RESET_ATTEMPTS = 3

# IP rate limiting: {ip: [timestamp, ...]}
_ip_login_attempts: dict = {}

def _is_ip_rate_limited(ip: str, window: int = 300, max_fail: int = 15) -> bool:
    now = time.time()
    attempts = [t for t in _ip_login_attempts.get(ip, []) if now - t < window]
    _ip_login_attempts[ip] = attempts
    if len(attempts) >= max_fail:
        return True
    attempts.append(now)
    _ip_login_attempts[ip] = attempts
    return False

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
        # M3: IP rate limit (15 failures / 5 min)
        ip = request.remote_addr
        if _is_ip_rate_limited(ip):
            flash('Trop de tentatives depuis cette adresse. Réessayez dans quelques minutes.', 'error')
            return render_template('auth/login.html')

        # Sanitize inputs (M1 null byte)
        login_input = (request.form.get('login') or '').replace('\x00', '').strip()[:128]
        password = request.form.get('password') or ''

        user = User.query.filter(
            (User.login == login_input) |
            ((User.email != None) & (User.email == login_input))
        ).first()

        max_attempts = get_max_attempts()
        lockout_duration = get_lockout_duration()

        if user and is_account_locked(user):
            remaining = max(0, (user.locked_until - datetime.utcnow()).seconds // 60)
            flash(f'Compte verrouillé. Réessayez dans {remaining} minute(s)', 'error')
            return render_template('auth/login.html')

        if user and user.check_password(password) and user.actif:
            if user.failed_attempts:
                user.failed_attempts = 0
                user.locked_until = None
                db.session.commit()
            login_user(user)
            Log.log(user, 'login', f'Connexion depuis {ip}')
            flash('Connexion réussie', 'success')

            if user.must_change_password:
                flash('Vous devez changer votre mot de passe', 'warning')
                return redirect(url_for('settings.mon_compte'))

            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            # M2: message identique qu'un compte existe ou non
            if user and user.actif:
                user.failed_attempts = (user.failed_attempts or 0) + 1
                if user.failed_attempts >= max_attempts:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_duration)
                    db.session.commit()
                    flash(f'Trop de tentatives. Compte verrouillé {lockout_duration} minutes', 'error')
                else:
                    db.session.commit()
                    flash('Identifiants invalides', 'error')
            else:
                Log.log(None, 'login_failed', f'Essai: {login_input[:32]} depuis {ip}')
                flash('Identifiants invalides', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'reset_password':
            # M1+M2: user_id depuis la session (pas le form)
            user_id = session.get('reset_user_id')
            if not user_id:
                flash('Session expirée. Veuillez recommencer.', 'error')
                return redirect(url_for('auth.forgot_password'))

            user = User.query.get(user_id)
            if not user:
                session.pop('reset_user_id', None)
                session.pop('reset_attempts', None)
                flash('Erreur. Veuillez recommencer.', 'error')
                return redirect(url_for('auth.forgot_password'))

            # M1: compteur de tentatives de réponse
            reset_attempts = session.get('reset_attempts', 0)
            if reset_attempts >= MAX_RESET_ATTEMPTS:
                session.pop('reset_user_id', None)
                session.pop('reset_attempts', None)
                Log.log(None, 'reset_brute', f'Trop de tentatives reset pour user {user_id}')
                flash('Trop de tentatives incorrectes. Veuillez recommencer depuis le début.', 'error')
                return redirect(url_for('auth.forgot_password'))

            answer = (request.form.get('answer') or '').strip()
            if answer and user.security_answer:
                if answer.lower() == user.security_answer.lower():
                    new_password = request.form.get('new_password') or ''
                    confirm = request.form.get('confirm_password') or ''

                    if new_password != confirm:
                        flash('Les mots de passe ne correspondent pas', 'error')
                        return render_template('auth/forgot_password.html',
                                               step='answer', question=user.security_question)

                    # M1: validation longueur côté serveur
                    if len(new_password) < MIN_PASSWORD_LEN:
                        flash(f'Le mot de passe doit contenir au moins {MIN_PASSWORD_LEN} caractères', 'error')
                        return render_template('auth/forgot_password.html',
                                               step='answer', question=user.security_question)

                    user.set_password(new_password)
                    user.failed_attempts = 0
                    user.locked_until = None
                    db.session.commit()
                    session.pop('reset_user_id', None)
                    session.pop('reset_attempts', None)
                    Log.log(user, 'reset_password_self', 'Réinitialisation via question de sécurité')
                    flash('Mot de passe réinitialisé. Vous pouvez vous connecter.', 'success')
                    return redirect(url_for('auth.login'))
                else:
                    session['reset_attempts'] = reset_attempts + 1
                    remaining = MAX_RESET_ATTEMPTS - session['reset_attempts']
                    if remaining > 0:
                        flash(f'Réponse incorrecte. Il vous reste {remaining} tentative(s).', 'error')
                    else:
                        flash('Réponse incorrecte.', 'error')
                    return render_template('auth/forgot_password.html',
                                           step='answer', question=user.security_question)
            else:
                flash('Réponse manquante', 'error')
                return render_template('auth/forgot_password.html',
                                       step='answer', question=user.security_question)

        # action == 'check_question'
        login_input = (request.form.get('login') or request.form.get('email') or '').strip()

        if login_input:
            user = User.query.filter(
                (User.login == login_input) |
                ((User.email != None) & (User.email == login_input))
            ).first()
        else:
            user = None

        # M2: réponse générique — ne pas révéler si le compte existe
        if not user or not user.security_question:
            flash('Si ce compte existe et dispose d\'une question de sécurité, répondez ci-dessous.', 'info')
            return render_template('auth/forgot_password.html')

        # Stocker user_id en session (M2: pas dans le form)
        session['reset_user_id'] = user.id
        session['reset_attempts'] = 0
        return render_template('auth/forgot_password.html', step='answer', question=user.security_question)

    # GET — réinitialiser la session de reset
    session.pop('reset_user_id', None)
    session.pop('reset_attempts', None)
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
        role='ddfpt',
        must_change_password=True
    )
    user.set_password('admin123')
    db.session.add(user)
    db.session.commit()

    flash('Compte admin créé (login: admin, mdp: admin123)', 'success')
    return redirect(url_for('auth.login'))