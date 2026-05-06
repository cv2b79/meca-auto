from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Log

auth_bp = Blueprint('auth', __name__)

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

        if user and user.check_password(password) and user.actif:
            login_user(user)
            Log.log(user, 'login', f'Connexion depuis {request.remote_addr}')
            flash('Connexion réussie', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            Log.log(None, 'login_failed', f'Essai de connexion: {login_input} depuis {request.remote_addr}')
            flash('Identifiants invalides', 'error')

    return render_template('auth/login.html')

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