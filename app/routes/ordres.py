from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import OrdreReparation, Client, Vehicule, EleveIntervention, User, Forfait, Parametre, RecupSurcharge, Classe, RendezVous, Log, Fourniture, etat_lieu
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def send_notification_email(or_obj, client, vehicule):
    """Envoyer notification au magasinier + DDFPT lors de création d'OR avec PDF joint"""
    from app.models import etat_lieu
    from flask import render_template
    
    # Get emails - storekeeper + optional DDFPT
    emails_config = Parametre.get('email_notifications', '')
    ddfpt_email = Parametre.get('email_ddfpt_notif', '')
    
    emails = []
    if emails_config:
        emails.extend([e.strip() for e in emails_config.split(',') if e.strip()])
    if ddfpt_email:
        emails.extend([e.strip() for e in ddfpt_email.split(',') if e.strip()])
    
    emails = list(set(e for e in emails if e))
    print(f"[NOTIF EMAIL] Destinataires ({len(emails)}): {emails}")
    if not emails:
        print("[NOTIF EMAIL] Aucune adresse configurée, email annulé.")
        return
    
    def get_smtp_param(key, default=''):
        param = Parametre.query.filter_by(cle=key).first()
        return param.valeur if param else current_app.config.get(key.upper(), default)
    
    smtp_host = get_smtp_param('smtp_host')
    smtp_port = int(get_smtp_param('smtp_port', '587'))
    smtp_user = get_smtp_param('smtp_user')
    smtp_password = get_smtp_param('smtp_password')
    smtp_from = get_smtp_param('smtp_from', 'atelier@lycee.fr')
    
    if not smtp_host or not smtp_user:
        return
    
    # Get user who created OR
    created_by_user = User.query.get(or_obj.created_by) if or_obj.created_by else None
    professor_name = f"{created_by_user.prenom} {created_by_user.nom}" if created_by_user else "N/A"
    
    # Get etat lieux
    etat_entree = etat_lieu.query.filter_by(or_id=or_obj.id, type='entree').first()
    etat_sortie = etat_lieu.query.filter_by(or_id=or_obj.id, type='sortie').first()
    
    subject = f"Ouverture Ordre de réparation Meca Auto - {or_obj.numero}"
    
    body = f"""Ouverture d'un nouvel ordre de réparation:

Numéro OR: {or_obj.numero}
Statut: {or_obj.statut}
Date de création: {or_obj.date_ouverture.strftime('%d/%m/%Y à %H:%M') if or_obj.date_ouverture else 'N/A'}

Véhicule:
- Immatriculation: {vehicule.immatriculation}
- Marque: {vehicule.marque or 'N/A'}
- Modèle: {vehicule.modele or 'N/A'}

Travaux à effectuer:
{or_obj.description[:500] if or_obj.description else 'Aucun'}

Informations complémentaires:
- Classe: {or_obj.classe_nom or 'N/A'}
- Élève: {or_obj.eleve_nom or 'N/A'}
- Professor: {professor_name}

État des lieux d'entrée: {'Effectué' if etat_entree else 'Non effectué'}

---
Document PDF en pièce jointe.
Cet email est envoyé automatiquement par MEC AUTO"""

    try:
        # Generate PDF (OR recap + état des lieux d'entrée si disponible)
        try:
            import io
            from xhtml2pdf import pisa

            etab_nom = Parametre.get('etab_nom', 'MEC AUTO')
            interventions = list(or_obj.interventions_eleves) if or_obj.interventions_eleves else []

            combined_html = render_template('ordres/email_or_pdf.html',
                or_obj=or_obj,
                vehicule=vehicule,
                client=client,
                etab_nom=etab_nom,
                etab_adresse=Parametre.get('etab_adresse', ''),
                etab_tel=Parametre.get('etab_tel', ''),
                interventions=interventions,
                etat_entree=etat_entree,
                print_date=datetime.now().strftime('%d/%m/%Y à %H:%M'))

            buf = io.BytesIO()
            result = pisa.CreatePDF(combined_html, dest=buf, encoding='utf-8')
            if result.err:
                raise Exception(f"xhtml2pdf error: {result.err}")
            pdf_bytes = buf.getvalue()
            has_pdf = True
        except Exception as e:
            import traceback
            print(f"[NOTIF EMAIL] PDF generation failed: {e}")
            traceback.print_exc()
            pdf_bytes = None
            has_pdf = False
        
        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = ', '.join(emails)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF if generated
        if has_pdf and pdf_bytes:
            from email.mime.base import MIMEBase
            from email import encoders
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename=OR_{or_obj.numero}.pdf')
            msg.attach(part)
        
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Erreur envoi notification: {e}")


