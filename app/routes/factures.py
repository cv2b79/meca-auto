from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from app import db
from app.models import Facture, OrdreReparation, EleveIntervention, Log
from datetime import datetime
import io
from app.smtp_utils import smtp_send
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

factures_bp = Blueprint('factures', __name__)


def calcul_montants(or_obj, taux_horaire=None):
    """Montants d'un OR, seule source de vérité pour la facture (montant enregistré ET PDF).

    Main-d'œuvre : forfait → montant du forfait de l'OR ;
    horaire → temps passé sur le véhicule (heures pleines, champ de l'OR) × taux horaire.
    Les heures des interventions élèves ne sont pas facturées : elles servent au suivi
    pédagogique et à suggérer le temps véhicule.
    Total = main-d'œuvre + fournitures + frais de dépollution (0 si « pas de facturation »)."""
    from app.models import Parametre
    interventions = EleveIntervention.query.filter_by(or_id=or_obj.id).all()
    total_heures = sum(float(i.heures or 0) for i in interventions)
    heures_par_eleve = {}
    for i in interventions:
        heures_par_eleve[i.eleve_id] = heures_par_eleve.get(i.eleve_id, 0) + float(i.heures or 0)
    if taux_horaire is not None:
        taux_horaire = float(taux_horaire)  # taux figé dans la facture
    else:
        try:
            taux_horaire = float(str(Parametre.get('taux_horaire', '50') or 50).replace(',', '.'))
        except ValueError:
            taux_horaire = 50.0
    est_forfait = or_obj.mode_tarif == 'forfait'
    heures_vehicule = or_obj.heures_vehicule or 0

    if est_forfait:
        prix = or_obj.montant if or_obj.montant is not None else (or_obj.forfait.montant if or_obj.forfait else 0)
        total_mo = float(prix or 0)
    else:
        total_mo = heures_vehicule * taux_horaire

    # Fournitures regroupées par article
    fournitures_map = {}
    for i in interventions:
        if i.fourniture_id and i.fourniture:
            f = fournitures_map.setdefault(i.fourniture_id, {
                'nom': i.fourniture.nom, 'qte': 0,
                'pu': float(i.fourniture.prix_unitaire or 0), 'total': 0.0,
            })
            f['qte'] += int(i.quantite or 1)
            f['total'] += f['pu'] * int(i.quantite or 1)
    fournitures_lines = list(fournitures_map.values())
    total_fournitures = sum(f['total'] for f in fournitures_lines)

    total_surcharge = float(or_obj.montant_surcharge or 0)
    total_ttc = 0.0 if or_obj.pas_de_facturation else total_mo + total_fournitures + total_surcharge

    return dict(
        interventions=interventions,
        mo_lines=[i for i in interventions if not i.fourniture_id],
        total_heures=total_heures,
        heures_vehicule=heures_vehicule,
        nb_eleves=len([e for e, h in heures_par_eleve.items() if h]),
        heures_max_eleve=max(heures_par_eleve.values(), default=0),
        taux_horaire=taux_horaire,
        est_forfait=est_forfait,
        total_mo=total_mo,
        fournitures_lines=fournitures_lines,
        total_fournitures=total_fournitures,
        total_surcharge=total_surcharge,
        total_ttc=total_ttc,
    )


