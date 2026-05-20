from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from app import db
from app.models import Facture, OrdreReparation, EleveIntervention, Log
from datetime import datetime
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

factures_bp = Blueprint('factures', __name__)


def _build_facture_context(facture):
    """Construit le contexte commun pour les templates de facture (print + pdf)."""
    from app.models import Parametre, RecupSurcharge
    or_obj = facture.ordre
    client = or_obj.client
    vehicule = or_obj.vehicule

    interventions = EleveIntervention.query.filter_by(or_id=or_obj.id).all()
    total_heures = sum(float(i.heures or 0) for i in interventions)

    taux = Parametre.query.filter_by(cle='taux_horaire').first()
    taux_horaire = float(taux.valeur) if taux else 50.0

    # Lignes main-d'œuvre (sans fourniture)
    mo_lines = [i for i in interventions if not i.fourniture_id]

    # Lignes fournitures regroupées
    fournitures_map = {}
    for i in interventions:
        if i.fourniture_id and i.fourniture:
            key = i.fourniture_id
            if key not in fournitures_map:
                fournitures_map[key] = {
                    'nom': i.fourniture.nom,
                    'qte': 0,
                    'pu': float(i.fourniture.prix_unitaire or 0),
                    'total': 0.0,
                }
            fournitures_map[key]['qte'] += int(i.quantite or 1)
            fournitures_map[key]['total'] += float(i.fourniture.prix_unitaire or 0) * int(i.quantite or 1)
    fournitures_lines = list(fournitures_map.values())
    total_fournitures = sum(f['total'] for f in fournitures_lines)

    surcharge_lines = []
    if or_obj.client_recup_pieces or or_obj.client_recup_fluides:
        surcharges = RecupSurcharge.query.filter_by(actif=True).all()
        for s in surcharges:
            if 'pieces' in s.nom.lower() and or_obj.client_recup_pieces:
                surcharge_lines.append(s)
            if ('huile' in s.nom.lower() or 'fluide' in s.nom.lower()) and or_obj.client_recup_fluides:
                surcharge_lines.append(s)

    total_mo = total_heures * taux_horaire
    total_surcharge = float(or_obj.montant_surcharge or 0)
    total_ttc = total_mo + total_fournitures + total_surcharge

    return dict(
        facture=facture,
        or_obj=or_obj,
        client=client,
        vehicule=vehicule,
        interventions=interventions,
        mo_lines=mo_lines,
        total_heures=total_heures,
        taux_horaire=taux_horaire,
        fournitures_lines=fournitures_lines,
        total_fournitures=total_fournitures,
        surcharge_lines=surcharge_lines,
        total_surcharge=total_surcharge,
        total_mo=total_mo,
        total_ttc=total_ttc,
    )

@factures_bp.route('/')
@login_required
def liste():
    year = request.args.get('year', type=int)
    query = Facture.query

    if year:
        query = query.filter(db.extract('year', Facture.emitted_at) == year)

    factures = query.order_by(Facture.emitted_at.desc()).all()
    return render_template('factures/list.html', factures=factures, year=year)

@factures_bp.route('/<int:id>')
@login_required
def view(id):
    facture = Facture.query.get_or_404(id)
    return render_template('factures/view.html', facture=facture)

@factures_bp.route('/create/<int:or_id>', methods=['GET', 'POST'])
@login_required
def create(or_id):
    if not current_user.can_facturer():
        flash('Accès refusé', 'error')
        return redirect(url_for('ordres.liste'))

    or_obj = OrdreReparation.query.get_or_404(or_id)

    if or_obj.statut not in ['termine', 'cloture']:
        flash('L\'OR doit être terminé avant facturation', 'error')
        return redirect(url_for('ordres.view', id=or_id))

    if or_obj.facture:
        flash('Facture déjà existante', 'info')
        return redirect(url_for('factures.view', id=or_obj.facture.id))

    if request.method == 'POST':
        total = float(or_obj.montant or 0) + float(or_obj.montant_surcharge or 0)
        
        intervention_details = or_obj.interventions_eleves.all()
        
        total_fournitures = 0
        details = f"Travaux sur {or_obj.vehicule.immatriculation} - {or_obj.vehicule.marque} {or_obj.vehicule.modele}\n"
        details += f"Mode: {'Forfait' if or_obj.mode_tarif == 'forfait' else 'Taux horaire'}\n"
        details += f"Montant travaux: {or_obj.montant}€\n"
        
        if intervention_details:
            total_heures = sum(float(i.heures or 0) for i in intervention_details)
            details += f"Temps total: {total_heures} heures\n"
            
            for inter in intervention_details:
                if inter.fourniture_id:
                    qte = inter.quantite or 1
                    prix = float(inter.fourniture.prix_unitaire or 0)
                    total_fournitures += prix * qte
                    details += f"  - {inter.fourniture.nom} x{qte} = {prix * qte}€\n"
        
        if total_fournitures > 0:
            details += f"Fournitures: {total_fournitures}€\n"
            total += total_fournitures
        
        if or_obj.montant_surcharge > 0:
            details += f"Frais dépollution: {or_obj.montant_surcharge}€\n"
            if not or_obj.client_recup_pieces:
                details += "  - Pièces non récupérées\n"
            if not or_obj.client_recup_fluides:
                details += "  - Fluides non récupérés\n"
        
        details += f"\nTotal: {total}€"
        
        facture = Facture(
            numero=Facture.generer_numero(or_obj),
            or_id=or_id,
            montant=total,
            mode_tarif=or_obj.mode_tarif,
            details=details
        )

        or_obj.statut = 'cloture'
        or_obj.date_cloture = datetime.utcnow()
        or_obj.date_facture = datetime.utcnow()

        db.session.add(facture)
        db.session.commit()
        Log.log(current_user, 'create_facture', f'Facture {facture.numero} créée - OR {or_obj.numero}', 'Facture', facture.id)

        # Notification client en arrière-plan
        import threading
        from flask import current_app
        app = current_app._get_current_object()
        facture_id = facture.id
        def _send_facture_notif():
            with app.app_context():
                from app.models import Facture, OrdreReparation
                from app.routes.ordres import send_client_email
                _facture = Facture.query.get(facture_id)
                if _facture:
                    _or = _facture.ordre
                    _client = _or.client or (_or.vehicule.proprietaire if _or.vehicule else None)
                    send_client_email(_or, _client, _or.vehicule, 'facture', facture=_facture)
        threading.Thread(target=_send_facture_notif, daemon=True).start()

        flash(f'Facture {facture.numero} créée', 'success')
        return redirect(url_for('factures.view', id=facture.id))

    return render_template('factures/create.html', or_obj=or_obj)

