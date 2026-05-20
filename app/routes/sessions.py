from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from app import db
from app.models import OrdreReparation, SessionTravail, Incident, Log, Parametre, User
from datetime import datetime
import threading

sessions_bp = Blueprint('sessions', __name__)


# ── Helpers ────────────────────────────────────────────────────

def _send_incident_alert(incident_id):
    """Envoie un email d'alerte DDFPT si la notification est activée."""
    notif = Parametre.get('notif_incident', 'non')
    if notif != 'oui':
        return
    email_dest = Parametre.get('notif_incident_email', '')
    if not email_dest:
        return

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = Parametre.get('smtp_host', '')
    smtp_port = int(Parametre.get('smtp_port', '587') or 587)
    smtp_user = Parametre.get('smtp_user', '')
    smtp_pass = Parametre.get('smtp_password', '')
    if not smtp_host or not smtp_user:
        return

    app = current_app._get_current_object()

    def _send():
        with app.app_context():
            inc = Incident.query.get(incident_id)
            if not inc:
                return
            or_obj = inc.ordre
            declarant = inc.declarant
            types_fr = {
                'vol': 'Vol', 'degradation': 'Dégradation',
                'objet_manquant': 'Objet manquant', 'anomalie': 'Anomalie constatée'
            }
            type_fr = types_fr.get(inc.type_incident, inc.type_incident)
            subject = f'[MECA AUTO] ⚠️ Incident déclaré — OR {or_obj.numero}'
            body = (
                f"Un incident a été déclaré sur l'OR {or_obj.numero}.\n\n"
                f"Type       : {type_fr}\n"
                f"Déclaré par: {declarant.prenom} {declarant.nom} ({declarant.role})\n"
                f"Date constat: {inc.date_constat.strftime('%d/%m/%Y %H:%M')}\n"
                f"Description: {inc.description}\n"
            )
            if inc.objets_concernes:
                body += f"Objets     : {inc.objets_concernes}\n"
            body += f"\nStatut : En attente de validation par un enseignant.\n"
            body += f"\nAccéder à l'OR : /ordres/{or_obj.id}"

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = email_dest
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            try:
                srv = smtplib.SMTP(smtp_host, smtp_port)
                srv.starttls()
                srv.login(smtp_user, smtp_pass)
                srv.send_message(msg)
                srv.quit()
            except Exception:
                pass

    threading.Thread(target=_send, daemon=True).start()


# ── Sessions de travail ────────────────────────────────────────

@sessions_bp.route('/or/<int:or_id>/sessions/new', methods=['POST'])
@login_required
def session_new(or_id):
    if current_user.role not in ('ddfpt', 'enseignant'):
        flash('Accès refusé', 'error')
        return redirect(url_for('ordres.view', id=or_id))

    or_obj = OrdreReparation.query.get_or_404(or_id)
    date_str = request.form.get('date_session', '').strip()
    try:
        date_session = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        try:
            date_session = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            flash('Date de session invalide', 'error')
            return redirect(url_for('ordres.view', id=or_id))

    session = SessionTravail(
        or_id=or_id,
        enseignant_id=current_user.id,
        date_session=date_session,
        classe_nom=request.form.get('classe_nom', '').strip() or None,
        eleves_presents=request.form.get('eleves_presents', '').strip() or None,
        zone_vehicule=request.form.get('zone_vehicule', '').strip() or None,
        observations=request.form.get('observations', '').strip() or None,
    )
    db.session.add(session)
    db.session.flush()

    # Certifier immédiatement si demandé
    if request.form.get('certifier') == '1':
        session.certified_at = datetime.utcnow()

    db.session.commit()
    Log.log(current_user, 'session_travail',
            f'Session déclarée OR {or_obj.numero} — zone: {session.zone_vehicule or "?"} '
            f'— classe: {session.classe_nom or "?"}',
            'session', session.id)
    flash('Session de travail enregistrée', 'success')
    return redirect(url_for('ordres.view', id=or_id) + '#sessions')


@sessions_bp.route('/or/<int:or_id>/sessions/<int:sid>/certifier', methods=['POST'])
@login_required
def session_certifier(or_id, sid):
    session = SessionTravail.query.get_or_404(sid)
    if session.or_id != or_id:
        flash('Erreur', 'error')
        return redirect(url_for('ordres.view', id=or_id))
    if session.is_certified:
        flash('Session déjà certifiée', 'info')
        return redirect(url_for('ordres.view', id=or_id) + '#sessions')
    # Seul l'auteur ou le DDFPT peut certifier
    if current_user.id != session.enseignant_id and current_user.role != 'ddfpt':
        flash('Seul l\'auteur ou le DDFPT peut certifier', 'error')
        return redirect(url_for('ordres.view', id=or_id) + '#sessions')
    session.certified_at = datetime.utcnow()
    db.session.commit()
    Log.log(current_user, 'session_certifiee',
            f'Session {sid} certifiée — OR {session.ordre.numero}', 'session', sid)
    flash('Session certifiée et figée', 'success')
    return redirect(url_for('ordres.view', id=or_id) + '#sessions')