def _build_facture_context(facture):
    """Construit le contexte commun pour les templates de facture (print + pdf)."""
    from app.models import Parametre, RecupSurcharge
    or_obj = facture.ordre

    surcharge_lines = []
    if not or_obj.client_recup_pieces or not or_obj.client_recup_fluides:
        for s in RecupSurcharge.query.filter_by(actif=True).all():
            if 'pieces' in s.nom.lower() and not or_obj.client_recup_pieces:
                surcharge_lines.append(s)
            if ('huile' in s.nom.lower() or 'fluide' in s.nom.lower()) and not or_obj.client_recup_fluides:
                surcharge_lines.append(s)

    return dict(
        facture=facture,
        or_obj=or_obj,
        client=or_obj.client,
        vehicule=or_obj.vehicule,
        surcharge_lines=surcharge_lines,
        cgv_texte=Parametre.get('cgv_texte', ''),
        mention_reglement=Parametre.get('mention_reglement', ''),
        **calcul_montants(or_obj, facture.taux_horaire),
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
    m = calcul_montants(facture.ordre, facture.taux_horaire) if facture.ordre else None
    ecart = m is not None and abs(round(m['total_ttc'], 2) - float(facture.montant or 0)) >= 0.01
    return render_template('factures/view.html', facture=facture, m=m, ecart=ecart)


@factures_bp.route('/<int:id>/recalcul', methods=['POST'])
@login_required
def recalcul(id):
    """Aligne le montant enregistré sur le calcul (celui de l'impression/PDF), après saisie éventuelle
    du temps véhicule. Le taux horaire est figé à cette occasion pour les anciennes factures."""
    if not current_user.can_facturer():
        flash('Accès refusé', 'error')
        return redirect(url_for('factures.view', id=id))
    facture = Facture.query.get_or_404(id)
    or_obj = facture.ordre
    if 'heures_vehicule' in request.form:
        from app.routes.ordres import _heures_pleines
        saisie = request.form.get('heures_vehicule', '').strip()
        or_obj.heures_vehicule = _heures_pleines(saisie) if saisie else None
    m = calcul_montants(or_obj, facture.taux_horaire)
    ancien = float(facture.montant or 0)
    nouveau = round(m['total_ttc'], 2)
    facture.taux_horaire = m['taux_horaire']
    if abs(nouveau - ancien) >= 0.01:
        facture.montant = nouveau
        facture.details = (facture.details or '') + (
            f"\n\nMontant mis à jour le {datetime.now():%d/%m/%Y} par {current_user.prenom} {current_user.nom} : "
            f"{ancien:.2f}€ → {nouveau:.2f}€")
        Log.log(current_user, 'recalcul_facture', f'Facture {facture.numero} : {ancien:.2f}€ → {nouveau:.2f}€',
                'Facture', facture.id)
        flash(f'Montant mis à jour : {ancien:.2f} € → {nouveau:.2f} €', 'success')
    else:
        flash('Le montant était déjà à jour', 'info')
    db.session.commit()
    return redirect(url_for('factures.view', id=id))

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

    if request.method == 'POST' and 'heures_vehicule' in request.form:
        from app.routes.ordres import _heures_pleines
        saisie = request.form.get('heures_vehicule', '').strip()
        or_obj.heures_vehicule = _heures_pleines(saisie) if saisie else None
        db.session.commit()
        if request.form.get('action') == 'apercu':
            return redirect(url_for('factures.create', or_id=or_id))

    m = calcul_montants(or_obj)

    if request.method == 'POST':
        total = round(m['total_ttc'], 2)
        lignes = [f"Travaux sur {or_obj.vehicule.immatriculation} - {or_obj.vehicule.marque} {or_obj.vehicule.modele}"]
        if m['est_forfait']:
            lignes += ["Mode: Forfait", f"Main-d'œuvre (forfait): {m['total_mo']:.2f}€"]
        else:
            lignes += ["Mode: Taux horaire",
                       f"Main-d'œuvre (temps véhicule): {m['heures_vehicule']} h × {m['taux_horaire']:.2f}€ = {m['total_mo']:.2f}€"]
        lignes += [f"  - {f['nom']} x{f['qte']} = {f['total']:.2f}€" for f in m['fournitures_lines']]
        if m['total_fournitures'] > 0:
            lignes.append(f"Fournitures: {m['total_fournitures']:.2f}€")
        if m['total_surcharge'] > 0:
            lignes.append(f"Frais dépollution: {m['total_surcharge']:.2f}€")
            if not or_obj.client_recup_pieces:
                lignes.append("  - Pièces non récupérées")
            if not or_obj.client_recup_fluides:
                lignes.append("  - Fluides non récupérés")
        if or_obj.pas_de_facturation:
            lignes.append("Travaux internes — pas de facturation")
        lignes += ["", f"Total: {total:.2f}€"]
        details = "\n".join(lignes)

        facture = Facture(
            numero=Facture.generer_numero(or_obj),
            or_id=or_id,
            montant=total,
            mode_tarif=or_obj.mode_tarif,
            details=details,
            taux_horaire=m['taux_horaire'],
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

    return render_template('factures/create.html', or_obj=or_obj, **m)

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
        smtp_send(msg, smtp_host, smtp_port, smtp_user, smtp_password)

        facture.send_by_email = True
        db.session.commit()
        Log.log(current_user, 'send_facture',
                f'Facture {facture.numero} envoyée à {client.email}', 'Facture', facture.id)
        flash('Facture envoyée par email ✓', 'success')
    except Exception as e:
        flash(f'Erreur envoi email : {str(e)}', 'error')

    return redirect(url_for('factures.view', id=id))


@factures_bp.route('/<int:id>/paiement', methods=['POST'])
@login_required
def toggle_paiement(id):
    """Magasinier ou DDFPT peuvent marquer une facture comme soldée / en attente."""
    if not current_user.can_facturer():
        flash('Accès refusé', 'error')
        return redirect(url_for('factures.view', id=id))

    facture = Facture.query.get_or_404(id)
    nouveau_statut = request.form.get('statut_paiement', 'en_attente')
    if nouveau_statut not in ('en_attente', 'soldee'):
        flash('Statut invalide', 'error')
        return redirect(url_for('factures.view', id=id))

    facture.statut_paiement = nouveau_statut
    db.session.commit()
    Log.log(current_user, 'paiement_facture',
            f'Facture {facture.numero} → statut paiement: {nouveau_statut}',
            'Facture', facture.id)
    flash('Statut de paiement mis à jour', 'success')
    return redirect(url_for('factures.view', id=id))