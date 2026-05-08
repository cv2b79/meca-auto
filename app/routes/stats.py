from flask import Blueprint, render_template, request, make_response, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import OrdreReparation, EleveIntervention, User, Client, Vehicule
from app import db
import csv
from io import StringIO
from datetime import datetime

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/')
@login_required
def index():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', type=int)
    
    # Base query
    query = OrdreReparation.query
    
    # Filter by year
    if year:
        query = query.filter(db.extract('year', OrdreReparation.created_at) == year)
    
    # Filter by month
    if month:
        query = query.filter(db.extract('month', OrdreReparation.created_at) == month)
    
    ordres = query.all()
    
    # Calculate stats
    total_ors = len(ordres)
    total_ca = sum(o.montant or 0 for o in ordres)
    or_clotures = len([o for o in ordres if o.statut == 'cloture'])
    taux_cloture = (or_clotures / total_ors * 100) if total_ors > 0 else 0
    ca_moyen = (total_ca / total_ors) if total_ors > 0 else 0
    
    # OR without invoice
    or_without_invoice = len([o for o in ordres if o.statut == 'cloture' and not o.facture])
    
    # Previous year stats
    prev_year = year - 1
    prev_ordres = OrdreReparation.query.filter(db.extract('year', OrdreReparation.created_at) == prev_year).all()
    prev_total = len(prev_ordres)
    prev_ca = sum(o.montant or 0 for o in prev_ordres)
    
    evolution_or = ((total_ors - prev_total) / prev_total * 100) if prev_total > 0 else 0
    evolution_ca = ((total_ca - prev_ca) / prev_ca * 100) if prev_ca > 0 else 0
    
    # Counts
    clients_count = Client.query.count()
    vehicules_count = Vehicule.query.count()
    
    # Status breakdown
    statuts = {
        'ouvert': len([o for o in ordres if o.statut == 'ouvert']),
        'en_cours': len([o for o in ordres if o.statut == 'en_cours']),
        'termine': len([o for o in ordres if o.statut == 'termine']),
        'cloture': len([o for o in ordres if o.statut == 'cloture'])
    }
    
    return render_template('stats/index.html',
                          total_ors=total_ors, total_ca=total_ca, taux_cloture=taux_cloture,
                          ca_moyen=ca_moyen, or_without_invoice=or_without_invoice,
                          evolution_or=evolution_or, evolution_ca=evolution_ca,
                          prev_year=prev_year, clients_count=clients_count,
                          vehicules_count=vehicules_count, or_by_status=statuts,
                          year=year, month=month)

@stats_bp.route('/export-ors')
@login_required
def export_ors():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    ordres = OrdreReparation.query.order_by(OrdreReparation.created_at.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Numéro', 'Statut', 'Véhicule', 'Client', 'Montant', 'Créé le', 'Clôturé le'])
    
    for o in ordres:
        writer.writerow([
            o.numero,
            o.statut,
            f"{o.vehicule.immatriculation} {o.vehicule.marque} {o.vehicule.modele}",
            f"{o.vehicule.proprietaire.prenom if o.vehicule.proprietaire else ''} {o.vehicule.proprietaire.nom if o.vehicule.proprietaire else ''}",
            str(o.montant) if o.montant else '',
            o.created_at.strftime('%d/%m/%Y') if o.created_at else '',
            o.date_cloture.strftime('%d/%m/%Y') if o.date_cloture else ''
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=ors_{datetime.now().strftime("%Y%m%d")}.csv'
    return response

@stats_bp.route('/export-interventions')
@login_required
def export_interventions():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    interventions = EleveIntervention.query.order_by(EleveIntervention.created_at.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'OR', 'Élève', 'Véhicule', 'Description', 'Heures', 'Fourniture', 'Quantité'])
    
    for i in interventions:
        writer.writerow([
            i.created_at.strftime('%d/%m/%Y') if i.created_at else '',
            i.ordre.numero if i.ordre else '',
            f"{i.eleve.prenom} {i.eleve.nom}" if i.eleve else '',
            f"{i.ordre.vehicule.immatriculation}" if i.orde and i.orde.vehicule else '',
            i.description or '',
            str(i.heures) if i.heures else '0',
            i.fourniture.nom if i.fourniture else '',
            str(i.quantite) if i.quantite else ''
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=interventions_{datetime.now().strftime("%Y%m%d")}.csv'
    return response