def send_client_email(or_obj, client, vehicule, event_type, facture=None):
    """Envoyer un email au client lors des changements de statut de l'OR"""
    if not client or not client.email:
        return

    notif_key = f'notif_client_{event_type}'
    if Parametre.get(notif_key, '0') != '1':
        return

    def get_smtp_param(key, default=''):
        param = Parametre.query.filter_by(cle=key).first()
        return param.valeur if param else current_app.config.get(key.upper(), default)

    smtp_host = get_smtp_param('smtp_host')
    smtp_port = int(get_smtp_param('smtp_port', '587'))
    smtp_user = get_smtp_param('smtp_user')
    smtp_password = get_smtp_param('smtp_password')
    smtp_from = get_smtp_param('smtp_from', 'atelier@lycee.fr')
    etab_nom = Parametre.get('etab_nom', 'Atelier')

    if not smtp_host or not smtp_user:
        return

    immat = vehicule.immatriculation if vehicule else 'N/A'
    marque_modele = f"{vehicule.marque or ''} {vehicule.modele or ''}".strip() if vehicule else ''

    subjects = {
        'cree':     f'Prise en charge de votre véhicule – OR {or_obj.numero}',
        'en_cours': f'Travaux en cours sur votre véhicule – OR {or_obj.numero}',
        'cloture':  f'Votre véhicule est prêt – OR {or_obj.numero}',
        'facture':  f'Votre facture – {facture.numero if facture else or_obj.numero}',
    }

    date_ouverture = or_obj.date_ouverture.strftime('%d/%m/%Y à %H:%M') if or_obj.date_ouverture else 'N/A'
    date_cloture = or_obj.date_cloture.strftime('%d/%m/%Y') if or_obj.date_cloture else 'N/A'

    bodies = {
        'cree': f"""Bonjour {client.prenom} {client.nom},

Votre véhicule {immat} {marque_modele} a bien été pris en charge par notre atelier.

Numéro OR : {or_obj.numero}
Date : {date_ouverture}
Travaux demandés : {or_obj.description or 'N/A'}

Nous vous contacterons dès que les travaux seront terminés.

Cordialement,
{etab_nom}""",
        'en_cours': f"""Bonjour {client.prenom} {client.nom},

Les travaux sur votre véhicule {immat} {marque_modele} ont démarré.

Numéro OR : {or_obj.numero}

Nous vous contacterons dès qu'ils seront terminés.

Cordialement,
{etab_nom}""",
        'cloture': f"""Bonjour {client.prenom} {client.nom},

Bonne nouvelle ! Les travaux sur votre véhicule {immat} {marque_modele} sont terminés.

Vous pouvez venir le récupérer à l'atelier.

Numéro OR : {or_obj.numero}
Date de clôture : {date_cloture}

Cordialement,
{etab_nom}""",
        'facture': f"""Bonjour {client.prenom} {client.nom},

Veuillez trouver ci-joint votre facture pour les travaux effectués sur votre véhicule {immat} {marque_modele}.

Numéro de facture : {facture.numero if facture else 'N/A'}
Montant : {facture.montant if facture else 'N/A'} €

Cordialement,
{etab_nom}""",
    }

    subject = subjects.get(event_type, f'Mise à jour OR {or_obj.numero}')
    body = bodies.get(event_type, '')

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = client.email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if event_type == 'facture' and facture:
            try:
                import io
                from xhtml2pdf import pisa
                from flask import render_template as _render
                from app.models import EleveIntervention as EI, RecupSurcharge
                interventions = EI.query.filter_by(or_id=or_obj.id).all()
                total_heures = sum(float(i.heures or 0) for i in interventions)
                taux_param = Parametre.query.filter_by(cle='taux_horaire').first()
                taux_horaire = float(taux_param.valeur) if taux_param else 50.0
                surcharge_lines = []
                if or_obj.client_recup_pieces or or_obj.client_recup_fluides:
                    for s in RecupSurcharge.query.filter_by(actif=True).all():
                        if 'pieces' in s.nom.lower() and or_obj.client_recup_pieces:
                            surcharge_lines.append(s)
                        if ('huile' in s.nom.lower() or 'fluide' in s.nom.lower()) and or_obj.client_recup_fluides:
                            surcharge_lines.append(s)
                html = _render('factures/print.html', facture=facture, or_obj=or_obj,
                               client=client, vehicule=vehicule, interventions=interventions,
                               total_heures=total_heures, taux_horaire=taux_horaire,
                               surcharge_lines=surcharge_lines)
                buf = io.BytesIO()
                result = pisa.CreatePDF(html, dest=buf, encoding='utf-8')
                if not result.err:
                    from email.mime.base import MIMEBase
                    from email import encoders
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(buf.getvalue())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename=facture_{facture.numero}.pdf')
                    msg.attach(part)
            except Exception as e:
                print(f"[CLIENT EMAIL] PDF facture failed: {e}")

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        print(f"[CLIENT EMAIL] '{event_type}' envoyé à {client.email}")
    except Exception as e:
        print(f"[CLIENT EMAIL] Erreur: {e}")


ordres_bp = Blueprint('ordres', __name__)

