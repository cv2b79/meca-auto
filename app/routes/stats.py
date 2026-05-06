from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import OrdreReparation, Client, Vehicule, EleveIntervention, Facture, User
from sqlalchemy import func
from datetime import datetime, timedelta
import calendar

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/')
@login_required
def index():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        from flask import redirect, url_for
        return redirect(url_for('main.index'))

    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', type=int)

    ors_query = OrdreReparation.query
    if year:
        ors_query = ors_query.filter(func.extract('year', OrdreReparation.created_at) == year)
    if month:
        ors_query = ors_query.filter(func.extract('month', OrdreReparation.created_at) == month)

    ors = ors_query.all()

    or_by_status = {
        'ouvert': sum(1 for o in ors if o.statut == 'ouvert'),
        'en_cours': sum(1 for o in ors if o.statut == 'en_cours'),
        'termine': sum(1 for o in ors if o.statut == 'termine'),
        'cloture': sum(1 for o in ors if o.statut == 'cloture')
    }

    or_by_month = {}
    for o in ors:
        if o.created_at:
            m = o.created_at.month
            or_by_month[m] = or_by_month.get(m, 0) + 1

    total_ca = sum(float(o.montant or 0) for o in ors if o.statut == 'cloture')
    
    # Stats supplémentaires
    total_ors_count = len(ors)
    taux_cloture = (or_by_status['cloture'] / total_ors_count * 100) if total_ors_count > 0 else 0
    ca_moyen = total_ca / or_by_status['cloture'] if or_by_status['cloture'] > 0 else 0
    
    or_without_invoice = sum(1 for o in ors if o.pas_de_facturation)
    
    # Comparaison année précédente
    prev_year = year - 1
    ors_prev = OrdreReparation.query.filter(func.extract('year', OrdreReparation.created_at) == prev_year).all()
    ors_prev_count = len(ors_prev)
    ors_prev_clotures = sum(1 for o in ors_prev if o.statut == 'cloture')
    ca_prev = sum(float(o.montant or 0) for o in ors_prev if o.statut == 'cloture')
    
    evolution_or = ((total_ors_count - ors_prev_count) / ors_prev_count * 100) if ors_prev_count > 0 else 0
    evolution_ca = ((total_ca - ca_prev) / ca_prev * 100) if ca_prev > 0 else 0
    
    or_by_teacher = {}
    for o in ors:
        if o.created_by_user:
            key = f"{o.created_by_user.prenom} {o.created_by_user.nom}"
            if key not in or_by_teacher:
                or_by_teacher[key] = {'count': 0, 'ca': 0}
            or_by_teacher[key]['count'] += 1
            if o.statut == 'cloture':
                or_by_teacher[key]['ca'] += float(o.montant or 0)
    
    or_by_class = {}
    for o in ors:
        if o.classe_nom:
            key = o.classe_nom
            if key not in or_by_class:
                or_by_class[key] = {'count': 0, 'ca': 0}
            or_by_class[key]['count'] += 1
            if o.statut == 'cloture':
                or_by_class[key]['ca'] += float(o.montant or 0)

    forfaits = sum(1 for o in ors if o.mode_tarif == 'forfait')
    horaire = sum(1 for o in ors if o.mode_tarif == 'horaire')

    interventions = EleveIntervention.query.join(User).all()
    eleve_stats = {}
    for i in interventions:
        key = f"{i.eleve.nom} {i.eleve.prenom}"
        if key not in eleve_stats:
            eleve_stats[key] = {'count': 0, 'heures': 0}
        eleve_stats[key]['count'] += 1
        eleve_stats[key]['heures'] += float(i.heures or 0)

    vehicules_brand = {}
    for v in Vehicule.query.all():
        if v.marque:
            vehicules_brand[v.marque] = vehicules_brand.get(v.marque, 0) + 1

    clients_count = Client.query.count()
    vehicules_count = Vehicule.query.count()
    top_clients = []
    for c in Client.query.all():
        or_count = c.vehicules.join(OrdreReparation).count()
        if or_count > 0:
            top_clients.append({'nom': f"{c.prenom} {c.nom}", 'count': or_count})
    top_clients.sort(key=lambda x: x['count'], reverse=True)
    top_clients = top_clients[:5]
    
    top_vehicules = []
    for v in Vehicule.query.all():
        or_count = v.ordres_reparation.count()
        if or_count > 0:
            top_vehicules.append({'immatriculation': v.immatriculation, 'count': or_count})
    top_vehicules.sort(key=lambda x: x['count'], reverse=True)
    top_vehicules = top_vehicules[:5]

    return render_template('stats/index.html',
        or_by_status=or_by_status,
        or_by_month=or_by_month,
        total_ca=total_ca,
        forfaits=forfaits,
        horaire=horaire,
        eleve_stats=eleve_stats,
        vehicules_brand=vehicules_brand,
        clients_count=clients_count,
        vehicules_count=vehicules_count,
        top_clients=top_clients,
        top_vehicules=top_vehicules,
        or_by_teacher=or_by_teacher,
        or_by_class=or_by_class,
        year=year,
        month=month,
        total_ors=len(ors),
        datetime=datetime,
        taux_cloture=taux_cloture,
        ca_moyen=ca_moyen,
        or_without_invoice=or_without_invoice,
        evolution_or=evolution_or,
        evolution_ca=evolution_ca,
        prev_year=prev_year)

@stats_bp.route('/export')
@login_required
def export():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        from flask import redirect, url_for
        return redirect(url_for('main.index'))

    import csv
    import io
    from flask import make_response

    ors = OrdreReparation.query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['N°', 'Statut', 'Véhicule', 'Client', 'Montant', 'Date création'])

    for o in ors:
        writer.writerow([
            o.numero,
            o.statut,
            f"{o.vehicule.marque} {o.vehicule.modele} ({o.vehicule.immatriculation})",
            f"{o.client.prenom} {o.client.nom}",
            o.montant,
            o.created_at.strftime('%d/%m/%Y') if o.created_at else ''
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=export_OR_{datetime.now().year}.csv'

    return response