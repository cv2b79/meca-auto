"""
MECA AUTO — Recalcul du montant des factures existantes

Avant le correctif 09e8c77, les factures au taux horaire enregistraient le champ
« Montant » de l'OR (souvent vide → 0 €) au lieu de heures × taux horaire.

Usage (dans /opt/meca-auto) :
    venv/bin/python scripts/recalcul_factures.py              # simulation : liste les écarts, ne modifie rien
    venv/bin/python scripts/recalcul_factures.py --appliquer  # corrige (anciens montants sauvegardés en CSV)
"""
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Facture
from app.routes.factures import calcul_montants

appliquer = '--appliquer' in sys.argv
app = create_app()

with app.app_context():
    ecarts = []
    for f in Facture.query.order_by(Facture.id).all():
        or_obj = f.ordre
        if not or_obj:
            continue
        ancien = round(float(f.montant or 0), 2)
        nouveau = round(calcul_montants(or_obj)['total_ttc'], 2)
        if abs(ancien - nouveau) >= 0.01:
            ecarts.append((f, or_obj, ancien, nouveau))

    total = Facture.query.count()
    print(f"{total} facture(s) au total, {len(ecarts)} à corriger\n")
    if not ecarts:
        sys.exit(0)

    print(f"{'Facture':<16} {'OR':<15} {'Mode':<8} {'Paiement':<11} {'Ancien':>9} {'Nouveau':>9}")
    for f, o, ancien, nouveau in ecarts:
        mode = 'interne' if o.pas_de_facturation else (o.mode_tarif or '?')
        paiement = getattr(f, 'statut_paiement', '') or ''
        print(f"{f.numero:<16} {o.numero:<15} {mode:<8} {paiement:<11} {ancien:>8.2f}€ {nouveau:>8.2f}€")

    if not appliquer:
        print("\nSimulation uniquement : rien n'a été modifié. Relancer avec --appliquer pour corriger.")
        sys.exit(0)

    dossier = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, f"factures_avant_recalcul_{datetime.now():%Y%m%d_%H%M%S}.csv")
    with open(chemin, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['facture_id', 'numero', 'or', 'ancien_montant', 'nouveau_montant'])
        for f, o, ancien, nouveau in ecarts:
            w.writerow([f.id, f.numero, o.numero, f"{ancien:.2f}", f"{nouveau:.2f}"])

    date = datetime.now().strftime('%d/%m/%Y')
    for f, o, ancien, nouveau in ecarts:
        f.montant = nouveau
        f.details = (f.details or '') + f"\n\nMontant recalculé le {date} : {ancien:.2f}€ → {nouveau:.2f}€"
    db.session.commit()
    print(f"\n✅ {len(ecarts)} facture(s) corrigée(s). Anciens montants sauvegardés dans : {chemin}")
