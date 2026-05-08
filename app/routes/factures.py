from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from app import db
from app.models import Facture, OrdreReparation, EleveIntervention, Log
from datetime import datetime
import io

factures_bp = Blueprint('factures', __name__)

@factures_bp.route('/')
@login_required
def list():
    year = request.args.get('year')
    query = Facture.query

    if year:
        query = query.filter(db.extract('year', Facture.emitted_at) == int(year))

    factures = query.order_by(Facture.emitted_at.desc()).all()
    return render_template('factures/list.html', factures=factures)

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
        return redirect(url_for('ordres.list'))

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

        flash(f'Facture {facture.numero} créée', 'success')
        return redirect(url_for('factures.view', id=facture.id))

    return render_template('factures/create.html', or_obj=or_obj)

@factures_bp.route('/<int:id>/view')
@login_required
def view_html(id):
    facture = Facture.query.get_or_404(id)
    or_obj = facture.ordre
    client = or_obj.client
    vehicule = or_obj.vehicule
    
    interventions = EleveIntervention.query.filter_by(or_id=or_obj.id).all()
    total_heures = sum(float(i.heures or 0) for i in interventions)
    
    from app.models import Parametre
    taux = Parametre.query.filter_by(cle='taux_horaire').first()
    taux_horaire = float(taux.valeur) if taux else 50.0
    
    surcharge_lines = []
    if or_obj.client_recup_pieces or or_obj.client_recup_fluides:
        from app.models import RecupSurcharge
        surcharges = RecupSurcharge.query.filter_by(actif=True).all()
        for s in surcharges:
            if 'pieces' in s.nom.lower() and or_obj.client_recup_pieces:
                surcharge_lines.append(s)
            if 'huile' in s.nom.lower() or 'fluide' in s.nom.lower():
                if or_obj.client_recup_fluides:
                    surcharge_lines.append(s)
    
    return render_template('factures/print.html', 
        facture=facture, 
        or_obj=or_obj, 
        client=client,
        vehicule=vehicule,
        interventions=interventions,
        total_heures=total_heures,
        taux_horaire=taux_horaire,
        surcharge_lines=surcharge_lines)

@factures_bp.route('/<int:id>/pdf')
@login_required
def pdf(id):
    try:
        from weasyprint import HTML
    except OSError:
        return redirect(url_for('factures.view_html', id=id))

    facture = Facture.query.get_or_404(id)
    or_obj = facture.ordre
    client = or_obj.client
    vehicule = or_obj.vehicule
    
    interventions = EleveIntervention.query.filter_by(or_id=or_obj.id).all()
    total_heures = sum(float(i.heures or 0) for i in interventions)
    
    from app.models import Parametre
    taux = Parametre.query.filter_by(cle='taux_horaire').first()
    taux_horaire = float(taux.valeur) if taux else 50.0
    
    surcharge_lines = []
    if or_obj.client_recup_pieces or or_obj.client_recup_fluides:
        from app.models import RecupSurcharge
        surcharges = RecupSurcharge.query.filter_by(actif=True).all()
        for s in surcharges:
            if 'pieces' in s.nom.lower() and or_obj.client_recup_pieces:
                surcharge_lines.append(s)
            if 'huile' in s.nom.lower() or 'fluide' in s.nom.lower():
                if or_obj.client_recup_fluides:
                    surcharge_lines.append(s)

    html = render_template('factures/pdf.html', 
        facture=facture, 
        or_obj=or_obj, 
        client=client,
        vehicule=vehicule,
        interventions=interventions,
        total_heures=total_heures,
        taux_horaire=taux_horaire,
        surcharge_lines=surcharge_lines)

    try:
        pdf = HTML(string=html).write_pdf()
    except Exception as e:
        flash(f'Erreur génération PDF: {str(e)}', 'error')
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
        return redirect(url_for('factures.list'))

    from flask import current_app
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    facture = Facture.query.get_or_404(id)
    or_obj = facture.ordre
    client = or_obj.client

    if not client.email:
        flash('Pas d\'email client', 'error')
        return redirect(url_for('factures.view', id=id))

    # Get SMTP config from database first, then fall back to config
    from app.models import Parametre
    def get_smtp_param(key, default=''):
        param = Parametre.query.filter_by(cle=key).first()
        return param.valeur if param else current_app.config.get(key.upper(), default)
    
    smtp_host = get_smtp_param('smtp_host')
    smtp_port = int(get_smtp_param('smtp_port', '587'))
    smtp_user = get_smtp_param('smtp_user')
    smtp_password = get_smtp_param('smtp_password')
    smtp_from = get_smtp_param('smtp_from', 'atelier@lycee.fr')

    if not smtp_host or not smtp_user:
        flash('SMTP non configuré', 'error')
        return redirect(url_for('factures.view', id=id))

    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = client.email
    msg['Subject'] = f'Facture {facture.numero} - Atelier'

    body = f"Bonjour {client.prenom} {client.nom},\n\nVeuillez trouver ci-joint votre facture {facture.numero}.\n\nMontant: {facture.montant}€\n\nCordialement,\nAtelier"
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        facture.send_by_email = True
        db.session.commit()
        Log.log(current_user, 'send_facture', f'Facture {facture.numero} envoyée à {client.email}', 'Facture', facture.id)
        flash('Facture envoyée par email', 'success')
    except Exception as e:
        flash(f'Erreur envoi email: {str(e)}', 'error')

    return redirect(url_for('factures.view', id=id))