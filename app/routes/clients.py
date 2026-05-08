from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import Client, Vehicule, Log
from datetime import datetime

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/')
@login_required
def list():
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'nom_asc')
    
    query = Client.query
    
    if search:
        query = query.filter(
            (Client.nom.like(f'%{search}%')) |
            (Client.prenom.like(f'%{search}%')) |
            (Client.telephone.like(f'%{search}%')) |
            (Client.email.like(f'%{search}%'))
        )
    
    if sort == 'nom_asc':
        query = query.order_by(Client.nom.asc())
    elif sort == 'nom_desc':
        query = query.order_by(Client.nom.desc())
    elif sort == 'prenom_asc':
        query = query.order_by(Client.prenom.asc())
    elif sort == 'recent':
        query = query.order_by(Client.created_at.desc())
    
    clients = query.all()
    return render_template('clients/list.html', clients=clients, search=search, sort=sort)

@clients_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_manage_clients():
        flash('Accès refusé', 'error')
        return redirect(url_for('clients.list'))
    if request.method == 'POST':
        client = Client(
            nom=request.form.get('nom'),
            prenom=request.form.get('prenom'),
            adresse=request.form.get('adresse'),
            telephone=request.form.get('telephone'),
            email=request.form.get('email')
        )
        db.session.add(client)
        db.session.commit()
        Log.log(current_user, 'create_client', f'Client créé: {client.nom} {client.prenom}', 'Client', client.id)
        db.session.commit()
        flash('Client créé', 'success')
        return redirect(url_for('clients.view', id=client.id))
    return render_template('clients/edit.html', client=None)

@clients_bp.route('/<int:id>')
@login_required
def view(id):
    client = Client.query.get_or_404(id)
    vehicules = client.vehicules.all()
    return render_template('clients/view.html', client=client, vehicules=vehicules)

@clients_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.can_manage_clients():
        flash('Accès refusé', 'error')
        return redirect(url_for('clients.list'))
    client = Client.query.get_or_404(id)
    if request.method == 'POST':
        client.nom = request.form.get('nom')
        client.prenom = request.form.get('prenom')
        client.adresse = request.form.get('adresse')
        client.telephone = request.form.get('telephone')
        client.email = request.form.get('email')
        client.updated_at = datetime.utcnow()
        db.session.commit()
        Log.log(current_user, 'edit_client', f'Client modifié: {client.nom} {client.prenom} (id: {client.id})', 'Client', client.id)
        flash('Client modifié', 'success')
        return redirect(url_for('clients.view', id=client.id))
    return render_template('clients/edit.html', client=client)

@clients_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.can_manage_clients():
        flash('Accès refusé', 'error')
        return redirect(url_for('clients.list'))
    client = Client.query.get_or_404(id)
    
    # Check for linked vehicles
    from app.models import Vehicule, OrdreReparation
    vehicules = Vehicule.query.filter_by(proprietaire_id=id).count()
    ors = OrdreReparation.query.filter_by(client_id=id).count()
    
    if vehicules > 0 or ors > 0:
        flash(f'Impossible de supprimer: {vehicules} véhicule(s) et {ors} OR(s) lié(s)', 'error')
        return redirect(url_for('clients.view', id=id))
    db.session.delete(client)
    db.session.commit()
    Log.log(current_user, 'delete_client', f'Client supprimé: {client.nom} {client.prenom} (id: {client.id})', 'Client', client.id)
    flash('Client supprimé', 'success')
    return redirect(url_for('clients.list'))