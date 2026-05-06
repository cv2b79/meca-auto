from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Client, Vehicule, OrdreReparation, Facture, Enseignant, Classe, Forfait, RecupSurcharge, Consumable, Log, User, Parametre
import os
import csv
import io
from datetime import datetime

data_bp = Blueprint('data', __name__)

@data_bp.route('/backup')
@login_required
def backup():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    import sqlite3
    import os
    
    db_path = 'mecaauto.db'
    if os.path.exists(db_path):
        return send_file(db_path, as_attachment=True, download_name=f'mecaauto_backup_{datetime.now().strftime("%Y%m%d")}.db')
    else:
        flash('Base de données non trouvée', 'error')
        return redirect(url_for('data.index'))

@data_bp.route('/')
@login_required
def index():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    stats = {
        'clients': Client.query.count(),
        'vehicules': Vehicule.query.count(),
        'ordres': OrdreReparation.query.count(),
        'or_clotures': OrdreReparation.query.filter_by(statut='cloture').count(),
        'factures': Facture.query.count()
    }
    return render_template('data/index.html', stats=stats)

@data_bp.route('/export/<type>')
@login_required
def export_csv(type):
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if type == 'clients':
        writer.writerow(['ID', 'Nom', 'Prénom', 'Email', 'Téléphone', 'Adresse'])
        for c in Client.query.all():
            writer.writerow([c.id, c.nom, c.prenom, c.email or '', c.telephone or '', c.adresse or ''])
        filename = f'clients_{datetime.now().strftime("%Y%m%d")}.csv'
    
    elif type == 'vehicules':
        writer.writerow(['ID', 'Immatriculation', 'Marque', 'Modèle', 'Année', 'VIN', 'Énergie'])
        for v in Vehicule.query.all():
            writer.writerow([v.id, v.immatriculation, v.marque, v.modele, v.annee or '', v.vin or '', v.energie or ''])
        filename = f'vehicules_{datetime.now().strftime("%Y%m%d")}.csv'
    
    elif type == 'ordres':
        writer.writerow(['ID', 'Numéro', 'Statut', 'Date création', 'Montant', 'Véhicule', 'Client'])
        for o in OrdreReparation.query.all():
            writer.writerow([o.id, o.numero, o.statut, o.created_at.strftime('%Y-%m-%d') if o.created_at else '', 
                           o.montant or '', o.vehicule.immatriculation if o.vehicule else '', 
                           f"{o.client.prenom} {o.client.nom}" if o.client else ''])
        filename = f'ordres_{datetime.now().strftime("%Y%m%d")}.csv'
    
    else:
        flash('Type d\'export invalide', 'error')
        return redirect(url_for('data.index'))
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), 
                     mimetype='text/csv', as_attachment=True, download_name=filename)

@data_bp.route('/import', methods=['POST'])
@login_required
def import_csv():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    file = request.files.get('file')
    type_import = request.form.get('type')
    
    if not file or not type_import:
        flash('Fichier ou type manquant', 'error')
        return redirect(url_for('data.index'))
    
    try:
        content = file.read().decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        next(reader)  # Skip header
        
        count = 0
        if type_import == 'clients':
            for row in reader:
                if len(row) >= 2:
                    client = Client(nom=row[1], prenom=row[2] if len(row) > 2 else '')
                    client.email = row[3] if len(row) > 3 else None
                    client.telephone = row[4] if len(row) > 4 else None
                    client.adresse = row[5] if len(row) > 5 else None
                    db.session.add(client)
                    count += 1
        
        elif type_import == 'vehicules':
            for row in reader:
                if len(row) >= 3:
                    vehicule = Vehicule(immatriculation=row[1], marque=row[2], modele=row[3] if len(row) > 3 else '')
                    vehicule.annee = int(row[4]) if len(row) > 4 and row[4].isdigit() else None
                    vehicule.vin = row[5] if len(row) > 5 else None
                    vehicule.energie = row[6] if len(row) > 6 else None
                    db.session.add(vehicule)
                    count += 1
        
        db.session.commit()
        flash(f'{count} enregistrements importés', 'success')
    
    except Exception as e:
        flash(f'Erreur import: {str(e)}', 'error')
    
    return redirect(url_for('data.index'))

@data_bp.route('/archiver', methods=['POST'])
@login_required
def archiver():
    if not current_user.can_manage_settings():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    year = request.form.get('year')
    if not year:
        flash('Année manquante', 'error')
        return redirect(url_for('data.index'))
    
    from datetime import datetime
    cutoff = datetime(int(year), 12, 31)
    
    # Archiver les OR cloturés
    ors = OrdreReparation.query.filter(
        OrdreReparation.statut == 'cloture',
        OrdreReparation.date_cloture != None,
        OrdreReparation.date_cloture < cutoff
    ).all()
    
    for o in ors:
        o.statut = 'archive'
    
    db.session.commit()
    flash(f'{len(ors)} ordres archivés', 'success')
    return redirect(url_for('data.index'))

