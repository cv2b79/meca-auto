from flask import Blueprint, render_template, request, make_response
from flask_login import login_required, current_user
from app.models import OrdreReparation, EleveIntervention, User
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
    
    return render_template('stats/index.html')

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