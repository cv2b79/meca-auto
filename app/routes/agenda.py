from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import RendezVous, Client, Vehicule, OrdreReparation, Log
from datetime import datetime, timedelta as td
from calendar import monthrange, HTMLCalendar

agenda_bp = Blueprint('agenda', __name__)

@agenda_bp.route('/')
@login_required
def index():
    today = datetime.now()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    
    if month > 12:
        month = 1
        year += 1
    elif month < 1:
        month = 12
        year -= 1
    
    # Get first and last day of month
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
    
    # Get appointments for the month
    rdv_list = RendezVous.query.filter(
        RendezVous.date_heure >= first_day,
        RendezVous.date_heure <= last_day
    ).order_by(RendezVous.date_heure).all()
    
    # Create calendar
    cal = HTMLCalendar()
    today = datetime.now()
    
    return render_template('agenda/index.html', 
                          today=today,
                          timedelta=td, 
                          year=year, month=month, 
                          rdv_list=rdv_list,
                          first_day=first_day)

@agenda_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        vehicule_id = request.form.get('vehicule_id')
        titre = request.form.get('titre')
        description = request.form.get('description')
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        duree = request.form.get('duree', 60)
        
        try:
            date_heure = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except:
            flash('Date/heure invalide', 'error')
            return redirect(url_for('agenda.new'))
        
        rdv = RendezVous(
            client_id=client_id,
            vehicule_id=vehicule_id if vehicule_id else None,
            titre=titre,
            description=description,
            date_heure=date_heure,
            duree=duree,
            created_by=current_user.id
        )
        db.session.add(rdv)
        db.session.commit()
        Log.log(current_user, 'rdv_create', f'RDV créé: {titre} le {date_heure.strftime("%d/%m/%Y %H:%M")}', 'rdv', rdv.id)
        flash('Rendez-vous créé', 'success')
        return redirect(url_for('agenda.index'))
    
    clients = Client.query.order_by(Client.nom).all()
    vehicules = Vehicule.query.all()
    return render_template('agenda/new.html', clients=clients, vehicules=vehicules)

@agenda_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    rdv = RendezVous.query.get_or_404(id)
    
    if request.method == 'POST':
        rdv.titre = request.form.get('titre')
        rdv.description = request.form.get('description')
        rdv.statut = request.form.get('statut')
        
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        try:
            rdv.date_heure = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except:
            pass
        
        rdv.duree = request.form.get('duree', 60)
        db.session.commit()
        Log.log(current_user, 'rdv_edit', f'RDV modifié: {rdv.titre} ({rdv.id})', 'rdv', rdv.id)
        flash('Rendez-vous modifié', 'success')
        return redirect(url_for('agenda.index'))
    
    clients = Client.query.order_by(Client.nom).all()
    vehicules = Vehicule.query.all()
    
    # Get related ORs for this client
    related_ors = OrdreReparation.query.filter(
        OrdreReparation.client_id == rdv.client_id,
        OrdreReparation.statut.in_(['ouvert', 'en_cours', 'termine'])
    ).all()
    
    return render_template('agenda/edit.html', rdv=rdv, clients=clients, vehicules=vehicules, related_ors=related_ors)

@agenda_bp.route('/<int:id>/delete')
@login_required
def delete(id):
    rdv = RendezVous.query.get_or_404(id)
    rdv_title = rdv.titre
    rdv_id = rdv.id
    db.session.delete(rdv)
    db.session.commit()
    Log.log(current_user, 'rdv_delete', f'RDV supprimé: {rdv_title} (id: {rdv_id})', 'rdv', rdv_id)
    flash('Rendez-vous supprimé', 'success')
    return redirect(url_for('agenda.index'))