@ordres_bp.route('/')
@login_required
def liste():
    statut = request.args.get('statut')
    search = request.args.get('search')
    sort = request.args.get('sort', 'date_desc')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Fix "None" string values
    if search == 'None' or search == '':
        search = None
    if statut == 'None' or statut == '':
        statut = None
    if date_from == 'None' or date_from == '':
        date_from = None
    if date_to == 'None' or date_to == '':
        date_to = None

    query = OrdreReparation.query.join(Vehicule).join(Client)
    
    if current_user.role == 'eleve':
        from app.models import EleveIntervention
        query = query.filter(
            (OrdreReparation.created_by == current_user.id) |
            (OrdreReparation.id.in_(
                db.session.query(EleveIntervention.or_id).filter_by(eleve_id=current_user.id)
            ))
        )
    
    if statut:
        query = query.filter(OrdreReparation.statut == statut)
    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(OrdreReparation.created_at >= d)
        except: pass
    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(OrdreReparation.created_at <= d.replace(hour=23, minute=59))
        except: pass
    if search:
        query = query.filter(
            (OrdreReparation.numero.like(f'%{search}%')) |
            (Vehicule.immatriculation.like(f'%{search}%')) |
            (Client.nom.like(f'%{search}%')) |
            (Client.prenom.like(f'%{search}%'))
        )

    # Sorting - keep inner join for now, add vehicule/client sorting
    if sort == 'date_asc':
        query = query.order_by(OrdreReparation.created_at.asc())
    elif sort == 'montant_asc':
        query = query.order_by(OrdreReparation.montant.asc())
    elif sort == 'montant_desc':
        query = query.order_by(OrdreReparation.montant.desc())
    elif sort == 'numero_asc':
        query = query.order_by(OrdreReparation.numero.asc())
    elif sort == 'numero_desc':
        query = query.order_by(OrdreReparation.numero.desc())
    elif sort == 'vehicule_asc':
        query = query.order_by(Vehicule.immatriculation.asc())
    elif sort == 'vehicule_desc':
        query = query.order_by(Vehicule.immatriculation.desc())
    elif sort == 'client_asc':
        query = query.order_by(Client.nom.asc(), Client.prenom.asc())
    elif sort == 'client_desc':
        query = query.order_by(Client.nom.desc(), Client.prenom.desc())
    elif sort == 'statut_asc':
        query = query.order_by(OrdreReparation.statut.asc())
    elif sort == 'statut_desc':
        query = query.order_by(OrdreReparation.statut.desc())
    else:
        query = query.order_by(OrdreReparation.created_at.desc())

    ordres = query.all()
    return render_template('ordres/list.html', ordres=ordres, search=search, statut=statut, sort=sort, date_from=date_from, date_to=date_to)