# ── Incidents ──────────────────────────────────────────────────

@sessions_bp.route('/or/<int:or_id>/incidents/new', methods=['POST'])
@login_required
def incident_new(or_id):
    or_obj = OrdreReparation.query.get_or_404(or_id)
    date_str = request.form.get('date_constat', '').strip()
    try:
        date_constat = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        date_constat = datetime.utcnow()

    type_incident = request.form.get('type_incident', '').strip()
    if type_incident not in Incident.TYPES:
        flash('Type d\'incident invalide', 'error')
        return redirect(url_for('ordres.view', id=or_id) + '#incidents')

    description = request.form.get('description', '').strip()
    if not description:
        flash('La description est obligatoire', 'error')
        return redirect(url_for('ordres.view', id=or_id) + '#incidents')

    incident = Incident(
        or_id=or_id,
        declared_by=current_user.id,
        type_incident=type_incident,
        description=description,
        objets_concernes=request.form.get('objets_concernes', '').strip() or None,
        date_constat=date_constat,
        statut='en_attente',
    )
    # Enseignant/DDFPT : validé directement
    if current_user.role in ('ddfpt', 'enseignant'):
        incident.statut = 'valide'
        incident.validated_by = current_user.id
        incident.validated_at = datetime.utcnow()

    db.session.add(incident)
    db.session.flush()
    db.session.commit()

    types_fr = {'vol': 'Vol', 'degradation': 'Dégradation',
                'objet_manquant': 'Objet manquant', 'anomalie': 'Anomalie'}
    Log.log(current_user, 'incident_declare',
            f'Incident "{types_fr.get(type_incident, type_incident)}" déclaré — OR {or_obj.numero}',
            'incident', incident.id)

    if incident.statut == 'en_attente':
        flash('Incident déclaré — en attente de validation par un enseignant', 'warning')
    else:
        flash('Incident déclaré et enregistré', 'warning')
        _send_incident_alert(incident.id)

    return redirect(url_for('ordres.view', id=or_id) + '#incidents')


@sessions_bp.route('/or/<int:or_id>/incidents/<int:iid>/valider', methods=['POST'])
@login_required
def incident_valider(or_id, iid):
    if current_user.role not in ('ddfpt', 'enseignant'):
        flash('Accès refusé', 'error')
        return redirect(url_for('ordres.view', id=or_id) + '#incidents')

    incident = Incident.query.get_or_404(iid)
    if incident.or_id != or_id:
        flash('Erreur', 'error')
        return redirect(url_for('ordres.view', id=or_id))

    incident.statut = 'valide'
    incident.validated_by = current_user.id
    incident.validated_at = datetime.utcnow()
    db.session.commit()
    Log.log(current_user, 'incident_valide',
            f'Incident {iid} validé — OR {incident.ordre.numero}', 'incident', iid)
    flash('Incident validé', 'success')
    _send_incident_alert(incident.id)
    return redirect(url_for('ordres.view', id=or_id) + '#incidents')


@sessions_bp.route('/or/<int:or_id>/incidents/<int:iid>/modifier', methods=['POST'])
@login_required
def incident_modifier(or_id, iid):
    """Seul le DDFPT peut modifier un incident — loggé systématiquement."""
    if current_user.role != 'ddfpt':
        flash('Seul le DDFPT peut modifier un incident enregistré', 'error')
        return redirect(url_for('ordres.view', id=or_id) + '#incidents')

    incident = Incident.query.get_or_404(iid)
    if incident.or_id != or_id:
        flash('Erreur', 'error')
        return redirect(url_for('ordres.view', id=or_id))

    old_desc = incident.description
    incident.description = request.form.get('description', incident.description).strip()
    incident.objets_concernes = request.form.get('objets_concernes', '').strip() or None
    incident.type_incident = request.form.get('type_incident', incident.type_incident)
    db.session.commit()

    Log.log(current_user, 'incident_modifie_ddfpt',
            f'DDFPT a modifié incident {iid} — OR {incident.ordre.numero} '
            f'— ancien contenu: "{old_desc[:80]}"',
            'incident', iid)
    flash('Incident modifié — action enregistrée dans les logs', 'warning')
    return redirect(url_for('ordres.view', id=or_id) + '#incidents')
