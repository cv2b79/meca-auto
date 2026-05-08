from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Vehicule, Client, VehiculeProprioHistory, OrdreReparation, Log
from datetime import datetime

vehicules_bp = Blueprint('vehicules', __name__)

@vehicules_bp.route('/')
@login_required
def list():
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'immat_asc')
    
    query = Vehicule.query
    
    if search:
        query = query.filter(
            (Vehicule.immatriculation.like(f'%{search}%')) |
            (Vehicule.marque.like(f'%{search}%')) |
            (Vehicule.modele.like(f'%{search}%')) |
            (Vehicule.vin.like(f'%{search}%'))
        )
    
    if sort == 'immat_asc':
        query = query.order_by(Vehicule.immatriculation.asc())
    elif sort == 'immat_desc':
        query = query.order_by(Vehicule.immatriculation.desc())
    elif sort == 'marque_asc':
        query = query.order_by(Vehicule.marque.asc())
    elif sort == 'recent':
        query = query.order_by(Vehicule.created_at.desc())
    
    vehicules = query.all()
    return render_template('vehicules/list.html', vehicules=vehicules, search=search, sort=sort)

@vehicules_bp.route('/search')
def search():
    q = request.args.get('q', '').upper().replace('-', '').replace(' ', '')
    if not q:
        return jsonify({'found': False})
    
    # Search in both stored format and without dashes
    from sqlalchemy import or_, func
    vehicule = Vehicule.query.filter(
        or_(
            func.replace(Vehicule.immatriculation, '-', '').like(f'%{q}%'),
            Vehicule.immatriculation.like(f'%{q}%')
        )
    ).first()
    if vehicule:
        return jsonify({
            'found': True,
            'vehicule': {
                'id': vehicule.id,
                'immatriculation': vehicule.immatriculation,
                'marque': vehicule.marque,
                'modele': vehicule.modele,
                'annee': vehicule.annee,
                'proprietaire': {
                    'id': vehicule.proprietaire.id,
                    'nom': vehicule.proprietaire.nom,
                    'prenom': vehicule.proprietaire.prenom,
                    'telephone': vehicule.proprietaire.telephone,
                    'email': vehicule.proprietaire.email
                } if vehicule.proprietaire else None
            }
        })
    return jsonify({'found': False})

@vehicules_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_manage_vehicules():
        flash('Accès refusé', 'error')
        return redirect(url_for('vehicules.list'))
    if request.method == 'POST':
        immat = request.form.get('immatriculation').upper()

        vehicule = Vehicule.query.filter_by(immatriculation=immat).first()
        if vehicule:
            flash('Véhicule déjà existant', 'info')
            return redirect(url_for('vehicules.edit', id=vehicule.id))

        proprietaire_id = request.form.get('proprietaire_id')
        if not proprietaire_id:
            client = Client(
                nom=request.form.get('proprio_nom'),
                prenom=request.form.get('proprio_prenom'),
                telephone=request.form.get('proprio_tel'),
                email=request.form.get('proprio_email')
            )
            db.session.add(client)
            db.session.flush()
            proprietaire_id = client.id

        vehicule = Vehicule(
            immatriculation=immat,
            marque=request.form.get('marque'),
            modele=request.form.get('modele'),
            annee=request.form.get('annee'),
            vin=request.form.get('vin'),
            couleur=request.form.get('couleur'),
            kilometrage=request.form.get('kilometrage'),
            proprietaire_id=proprietaire_id
        )
        db.session.add(vehicule)
        db.session.commit()
        Log.log(current_user, 'create_vehicule', f'Véhicule créé: {vehicule.immatriculation} - {vehicule.marque} {vehicule.modele}', 'Vehicule', vehicule.id)
        db.session.commit()
        flash('Véhicule créé', 'success')
        return redirect(url_for('vehicules.view', id=vehicule.id))
    return render_template('vehicules/edit.html', vehicule=None)

@vehicules_bp.route('/<int:id>')
@login_required
def view(id):
    vehicule = Vehicule.query.get_or_404(id)
    historiques = vehicule.historiques_proprio.order_by(VehiculeProprioHistory.date_debut.desc()).all()
    ors = vehicule.ordres_reparation.order_by(OrdreReparation.created_at.desc()).all()
    
    # Calculate totals
    total_interventions = 0
    total_heures = 0
    for o in ors:
        interventions = o.interventions_eleves.all()
        total_interventions += len(interventions)
        total_heures += sum(float(i.heures or 0) for i in interventions)
    
    return render_template('vehicules/view.html', vehicule=vehicule, historiques=historiques, ors=ors, total_interventions=total_interventions, total_heures=total_heures)

@vehicules_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.can_manage_vehicules():
        flash('Accès refusé', 'error')
        return redirect(url_for('vehicules.list'))
    
    vehicule = Vehicule.query.get_or_404(id)
    if request.method == 'POST':
        old_proprio_id = vehicule.proprietaire_id

        vehicule.immatriculation = request.form.get('immatriculation').upper()
        vehicule.marque = request.form.get('marque')
        vehicule.modele = request.form.get('modele')
        vehicule.annee = request.form.get('annee')
        vehicule.vin = request.form.get('vin')
        vehicule.couleur = request.form.get('couleur')
        vehicule.kilometrage = request.form.get('kilometrage')

        new_proprio_id = request.form.get('proprietaire_id')
        if new_proprio_id and int(new_proprio_id) != old_proprio_id:
            if old_proprio_id:
                histo = VehiculeProprioHistory.query.filter_by(
                    vehicule_id=vehicule.id, client_id=old_proprio_id, date_fin=None
                ).first()
                if histo:
                    histo.date_fin = datetime.utcnow()

            vehicule.proprietaire_id = new_proprio_id
            histo_new = VehiculeProprioHistory(
                vehicule_id=vehicule.id,
                client_id=new_proprio_id
            )
            db.session.add(histo_new)

        vehicule.updated_at = datetime.utcnow()
        db.session.commit()
        Log.log(current_user, 'edit_vehicule', f'Véhicule modifié: {vehicule.immatriculation} ({vehicule.id})', 'Vehicule', vehicule.id)
        flash('Véhicule modifié', 'success')
        return redirect(url_for('vehicules.view', id=vehicule.id))
    return render_template('vehicules/edit.html', vehicule=vehicule)