@ordres_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not current_user.can_create_or():
        flash('Accès refusé', 'error')
        return redirect(url_for('ordres.liste'))

    if request.method == 'POST':
        # Validation téléphone : 10 chiffres requis
        tel_raw = request.form.get('client_tel', '').replace(' ', '').replace('.', '').replace('-', '')
        if tel_raw and len(tel_raw) != 10:
            flash('Le numéro de téléphone doit comporter 10 chiffres', 'error')
            return redirect(url_for('ordres.new'))
        if not tel_raw:
            flash('Le numéro de téléphone est obligatoire', 'error')
            return redirect(url_for('ordres.new'))

        vehicule_id = request.form.get('vehicule_id') or None
        immat = request.form.get('immatriculation', '').upper().replace('-', '').replace(' ', '')

        # Vérifier si véhicule existant ou à créer
        vehicule = None
        if vehicule_id:
            vehicule = Vehicule.query.get(vehicule_id)
        
        if not vehicule:
            from sqlalchemy import or_ as sql_or, func
            immat_input = request.form.get('immatriculation', '').upper().replace('-', '').replace(' ', '')
            existing_vehicule = Vehicule.query.filter(
                sql_or(
                    Vehicule.immatriculation == request.form.get('immatriculation', '').upper(),
                    func.replace(func.replace(Vehicule.immatriculation, '-', ''), ' ', '') == immat_input
                )
            ).first()

            if existing_vehicule:
                vehicule_id = existing_vehicule.id
                client_id = existing_vehicule.proprietaire_id or None
            else:
                client = Client(
                    nom=request.form.get('client_nom'),
                    prenom=request.form.get('client_prenom'),
                    telephone=request.form.get('client_tel'),
                    email=request.form.get('client_email')
                )
                db.session.add(client)
                db.session.flush()
                client_id = client.id

                _annee_raw = request.form.get('annee', '').strip()
                vehicule = Vehicule(
                    immatriculation=request.form.get('immatriculation').upper(),
                    marque=request.form.get('marque') or None,
                    modele=request.form.get('modele') or None,
                    annee=int(_annee_raw) if _annee_raw.isdigit() else None,
                    vin=request.form.get('vin') or None,
                    energie=request.form.get('energie') or None,
                    proprietaire_id=client_id
                )
                db.session.add(vehicule)
                db.session.flush()
                vehicule_id = vehicule.id

        vehicule = Vehicule.query.get(vehicule_id)
        # Mettre à jour VIN et énergie si renseignés dans le formulaire
        if vehicule:
            vin_form = request.form.get('vin') or None
            energie_form = request.form.get('energie') or None
            if vin_form:
                vehicule.vin = vin_form
            if energie_form:
                vehicule.energie = energie_form
        client = None

        if not vehicule or not vehicule.proprietaire:
            client = Client(
                nom=request.form.get('client_nom'),
                prenom=request.form.get('client_prenom'),
                telephone=request.form.get('client_tel'),
                email=request.form.get('client_email')
            )
            db.session.add(client)
            db.session.flush()
            client_id = client.id
        else:
            client_id = vehicule.proprietaire.id
            if request.form.get('change_proprio'):
                client = Client.query.get(client_id)
                client.nom = request.form.get('client_nom')
                client.prenom = request.form.get('client_prenom')
                client.telephone = request.form.get('client_tel')
                client.email = request.form.get('client_email')
            else:
                client = vehicule.proprietaire

        or_numero = OrdreReparation.generer_numero()
        or_obj = OrdreReparation(
            numero=or_numero,
            vehicule_id=vehicule_id,
            client_id=client_id,
            description=request.form.get('description'),
            statut='ouvert',
            mode_tarif=request.form.get('mode_tarif') or 'forfait',
            created_by=current_user.id,
            classe_nom = request.form.get('classe_nom') or None,
            eleve_nom = request.form.get('eleve_nom') or None,
            eleve_id = request.form.get('eleve_id') or None,
            rdv_titre = request.form.get('rdv_titre') or None,
            rdv_date_heure = None,
            ct_valide = request.form.get('ct_valide') == 'on',
            assurance_valide = request.form.get('assurance_valide') == 'on'
        )
        
        # Handle planned RDV - create proper RendezVous record
        rdv_date = request.form.get('rdv_date')
        rdv_time = request.form.get('rdv_time')
        if rdv_date and rdv_time:
            try:
                rdv_datetime = datetime.strptime(f"{rdv_date} {rdv_time}", "%Y-%m-%d %H:%M")
                or_obj.rdv_date_heure = rdv_datetime

                # Also create a proper RendezVous record if we have client_id
                if client_id:
                    # Get client name for title
                    client_obj = Client.query.get(client_id)
                    client_name = f"{client_obj.prenom} {client_obj.nom}" if client_obj else ""
                    intervention = (request.form.get('description', '') or '')[:30]
                    rdv_titre_auto = f"{client_name} - {intervention}" if (client_name and intervention) else (client_name or 'Rendez-vous')
                    or_obj.rdv_titre = rdv_titre_auto

                    rdv = RendezVous(
                        client_id=client_id,
                        vehicule_id=vehicule_id,
                        titre=rdv_titre_auto,
                        description=f"RDV lié à l'OR {or_numero}" + (f": {intervention}" if intervention else ""),
                        date_heure=rdv_datetime,
                        duree=60,
                        statut='planifie',
                        created_by=current_user.id
                    )
                    db.session.add(rdv)
                    db.session.flush()
                    Log.log(current_user, 'rdv_create', f'RDV créé depuis OR {or_numero}: {rdv.titre}', 'rdv', rdv.id)
            except Exception as e:
                print(f'Error creating RDV: {e}')
                pass

        db.session.add(or_obj)
        db.session.commit()
        
        client_name = 'N/A'
        if client:
            client_name = client.nom
        elif vehicule and vehicule.proprietaire:
            client_name = vehicule.proprietaire.nom
        Log.log(current_user, 'create_or', f'OR {or_numero} créé - Client: {client_name} - Véhicule: {vehicule.immatriculation}', 'OrdreReparation', or_obj.id)
        db.session.commit()
        
        # Envoyer notifications en arrière-plan
        final_client = client if client else (vehicule.proprietaire if vehicule and vehicule.proprietaire else None)
        if final_client:
            import threading
            app = current_app._get_current_object()
            or_id = or_obj.id
            client_id = final_client.id
            vehicule_id_bg = vehicule.id if vehicule else None
            def _send_email_bg():
                with app.app_context():
                    from app.models import OrdreReparation, Client, Vehicule
                    _or = OrdreReparation.query.get(or_id)
                    _client = Client.query.get(client_id)
                    _vehicule = Vehicule.query.get(vehicule_id_bg) if vehicule_id_bg else None
                    if _or and _client:
                        send_notification_email(_or, _client, _vehicule)
                        send_client_email(_or, _client, _vehicule, 'cree')
            threading.Thread(target=_send_email_bg, daemon=True).start()

        flash(f'OR {or_numero} créé', 'success')
        
        if request.form.get('faire_etat_lieux'):
            return redirect(url_for('ordres.etat_lieu_form', or_id=or_obj.id, type='entree'))
        
        return redirect(url_for('ordres.view', id=or_obj.id))

    forfaits = Forfait.query.filter_by(actif=True).all()
    surcharges = RecupSurcharge.query.filter_by(actif=True).all()
    surcharges_list = [{'id': s.id, 'nom': s.nom, 'montant': float(s.montant)} for s in surcharges]
    classes = Classe.query.filter_by(actif=True).order_by(Classe.nom).all()
    eleves = User.query.filter_by(role='eleve', actif=True).order_by(User.nom).all()
    return render_template('ordres/new.html', forfaits=forfaits, surcharges=surcharges, surcharges_list=surcharges_list, classes=classes, eleves=eleves)