@factures_bp.route('/<int:id>/view')
@login_required
def view_html(id):
    facture = Facture.query.get_or_404(id)
    ctx = _build_facture_context(facture)
    return render_template('factures/print.html', **ctx)

@factures_bp.route('/<int:id>/pdf')
@login_required
def pdf(id):
    try:
        import weasyprint
        from weasyprint import HTML
    except Exception as e:
        flash(f'WeasyPrint non installé: {str(e)}', 'error')
        return redirect(url_for('factures.view_html', id=id))

    facture = Facture.query.get_or_404(id)
    ctx = _build_facture_context(facture)
    html = render_template('factures/pdf.html', **ctx)

    try:
        from weasyprint import HTML
        base_url = request.host_url if request else None
        pdf = HTML(string=html, base_url=base_url).write_pdf()
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        flash(f'Erreur génération PDF: {str(e)}\n{error_detail[:500]}', 'error')
        return redirect(url_for('factures.view', id=id))

    return send_file(
        io.BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'facture_{facture.numero}.pdf'
    )

@factures_bp.route('/<int:id>/send', methods=['POST'])
@login_required
def send(id):
    if not current_user.can_facturer():
        flash('Accès refusé', 'error')
        return redirect(url_for('factures.liste'))

    from flask import current_app
    from app.models import Parametre

    facture = Facture.query.get_or_404(id)
    ctx = _build_facture_context(facture)
    client = ctx['client']

    # Vérifications préalables
    if not client or not client.email:
        flash("Pas d'adresse email pour ce client", 'error')
        return redirect(url_for('factures.view', id=id))

    def get_smtp_param(key, default=''):
        param = Parametre.query.filter_by(cle=key).first()
        return param.valeur if param else current_app.config.get(key.upper(), default)

    smtp_host = get_smtp_param('smtp_host')
    smtp_port_raw = get_smtp_param('smtp_port', '587')
    smtp_user = get_smtp_param('smtp_user')
    smtp_password = get_smtp_param('smtp_password')
    smtp_from = get_smtp_param('smtp_from', 'atelier@lycee.fr')

    if not smtp_host or not smtp_user:
        flash('SMTP non configuré (Administration → Email)', 'error')
        return redirect(url_for('factures.view', id=id))

    try:
        smtp_port = int(smtp_port_raw)
    except (ValueError, TypeError):
        smtp_port = 587

    # Génération du PDF
    html_content = render_template('factures/pdf.html', **ctx)
    pdf_bytes = None
    try:
        from weasyprint import HTML as WeasyHTML
        base_url = request.host_url
        pdf_bytes = WeasyHTML(string=html_content, base_url=base_url).write_pdf()
    except ImportError:
        flash('WeasyPrint non installé — email envoyé sans PDF joint', 'info')
    except Exception as e:
        flash(f'Erreur génération PDF : {str(e)}', 'error')
        return redirect(url_for('factures.view', id=id))

    # Construction de l'email
    prenom = client.prenom or ''
    nom = client.nom or ''
    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = client.email
    msg['Subject'] = f'Facture {facture.numero} - {ctx.get("or_obj") and ctx["or_obj"].vehicule and ctx["or_obj"].vehicule.marque or "Atelier"}'

    body = (
        f"Bonjour {prenom} {nom},\n\n"
        f"Veuillez trouver ci-joint votre facture N° {facture.numero}.\n\n"
        f"Montant total : {facture.montant} €\n\n"
        f"Cordialement,\n"
        f"{Parametre.get('etab_nom', 'Atelier MVA')}"
    )
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if pdf_bytes:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=facture_{facture.numero}.pdf')
        msg.attach(part)

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        facture.send_by_email = True
        db.session.commit()
        Log.log(current_user, 'send_facture',
                f'Facture {facture.numero} envoyée à {client.email}', 'Facture', facture.id)
        flash('Facture envoyée par email ✓', 'success')
    except Exception as e:
        flash(f'Erreur envoi email : {str(e)}', 'error')

    return redirect(url_for('factures.view', id=id))