@data_bp.route('/stats')
@login_required
def stats():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    from sqlalchemy import func
    
    stats = {
        'total_clients': Client.query.count(),
        'total_vehicules': Vehicule.query.count(),
        'total_ordres': OrdreReparation.query.count(),
        'or_par_statut': db.session.query(OrdreReparation.statut, func.count(OrdreReparation.id)).group_by(OrdreReparation.statut).all(),
        'total_factures': db.session.query(func.sum(Facture.montant)).scalar() or 0,
        'factures_par_mois': db.session.query(
            func.strftime('%Y-%m', Facture.emitted_at), 
            func.count(Facture.id),
            func.sum(Facture.montant)
        ).filter(Facture.emitted_at != None).group_by(func.strftime('%Y-%m', Facture.emitted_at)).all()
    }
    
    return render_template('data/stats.html', stats=stats)

@data_bp.route('/stats/export')
@login_required
def stats_export():
    if not current_user.can_see_stats():
        flash('Accès refusé', 'error')
        return redirect(url_for('main.index'))
    
    from sqlalchemy import func
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Statistiques MEC AUTO'])
    writer.writerow(['Date export', datetime.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow([])
    
    writer.writerow(['Total clients', Client.query.count()])
    writer.writerow(['Total véhicules', Vehicule.query.count()])
    writer.writerow(['Total ordres', OrdreReparation.query.count()])
    writer.writerow(['Total factures', db.session.query(func.sum(Facture.montant)).scalar() or 0])
    writer.writerow([])
    
    writer.writerow(['ORDRE PAR STATUT'])
    for statut, count in db.session.query(OrdreReparation.statut, func.count(OrdreReparation.id)).group_by(OrdreReparation.statut).all():
        writer.writerow([statut, count])
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), 
                     mimetype='text/csv', as_attachment=True, download_name=f'stats_mecaauto_{datetime.now().strftime("%Y%m%d")}.csv')

@data_bp.route('/logs')
@login_required
def logs():
    if not current_user.role == 'ddfpt':
        flash('Accès réservé au DDFPT', 'error')
        return redirect(url_for('main.index'))
    
    sort = request.args.get('sort', 'date_desc')
    action_filter = request.args.get('action')
    user_filter = request.args.get('user_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Log.query
    
    if action_filter:
        query = query.filter(Log.action == action_filter)
    if user_filter:
        query = query.filter(Log.user_id == user_filter)
    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Log.created_at >= d)
        except: pass
    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Log.created_at <= d.replace(hour=23, minute=59))
        except: pass
    
    # Sorting
    if sort == 'date_asc':
        query = query.order_by(Log.created_at.asc())
    elif sort == 'user':
        query = query.join(User).order_by(User.nom.asc(), User.prenom.asc())
    elif sort == 'action':
        query = query.order_by(Log.action.asc())
    else:
        query = query.order_by(Log.created_at.desc())
    
    logs = query.limit(200).all()
    
    # Get filter options
    actions = db.session.query(Log.action).distinct().all()
    users = User.query.filter(User.actif == True).order_by(User.nom, User.prenom).all()
    
    return render_template('data/logs.html', logs=logs, actions=[a[0] for a in actions], 
                          users=users, sort=sort, action_filter=action_filter, 
                          user_filter=user_filter, date_from=date_from, date_to=date_to)

@data_bp.route('/backup-create')
@login_required
def backup_create():
    if not current_user.role == 'ddfpt':
        flash('Accès réservé au DDFPT', 'error')
        return redirect(url_for('main.index'))
    
    from flask import make_response
    import subprocess
    import os
    
    db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    
    backup_path = Parametre.get('backup_path', '')
    if not backup_path:
        backup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    
    os.makedirs(backup_path, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'mecaauto_backup_{timestamp}.sql'
    filepath = os.path.join(backup_path, filename)
    
    if 'sqlite' in db_url:
        db_path = db_url.replace('sqlite:///', '')
        # Si chemin relatif, utiliser le chemin absolue depuis le dossier instance
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', db_path)
        import shutil
        shutil.copy(db_path, filepath)
    else:
        flash('Backup PostgreSQL nécessite configuration manuelle', 'warning')
        return redirect(url_for('data.index'))
    
    flash(f'Sauvegarde créée: {filename}', 'success')
    Log.log(current_user, 'backup', f'Sauvegarde created: {filename}')
    return redirect(url_for('data.backups'))

@data_bp.route('/backup-file/<path:filename>')
@login_required
def backup_file(filename):
    if not current_user.role == 'ddfpt':
        flash('Accès réservé au DDFPT', 'error')
        return redirect(url_for('main.index'))
    
    backup_path = Parametre.get('backup_path', '')
    if not backup_path:
        backup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    
    filepath = os.path.join(backup_path, filename)
    if not os.path.exists(filepath):
        flash('Fichier non trouvé', 'error')
        return redirect(url_for('data.index'))
    
    from flask import send_file
    return send_file(filepath, as_attachment=True, download_name=filename)

@data_bp.route('/backups')
@login_required
def backups():
    if not current_user.role == 'ddfpt':
        flash('Accès réservé au DDFPT', 'error')
        return redirect(url_for('main.index'))
    
    import os
    backup_path = Parametre.get('backup_path', '')
    if not backup_path:
        backup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    
    files = []
    if os.path.exists(backup_path):
        for f in os.listdir(backup_path):
            if f.endswith('.sql') or f.endswith('.db'):
                filepath = os.path.join(backup_path, f)
                size = os.path.getsize(filepath)
                files.append({
                    'name': f,
                    'size': f'{size/1024:.1f} KB',
                    'date': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%d/%m/%Y %H:%M')
                })
    
    files.sort(key=lambda x: x['date'], reverse=True)
    return render_template('data/backups.html', files=files, backup_path=backup_path)