@ordres_bp.route('/<int:id>')
@login_required
def view(id):
    from app.models import SessionTravail, Incident
    or_obj = OrdreReparation.query.get_or_404(id)
    client = Client.query.get(or_obj.client_id) if or_obj.client_id else None
    interventions = or_obj.interventions_eleves.all()
    etats = or_obj.etats_lieux.all()
    etat_entree = or_obj.etats_lieux.filter_by(type='entree').first()
    etat_sortie = or_obj.etats_lieux.filter_by(type='sortie').first()
    rdv_list = RendezVous.query.filter_by(client_id=or_obj.client_id).order_by(RendezVous.date_heure.desc()).all() if or_obj.client_id else []
    eleves = User.query.filter_by(role='eleve', actif=True).order_by(User.nom).all()
    fournitures = Fourniture.query.filter_by(actif=True).order_by(Fourniture.nom).all()

    # Défensif : tables créées par migrate_db.py, peut ne pas exister si migration pas encore faite
    try:
        sessions = SessionTravail.query.filter_by(or_id=id).order_by(SessionTravail.date_session.desc()).all()
        incidents = Incident.query.filter_by(or_id=id).order_by(Incident.date_constat.desc()).all()
    except Exception:
        db.session.rollback()
        sessions = []
        incidents = []
    incidents_attente = [i for i in incidents if i.statut == 'en_attente']

    return render_template('ordres/view.html',
        or_obj=or_obj, client=client, interventions=interventions,
        etats=etats, etat_entree=etat_entree, etat_sortie=etat_sortie,
        rdv_list=rdv_list, eleves=eleves, fournitures=fournitures,
        sessions=sessions, incidents=incidents,
        incidents_attente=incidents_attente,
        now=datetime.utcnow())

@ordres_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.can_edit_or():
        flash('Permission refusée: vous ne pouvez pas modifier les OR', 'error')
        return redirect(url_for('ordres.view', id=id))
    
    or_obj = OrdreReparation.query.get_or_404(id)
    if or_obj.statut == 'cloture':
        flash('OR cloturé, modification impossible', 'error')
        return redirect(url_for('ordres.view', id=id))

    if request.method == 'POST':
        or_obj.description = request.form.get('description')
        or_obj.mode_tarif = request.form.get('mode_tarif')

        if request.form.get('mode_tarif') == 'forfait':
            forfait_id = request.form.get('forfait_id')
            if forfait_id:
                forfait = Forfait.query.get(forfait_id)
                or_obj.montant = forfait.montant
        else:
            or_obj.montant = request.form.get('montant')

        or_obj.updated_at = datetime.utcnow()
        
        # Attente pièces
        attente_now = request.form.get('attente_pieces') == 'on'
        if attente_now and not or_obj.attente_pieces:
            or_obj.date_attente_pieces = datetime.now()
        elif not attente_now and or_obj.attente_pieces:
            or_obj.date_attente_pieces = None
        or_obj.attente_pieces = attente_now
        or_obj.remarque_attente = request.form.get('remarque_attente') or None
        
        # Pas de facturation
        or_obj.pas_de_facturation = request.form.get('pas_de_facturation') == 'on'
        
        db.session.commit()
        Log.log(current_user, 'edit_or', f'OR {or_obj.numero} modifié', 'OrdreReparation', or_obj.id)
        db.session.commit()
        flash('OR modifié', 'success')
        return redirect(url_for('ordres.view', id=id))

    forfaits = Forfait.query.filter_by(actif=True).all()
    return render_template('ordres/edit.html', or_obj=or_obj, forfaits=forfaits)

@ordres_bp.route('/<int:id>/statut', methods=['POST'])
@login_required
def set_statut(id):
    if not current_user.can_edit_or():
        flash('Permission refusée: vous ne pouvez pas modifier les OR', 'error')
        return redirect(url_for('ordres.view', id=id))
    
    or_obj = OrdreReparation.query.get_or_404(id)
    new_statut = request.form.get('statut')

    if new_statut not in ['ouvert', 'en_cours', 'termine', 'cloture']:
        flash('Statut invalide', 'error')
        return redirect(url_for('ordres.view', id=id))

    # Vérifications état des lieux (seulement pour cloture par DDFPT)
    etat_entree = or_obj.etats_lieux.filter_by(type='entree').first()
    etat_sortie = or_obj.etats_lieux.filter_by(type='sortie').first()

    if new_statut == 'cloture' and not etat_sortie and current_user.role == 'ddfpt':
        flash('État des lieux de SORTIE requis avant de cloturer', 'warning')
        return redirect(url_for('ordres.etat_lieu_form', or_id=id, type='sortie'))
    
    if new_statut == 'cloture':
        or_obj.date_cloture = datetime.utcnow()

    old_statut = or_obj.statut
    or_obj.statut = new_statut
    or_obj.updated_at = datetime.utcnow()
    db.session.commit()
    Log.log(current_user, 'change_statut', f'OR {or_obj.numero} - Statut: {old_statut} → {new_statut}', 'OrdreReparation', or_obj.id)
    db.session.commit()

    if new_statut in ('en_cours', 'cloture'):
        import threading
        app = current_app._get_current_object()
        or_id = or_obj.id
        event = new_statut
        def _send_statut_bg():
            with app.app_context():
                from app.models import OrdreReparation, Client, Vehicule
                _or = OrdreReparation.query.get(or_id)
                if _or:
                    _client = _or.client or (_or.vehicule.proprietaire if _or.vehicule else None)
                    send_client_email(_or, _client, _or.vehicule, event)
        threading.Thread(target=_send_statut_bg, daemon=True).start()

    flash(f'Statut mis à jour: {new_statut}', 'success')
    return redirect(url_for('ordres.view', id=id))

