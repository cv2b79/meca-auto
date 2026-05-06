#!/usr/bin/env python3
"""
Script pour populate la base de données avec des données de test
Usage: python populate_test.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Client, Vehicule, User, Enseignant, Classe
import random
from datetime import datetime, timedelta

app = create_app()

# Configuration
MARQUES = ['Peugeot', 'Renault', 'Citroën', 'Volkswagen', 'Ford', 'Toyota', 'Nissan', 'BMW', 'Mercedes', 'Audi']
MODELES = {
    'Peugeot': ['208', '308', '3008', '5008'],
    'Renault': ['Clio', 'Mégane', 'Captur', 'Kadjar', 'Austral'],
    'Citroën': ['C3', 'C4', 'C5 Aircross', 'Berlingo'],
    'Volkswagen': ['Golf', 'Polo', 'T-Roc', 'Tiguan'],
    'Ford': ['Fiesta', 'Focus', 'Kuga', 'Puma'],
    'Toyota': ['Yaris', 'Corolla', 'RAV4', 'C-HR'],
    'Nissan': ['Qashqai', 'Juke', 'Micra'],
    'BMW': ['Serie 1', 'Serie 3', 'X1', 'X3'],
    'Mercedes': ['Classe A', 'Classe C', 'GLA'],
    'Audi': ['A3', 'A4', 'Q2', 'Q3']
}

PRENOMS_H = ['Jean', 'Pierre', 'Michel', 'Alain', 'Bernard', 'Christian', 'Daniel', 'François', 'Gérard', 'Laurent']
PRENOMS_F = ['Marie', 'Christine', 'Catherine', 'Patricia', 'Nathalie', 'Sylvie', 'Nicole', 'Monique', 'Isabelle', 'Véronique']
NOMS = ['Dupont', 'Martin', 'Bernard', 'Thomas', 'Robert', 'Durand', 'Lefebvre', 'Moreau', 'Simon', 'Laurent', 'Leroy', 'Rousseau', 'Girard', 'Fontaine', 'Chevalier', 'Roussel', 'Bouvier', 'Garnier', 'Charles', 'Muller']

ADRESSE_RUES = ['Rue de la Paix', 'Avenue Victor Hugo', 'Rue Jean Jaurès', 'Avenue des Champs-Élysées', 'Rue du Faubourg Saint-Antoine', 'Boulevard Saint-Michel', 'Rue de Rivoli', 'Avenue Foch', 'Rue du Commerce', 'Place de la République']

VILLES = ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice', 'Nantes', 'Strasbourg', 'Bordeaux', 'Lille', 'Rennes']

TEACHERS = [
    {'nom': 'Petit', 'prenom': 'Christophe'},
    {'nom': 'Blanchard', 'prenom': 'Fabien'}
]

CLIENTS_DATA = []
for i in range(20):
    genre = random.choice(['M', 'F'])
    if genre == 'M':
        prenom = random.choice(PRENOMS_H)
    else:
        prenom = random.choice(PRENOMS_F)
    nom = random.choice(NOMS)
    CLIENTS_DATA.append({'prenom': prenom, 'nom': nom})

def generate_phone():
    return f"06{random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}"

def generate_immat():
    lettres = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    partie1 = ''.join(random.choices(lettres, k=2))
    chiffres = ''.join(random.choices('0123456789', k=3))
    partie2 = ''.join(random.choices(lettres, k=2))
    return f"{partie1}-{chiffres}-{partie2}"

def populate():
    with app.app_context():
        print("=== Population de la base de donnees de test ===")
        
        # Creer les enseignants
        print("\n1. Ajout des enseignants...")
        for t in TEACHERS:
            existing = Enseignant.query.filter_by(nom=t['nom'], prenom=t['prenom']).first()
            if not existing:
                ens = Enseignant(nom=t['nom'], prenom=t['prenom'], actif=True)
                db.session.add(ens)
                print(f"   - {t['prenom']} {t['nom']}")
        db.session.commit()
        
        # Creer les clients et vehicules
        print("\n2. Ajout des clients et vehicules...")
        for i, c_data in enumerate(CLIENTS_DATA):
            existing_client = Client.query.filter_by(nom=c_data['nom'], prenom=c_data['prenom']).first()
            if existing_client:
                client = existing_client
                print(f"   Client existant: {client.prenom} {client.nom}")
            else:
                client = Client(
                    nom=c_data['nom'],
                    prenom=c_data['prenom'],
                    adresse=f"{random.randint(1, 150)} {random.choice(ADRESSE_RUES)}, {random.randint(1000, 99999)} {random.choice(VILLES)}",
                    telephone=generate_phone(),
                    email=f"{c_data['prenom'].lower()}.{c_data['nom'].lower()}@email.fr"
                )
                db.session.add(client)
                db.session.flush()
                print(f"   - Client {i+1}: {client.prenom} {client.nom}")
            
            nb_vehicules = random.randint(1, 2)
            for j in range(nb_vehicules):
                marque = random.choice(MARQUES)
                modele = random.choice(MODELES.get(marque, ['Modele']))
                
                immat = generate_immat()
                while Vehicule.query.filter_by(immatriculation=immat).first():
                    immat = generate_immat()
                
                vehicule = Vehicule(
                    immatriculation=immat,
                    marque=marque,
                    modele=modele,
                    annee=random.randint(2005, 2024),
                    couleur=random.choice(['Noir', 'Blanc', 'Gris', 'Bleu', 'Rouge', 'Vert']),
                    kilometrage=random.randint(10000, 200000),
                    proprietaire_id=client.id
                )
                db.session.add(vehicule)
                print(f"      Vehicule: {immat} - {marque} {modele}")
        
        db.session.commit()
        
        print(f"\n=== Resume ===")
        print(f"Clients: {Client.query.count()}")
        print(f"Vehicules: {Vehicule.query.count()}")
        print(f"Enseignants: {Enseignant.query.count()}")
        print("\nDonnees de test ajoutees avec succes!")

if __name__ == '__main__':
    populate()