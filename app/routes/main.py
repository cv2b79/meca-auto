from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import OrdreReparation, Client, Vehicule, RendezVous, EleveIntervention
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    from app import db
    
    base_query = OrdreReparation.query
    
    if current_user.role == 'eleve':
        from app.models import EleveIntervention
        base_query = base_query.filter(
            (OrdreReparation.created_by == current_user.id) |
            (OrdreReparation.id.in_(
                db.session.query(EleveIntervention.or_id).filter_by(eleve_id=current_user.id)
            ))
        )
    
    ordres_atelier = []
    for or_obj in base_query.all():
        if or_obj.statut in ['ouvert', 'en_cours', 'termine']:
            ordres_atelier.append(or_obj)
    
    vehicules_dict = {}
    for o in ordres_atelier:
        v = o.vehicule
        if v.id not in vehicules_dict:
            vehicules_dict[v.id] = v
    
    vehicules_atelier = list(vehicules_dict.values())
    
    # Get this week's RDVs (from Monday to Sunday)
    today = datetime.now()
    # 7-day sliding window (last 7 days + next 7 days)
    start_sliding = today - timedelta(days=7)
    end_sliding = today + timedelta(days=7)
    
    rdv_7_jours = RendezVous.query.filter(
        RendezVous.date_heure >= start_sliding,
        RendezVous.date_heure <= end_sliding,
        RendezVous.statut != 'annule'
    ).order_by(RendezVous.date_heure).all()
    
    # Today's RDVs
    rdv_aujourdhui = RendezVous.query.filter(
        RendezVous.date_heure >= today.replace(hour=0, minute=0),
        RendezVous.date_heure <= today.replace(hour=23, minute=59),
        RendezVous.statut != 'annule'
    ).order_by(RendezVous.date_heure).all()
    
    # Month stats
    start_month = today.replace(day=1, hour=0, minute=0)
    if current_user.role == 'eleve':
        or_mois = base_query.filter(OrdreReparation.created_at >= start_month).count()
        recent_ors = base_query.order_by(OrdreReparation.created_at.desc()).limit(5).all()
    else:
        or_mois = OrdreReparation.query.filter(OrdreReparation.created_at >= start_month).count()
        recent_ors = OrdreReparation.query.order_by(OrdreReparation.created_at.desc()).limit(5).all()
    
    # Alertes
    alertes = []
    
    # OR en attente de pièces
    or_attente_pieces = OrdreReparation.query.filter_by(attente_pieces=True, statut='en_cours').all()
    for or_obj in or_attente_pieces:
        jours_attente = (today - or_obj.date_attente_pieces).days if or_obj.date_attente_pieces else 0
        alertes.append({
            'type': 'attente_pieces',
            'niveau': 'warning' if jours_attente < 3 else 'danger',
            'message': f"Attente pièces depuis {jours_attente} jour(s)",
            'or': or_obj
        })
    
    # OR en cours depuis plus de 5 jours
    for or_obj in ordres_atelier:
        jours_encours = (today - or_obj.created_at).days
        if jours_encours > 5:
            alertes.append({
                'type': 'duree',
                'niveau': 'warning' if jours_encours < 10 else 'danger',
                'message': f"En cours depuis {jours_encours} jours",
                'or': or_obj
            })
    
    stats = {
        'or_ouvert': OrdreReparation.query.filter_by(statut='ouvert').count(),
        'or_encours': OrdreReparation.query.filter_by(statut='en_cours').count(),
        'or_termine': OrdreReparation.query.filter_by(statut='termine').count(),
        'or_cloture': OrdreReparation.query.filter_by(statut='cloture').count(),
        'vehicules_atelier': vehicules_atelier,
        'ordres_actifs': ordres_atelier,
        'rdv_7_jours': rdv_7_jours,
        'rdv_aujourdhui': rdv_aujourdhui,
        'or_mois': or_mois,
        'recent_ors': recent_ors,
        'alertes': alertes
    }
    return render_template('main/index.html', stats=stats, current_date=datetime.now())

@main_bp.route('/mes-interventions')
@login_required
def mes_interventions():
    if current_user.role != 'eleve':
        flash('Accès réservé aux élèves', 'error')
        return redirect(url_for('main.index'))
    
    interventions = EleveIntervention.query.filter_by(eleve_id=current_user.id).order_by(EleveIntervention.created_at.desc()).all()
    
    total_heures = sum(float(i.heures or 0) for i in interventions)
    total_fournitures = 0
    for i in interventions:
        if i.fourniture_id and i.quantite:
            total_fournitures += float(i.fourniture.prix_unitaire or 0) * i.quantite
    
    return render_template('main/mes_interventions.html', 
                          interventions=interventions, 
                          total_heures=total_heures,
                          total_fournitures=total_fournitures)