@ordres_bp.route('/<int:id>/intervention', methods=['POST'])
@login_required
def add_intervention(id):
    if not current_user.has_permission('edit_intervention'):
        flash('Permission refusée: vous ne pouvez pas ajouter d\'interventions', 'error')
        return redirect(url_for('ordres.view', id=id))
    
    or_obj = OrdreReparation.query.get_or_404(id)
    if or_obj.statut == 'cloture':
        flash('OR cloturé', 'error')
        return redirect(url_for('ordres.view', id=id))

    if current_user.role == 'eleve':
        eleve_id = current_user.id
    else:
        eleve_id = request.form.get('eleve_id')
        if not eleve_id:
            flash('Élève requis', 'error')
            return redirect(url_for('ordres.view', id=id))

    intervention = EleveIntervention(
        or_id=id,
        eleve_id=eleve_id,
        description=request.form.get('description'),
        heures=request.form.get('heures') or 0,
        fourniture_id=request.form.get('fourniture_id') or None,
        quantite=request.form.get('quantite') or 1
    )
    db.session.add(intervention)
    db.session.commit()
    flash('Intervention ajoutée', 'success')
    return redirect(url_for('ordres.view', id=id))

@ordres_bp.route('/intervention/<int:interv_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_intervention(interv_id):
    interv = EleveIntervention.query.get_or_404(interv_id)
    or_obj = interv.ordre
    if or_obj.statut == 'cloture':
        flash('OR clôturé, modification impossible', 'error')
        return redirect(url_for('ordres.view', id=or_obj.id))
    if current_user.role == 'eleve' and interv.eleve_id != current_user.id:
        flash('Permission refusée', 'error')
        return redirect(url_for('ordres.view', id=or_obj.id))
    if not current_user.has_permission('edit_intervention'):
        flash('Permission refusée', 'error')
        return redirect(url_for('ordres.view', id=or_obj.id))

    if request.method == 'POST':
        interv.description = request.form.get('description')
        interv.heures = request.form.get('heures') or 0
        interv.fourniture_id = request.form.get('fourniture_id') or None
        interv.quantite = request.form.get('quantite') or 1
        if current_user.role != 'eleve':
            eleve_id = request.form.get('eleve_id')
            if eleve_id:
                interv.eleve_id = eleve_id
        db.session.commit()
        flash('Intervention modifiée', 'success')
        return redirect(url_for('ordres.view', id=or_obj.id))

    eleves = User.query.filter_by(role='eleve').order_by(User.nom).all()
    fournitures = Fourniture.query.order_by(Fourniture.nom).all()
    return render_template('ordres/edit_intervention.html', interv=interv, or_obj=or_obj, eleves=eleves, fournitures=fournitures)


@ordres_bp.route('/intervention/<int:interv_id>/delete', methods=['POST'])
@login_required
def delete_intervention(interv_id):
    interv = EleveIntervention.query.get_or_404(interv_id)
    or_obj = interv.ordre
    if or_obj.statut == 'cloture':
        flash('OR clôturé, suppression impossible', 'error')
        return redirect(url_for('ordres.view', id=or_obj.id))
    if current_user.role == 'eleve':
        flash('Permission refusée', 'error')
        return redirect(url_for('ordres.view', id=or_obj.id))
    if not current_user.has_permission('edit_intervention'):
        flash('Permission refusée', 'error')
        return redirect(url_for('ordres.view', id=or_obj.id))
    or_id = or_obj.id
    db.session.delete(interv)
    db.session.commit()
    flash('Intervention supprimée', 'success')
    return redirect(url_for('ordres.view', id=or_id))


@ordres_bp.route('/<int:id>/etat-lieu', methods=['POST'])
@login_required
def add_etat_lieu(id):
    or_obj = OrdreReparation.query.get_or_404(id)
    type_etat = request.form.get('type')

    existing = or_obj.etats_lieux.filter_by(type=type_etat).first()
    if existing:
        _km = request.form.get('kilometrage', '').strip()
        existing.kilometrage = int(_km) if _km.isdigit() else None
        existing.niveau_carburant = request.form.get('niveau_carburant')
        existing.dommages = request.form.get('dommages')
        existing.observations = request.form.get('observations')
        existing.responsable = request.form.get('responsable')
        if type_etat == 'entree':
            existing.inventaire_objets = request.form.get('inventaire_objets', '').strip() or None
            existing.inventaire_signe = request.form.get('inventaire_signe') == '1'
    else:
        _km = request.form.get('kilometrage', '').strip()
        etat_kwargs = dict(
            or_id=or_obj.id,
            type=type_etat,
            kilometrage=int(_km) if _km.isdigit() else None,
            niveau_carburant=request.form.get('niveau_carburant'),
            dommages=request.form.get('dommages'),
            observations=request.form.get('observations'),
            responsable=request.form.get('responsable'),
        )
        if type_etat == 'entree':
            etat_kwargs['inventaire_objets'] = request.form.get('inventaire_objets', '').strip() or None
            etat_kwargs['inventaire_signe'] = request.form.get('inventaire_signe') == '1'
        etat = etat_lieu(**etat_kwargs)
        db.session.add(etat)

    db.session.commit()
    flash('État des lieux enregistré', 'success')
    return redirect(url_for('ordres.view', id=id))

@ordres_bp.route('/<int:id>/print')
@login_required
def print_or(id):
    or_obj = OrdreReparation.query.get_or_404(id)
    interventions = or_obj.interventions_eleves.all()
    etab_nom = Parametre.get('etab_nom', 'LYCÉE PROFESSIONNEL')
    return render_template('ordres/print.html', or_obj=or_obj, interventions=interventions, etab_nom=etab_nom)

def cascade_delete_or(or_obj):
    """
    Supprime un OR en gérant toutes les FK PostgreSQL.
    - Facture      : supprimée si présente (admin seulement — à vérifier avant d'appeler)
    - Interventions / états des lieux : cascade SQLAlchemy (delete-orphan)
    - Contrôles visuels / checklist    : supprimés explicitement (pas de cascade déclarée)
    """
    from app.models import Facture, ChecklistVerification, ControleVisuel

    # Facture liée (pas de cascade dans le modèle)
    if or_obj.facture:
        db.session.delete(or_obj.facture)

    # Contrôles visuels (pas de cascade déclarée)
    ControleVisuel.query.filter_by(or_id=or_obj.id).delete()

    # Vérifications checklist
    ChecklistVerification.query.filter_by(or_id=or_obj.id).delete()

    # L'OR lui-même (interventions + états des lieux cascadent via SQLAlchemy)
    db.session.delete(or_obj)
    db.session.commit()


@ordres_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.has_permission('delete_or'):
        flash('Permission refusée', 'error')
        return redirect(url_for('ordres.view', id=id))

    or_obj = OrdreReparation.query.get_or_404(id)
    numero = or_obj.numero

    # Facture liée : seul le DDFPT peut supprimer un OR facturé
    if or_obj.facture and current_user.role != 'ddfpt':
        flash(f'OR {numero} : une facture est liée. Seul l\'administrateur peut supprimer un OR facturé.', 'error')
        return redirect(url_for('ordres.view', id=id))

    cascade_delete_or(or_obj)
    flash(f'OR {numero} supprimé{" (facture incluse)" if or_obj.facture else ""}', 'success')
    return redirect(url_for('ordres.liste'))

@ordres_bp.route('/etat-lieu-form')
@login_required
def etat_lieu_form():
    vehicule_id = request.args.get('vehicule_id')
    or_id = request.args.get('or_id')
    type_etat = request.args.get('type', 'entree')
    vehicule = None
    or_obj = None
    
    if vehicule_id:
        vehicule = Vehicule.query.get(vehicule_id)
    if or_id:
        or_obj = OrdreReparation.query.get(or_id)
        if not vehicule:
            vehicule = or_obj.vehicule
    
    # Get checklist items for sortie
    checklist_items = []
    existing_verifs = {}
    km_entree = None
    if type_etat == 'sortie':
        from app.models import ChecklistItem, ChecklistVerification
        checklist_items = ChecklistItem.query.filter_by(actif=True).order_by(ChecklistItem.ordre).all()
        if or_obj:
            verifs = ChecklistVerification.query.filter_by(or_id=or_obj.id).all()
            for v in verifs:
                existing_verifs[v.checklist_item_id] = v.verified
            etat_entree = etat_lieu.query.filter_by(or_id=or_obj.id, type='entree').first()
            if etat_entree and etat_entree.kilometrage:
                km_entree = etat_entree.kilometrage

    etat_existant = etat_lieu.query.filter_by(or_id=or_obj.id, type=type_etat).first() if or_obj else None
    return render_template('ordres/etat_lieu_form.html', vehicule=vehicule, or_obj=or_obj,
                           type_etat=type_etat, checklist_items=checklist_items,
                           existing_verifs=existing_verifs, km_entree=km_entree,
                           etat=etat_existant)

@ordres_bp.route('/etat-lieu-save', methods=['POST'])
@login_required
def etat_lieu_save():
    # Only eleve and enseignant can create/edit etat des lieux
    if current_user.role not in ['eleve', 'enseignant']:
        flash('Seuls les élèves et enseignants peuvent modifier les états des lieux', 'error')
        return redirect(url_for('ordres.liste'))
    
    from app.models import etat_lieu
    
    or_id = request.form.get('or_id')
    vehicule_id = request.form.get('vehicule_id')
    type_etat = request.form.get('type_etat')
    
    if or_id:
        or_obj = OrdreReparation.query.get(or_id)
        existing = or_obj.etats_lieux.filter_by(type=type_etat).first()
        
        if existing:
            _km2 = request.form.get('kilometrage', '').strip()
            existing.kilometrage = int(_km2) if _km2.isdigit() else None
            existing.niveau_carburant = request.form.get('niveau_carburant')
            existing.dommages = request.form.get('dommages')
            existing.observations = request.form.get('observations')
            existing.responsable = request.form.get('responsable')
        else:
            _km2 = request.form.get('kilometrage', '').strip()
            etat = etat_lieu(
                or_id=or_id,
                type=type_etat,
                kilometrage=int(_km2) if _km2.isdigit() else None,
                niveau_carburant=request.form.get('niveau_carburant'),
                dommages=request.form.get('dommages'),
                observations=request.form.get('observations'),
                responsable=request.form.get('responsable')
            )
            db.session.add(etat)
        
        db.session.commit()
        
        # Save checklist verifications for sortie
        if type_etat == 'sortie':
            from app.models import ChecklistItem, ChecklistVerification
            checklist_items = ChecklistItem.query.filter_by(actif=True).all()
            for item in checklist_items:
                checked = request.form.get(f'checklist_{item.id}') == 'on'
                verif = ChecklistVerification.query.filter_by(or_id=or_id, checklist_item_id=item.id).first()
                if verif:
                    verif.verified = checked
                    verif.verified_by = current_user.id
                else:
                    verif = ChecklistVerification(or_id=or_id, checklist_item_id=item.id, verified=checked, verified_by=current_user.id)
                    db.session.add(verif)
            db.session.commit()
        
        action_type = "Création" if not existing else "Modification"
        Log.log(current_user, 'etat_lieu', f'{action_type} état des lieux {type_etat} - OR {or_obj.numero}', 'etat_lieu', existing.id if existing else etat.id)
        db.session.commit()
        flash('État des lieux enregistré', 'success')
        return redirect(url_for('ordres.view', id=or_id))
    else:
        flash('OR requis', 'error')
        return redirect(url_for('ordres.liste'))

@ordres_bp.route('/etat-lieu-print', methods=['GET', 'POST'])
@login_required
def etat_lieu_print():
    vehicule_id = request.args.get('vehicule_id') or request.form.get('vehicule_id')
    or_id = request.args.get('or_id')
    type_etat = request.args.get('type', 'entree')
    vehicule = None
    or_obj = None
    
    if vehicule_id:
        vehicule = Vehicule.query.get(vehicule_id)
    if or_id:
        or_obj = OrdreReparation.query.get(or_id)
        if or_obj:
            if not vehicule:
                vehicule = or_obj.vehicule
            client = or_obj.client
            etat = or_obj.etats_lieux.filter_by(type=type_etat).first()
        else:
            client = None
            etat = None
    else:
        client = None
        etat = None
    
    data = {
        'vehicule': vehicule,
        'or_obj': or_obj,
        'client': client,
        'etat_lieu': etat,
        'type_etat': type_etat,
        'kilometrage': request.form.get('kilometrage') or (etat.kilometrage if etat else ''),
        'niveau_carburant': request.form.get('niveau_carburant') or (etat.niveau_carburant if etat else ''),
        'dommages': request.form.get('dommages') or (etat.dommages if etat else ''),
        'observations': request.form.get('observations') or (etat.observations if etat else ''),
        'responsable': request.form.get('responsable') or (etat.responsable if etat else ''),
        'print_date': datetime.now().strftime('%d/%m/%Y'),
        'etab_nom': Parametre.get('etab_nom', 'LYCÉE PROFESSIONNEL')
    }
    return render_template('ordres/etat_lieu_print.html', **data)

@ordres_bp.route('/<int:id>/print-pare-brise')
@login_required
def print_pare_brise(id):
    """Impression simplifiée pour pare-brise - véhicule + travaux + états lieux"""
    or_obj = OrdreReparation.query.get_or_404(id)
    vehicule = or_obj.vehicule
    
    from app.models import etat_lieu
    etat_entree = etat_lieu.query.filter_by(or_id=id, type='entree').first()
    etat_sortie = etat_lieu.query.filter_by(or_id=id, type='sortie').first()
    
    created_by_user = User.query.get(or_obj.created_by) if or_obj.created_by else None
    
    return render_template('ordres/pare_brise.html', 
        or_obj=or_obj, 
        vehicule=vehicule,
        etab_nom=Parametre.get('etab_nom', 'MEC AUTO'),
        print_date=datetime.now().strftime('%d/%m/%Y à %H:%M'),
        etat_entree=etat_entree,
        etat_sortie=etat_sortie,
        created_by_user=created_by_user)

@ordres_bp.route('/controle/<int:id>', methods=['GET', 'POST'])
@login_required
def controle(id):
    from app.models import ControleVisuel
    import json
    
    or_obj = OrdreReparation.query.get_or_404(id)
    
    if request.method == 'POST':
        controle_data = {}
        
        for key in request.form:
            if key != 'observations':
                controle_data[key] = request.form.get(key)
        
        controle_data['observations'] = request.form.get('observations', '')
        
        existing = ControleVisuel.query.filter_by(or_id=id).first()
        
        try:
            if existing:
                existing.controle_data = json.dumps(controle_data)
                existing.created_by = current_user.id
            else:
                controle = ControleVisuel(
                    or_id=id,
                    controle_data=json.dumps(controle_data),
                    created_by=current_user.id
                )
                db.session.add(controle)
            
            db.session.commit()
            print("Enregistré:", controle_data)
        except Exception as e:
            print("Erreur:", e)
            db.session.rollback()
        Log.log(current_user, 'controle_visuel', f'Contrôle visuel enregistré - OR {or_obj.numero}', 'OrdreReparation', id)
        flash('Contrôle visuel enregistré', 'success')
        return redirect(url_for('ordres.view', id=id))
    
    existing = ControleVisuel.query.filter_by(or_id=id).first()
    controle_data = {}
    if existing and existing.controle_data:
        try:
            controle_data = json.loads(existing.controle_data)
        except:
            pass
    
    return render_template('ordres/controle.html', or_obj=or_obj, controle_data=controle_data)

@ordres_bp.route('/controle/<int:id>/print')
@login_required
def controle_print(id):
    or_obj = OrdreReparation.query.get_or_404(id)
    return render_template('ordres/controle_print.html', or_obj=or_obj, print_date=datetime.now().strftime('%d/%m/%Y'))