import random
import datetime
import mysql.connector
from typing import List, Dict, Optional
from flask import Flask, render_template, redirect, session, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from datetime import datetime 
from math import ceil
from flask import jsonify
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']

# Configuration MySQL
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="Agricul"
    )

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Tables (inchangées)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(20),
            password VARCHAR(255) NOT NULL,
            role ENUM('user', 'admin') DEFAULT 'user' NOT NULL
        )
        """)
        # ... (autres tables inchangées)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recoltes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            plante_id INT NOT NULL,
            quantite DECIMAL(10,2) NOT NULL,
            date_recolte DATE NOT NULL,
            qualite VARCHAR(50) NOT NULL,
            FOREIGN KEY (plante_id) REFERENCES plantes(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type_plante VARCHAR(50) NOT NULL,
            quantite DECIMAL(10,2) NOT NULL DEFAULT 0,
            date_recolte DATE NOT NULL,
            prix_base DECIMAL(10,2) NOT NULL,
            qualite VARCHAR(50) NOT NULL DEFAULT 'bonne',
            plante_id INT NOT NULL,
            FOREIGN KEY (plante_id) REFERENCES plantes(id) ON DELETE CASCADE,
            INDEX (type_plante),
            INDEX (date_recolte)
        ) ENGINE=InnoDB
    """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            recolte_id INT NOT NULL,
            date_vente DATE NOT NULL,
            quantite DECIMAL(10,2) NOT NULL,
            prix_unitaire DECIMAL(10,2) NOT NULL,
            montant_total DECIMAL(10,2) NOT NULL,
            client VARCHAR(100),
            FOREIGN KEY (recolte_id) REFERENCES recoltes(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""
                        
        CREATE TABLE IF NOT EXISTS message(
            id INT AUTO_INCREMENT PRIMARY KEY,
            nom VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            options VARCHAR(20),
            message TEXT NOT NULL,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP        
        )
        """)

        
        
        db.commit()

init_db()

# Routes d'authentification modifiées
@app.route('/Login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        passwordcf = request.form['passwordcf']
        
        if password != passwordcf:
            flash("Les mots de passe ne correspondent pas", 'error')
            return redirect(url_for('login'))
            
        hashed_password = generate_password_hash(password)
        
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, phone, password, role) VALUES (%s, %s, %s, %s,'user')",
                (name, email, phone, hashed_password)
            )
            db.commit()
            
            # NE PAS connecter automatiquement, juste rediriger vers inscription
            flash("Inscription réussie! Veuillez vous connecter.", 'success')
            return redirect(url_for('inscription'))  # Redirection vers la page inscription/connexion
            
        except mysql.connector.IntegrityError:
            flash("Nom d'utilisateur ou email déjà existant", 'error')
        finally:
            cursor.close() if 'cursor' in locals() else None
    
    return render_template('Login.html')

@app.route('/Contactez_nous', methods=['GET', 'POST'])
def Contactez_nous():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        options = request.form.get('options')
        message = request.form.get('message')

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO message (nom, email, options, message) VALUES (%s, %s, %s, %s)", 
                (nom, email, options, message)
            )
            db.commit()  # Correction: "commit" au lieu de "comit"
            flash("Votre message a été envoyé avec succès!", 'success')
            return redirect(url_for('Contactez_nous'))
        except mysql.connector.Error as err:  # Gestion plus large des erreurs
            flash(f"Une erreur s'est produite: {err}", 'error')
            db.rollback()  # Annulation des changements en cas d'erreur
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()
        
    return render_template('Contactez_nous.html')

    # Recupreation des données dans le dashboard
@app.route('/Dashboard/dashboard')
def dash():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    TOTAL_KEY = 'total'

    try:
        # Requêtes SQL
        cursor.execute("SELECT COUNT(*) AS total FROM plantes")
        nombre_plantes = cursor.fetchone()[TOTAL_KEY]

        cursor.execute("SELECT COUNT(*) AS total FROM parcelles")
        nombre_parcelles = cursor.fetchone()[TOTAL_KEY]

        cursor.execute("SELECT COUNT(*) AS total FROM plantes WHERE est_recoltee = 1")
        nombre_recoltees = cursor.fetchone()[TOTAL_KEY]

        cursor.execute("SELECT COALESCE(SUM(prix_total), 0) AS total FROM ventes")
        somme_vendue = round(cursor.fetchone()[TOTAL_KEY], 2)

        cursor.execute("SELECT COALESCE(SUM(quantite), 0) AS total FROM stock")
        stock_disponible = cursor.fetchone()[TOTAL_KEY]

        return render_template(
            '/Dashboard/dashboard.html',
            nombre_plantes=nombre_plantes,
            nombre_parcelles=nombre_parcelles,
            nombre_recoltees=nombre_recoltees,
            somme_vendue=somme_vendue,
            stock_disponible=stock_disponible,
            user_name=session.get('user_name')
        )

    except Exception as e:
        print(f"Database error: {e}")
        return "Une erreur est survenue", 500
        
    finally:
        cursor.close()
        db.close()

@app.route('/Dashboard/message')
def message():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)  # Utilisez dictionary=True pour obtenir des résultats sous forme de dictionnaires
        
        # Récupérer tous les messages
        cursor.execute("SELECT * FROM message ORDER BY id DESC")  # Trie par  'id' 
        messages = cursor.fetchall()
        
        return render_template('Dashboard/message.html', messages=messages)
    except mysql.connector.Error as err:
        flash(f"Erreur lors de la récupération des messages: {err}", 'error')
        return redirect(url_for('dashboard'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/Inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['user_role'] = user['role']  # Stocker le rôle dans la session
            session['logged_in'] = True
            
            # Redirection en fonction du rôle
            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('index'))  # Rediriger les utilisateurs normaux vers les produits
        
        flash("Email ou mot de passe incorrect", 'error')
    
    return render_template('Inscription.html')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('user_role') != 'admin':
            flash("Accès refusé - Admin requis", 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Récupérer le nom de l'utilisateur depuis la session
    user_name = session.get('user_name', 'Utilisateur')
    
    return render_template('Dashboard/dashboard.html', 
                         user_name=user_name,
                         user_data=session)
# Telecharger Rapport 
from flask import make_response
from reportlab.pdfgen import canvas
import io
from datetime import datetime

from flask import make_response
from reportlab.lib.pagesizes import letter  
from reportlab.pdfgen import canvas
import io
from datetime import datetime

@app.route('/download_report')
def download_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Récupération des données avec les bons noms de colonnes
        cursor.execute("SELECT COUNT(*) AS total FROM plantes")
        plantes = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) AS total FROM parcelles")
        parcelles = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) AS total FROM plantes WHERE est_recoltee = 1")
        recoltes = cursor.fetchone()['total']
        
        # CORRECTION: Utilisation de 'montant'
        cursor.execute("SELECT COALESCE(SUM(montant), 0) AS total FROM ventes")
        ventes = cursor.fetchone()['total']
        
        cursor.execute("SELECT COALESCE(SUM(quantite), 0) AS total FROM stock")
        stock = cursor.fetchone()['total']
        
        # Création du PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # En-tête
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, "Rapport d'Activités D'AGRICONNECT")
        p.setFont("Helvetica", 12)
        p.drawString(100, 730, f"Date du rapport: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        # Contenu
        y_position = 700
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, y_position, "Statistiques Globales:")
        y_position -= 30
        
        stats = [
            ("Plantes cultivées", plantes),
            ("Parcelles exploitées", parcelles),
            ("Plantes récoltées", recoltes),
            ("Chiffre d'affaires", f"{ventes} FCFA"),  # Montant total des ventes
            ("Stock disponible", f"{stock} unités")
        ]
        
        p.setFont("Helvetica", 12)
        for stat in stats:
            p.drawString(120, y_position, f"{stat[0]}: {stat[1]}")
            y_position -= 20
        
        # Pied de page
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(100, 50, "Généré automatiquement par le système de gestion agricole")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=rapport_agricole_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response

    except Exception as e:
        print(f"Erreur lors de la génération du rapport: {str(e)}")
        return "Une erreur est survenue lors de la génération du rapport", 500
        
    finally:
        cursor.close()
        db.close()
@app.route('/deconnexion/', methods=['POST'])
def deconnexion():
    session.clear()
    flash("Vous avez été déconnecté avec succès", 'info')
    return redirect(url_for('index'))

# Nombre de message reçu
@app.route('/get_message_count')
def get_message_count():
    if not session.get('logged_in'):
        return jsonify({'count': 0})
    
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM message")  
        count = cursor.fetchone()[0]
        return jsonify({'count': count})
    except Exception as e:
        app.logger.error(f"Erreur récupération nombre messages: {str(e)}")
        return jsonify({'count': 0})
    finally:
        cursor.close()
        db.close()

# Routes principales avec passage du nom d'utilisateur
@app.route('/')
def index():
    user_name = session.get('user_name') if session.get('logged_in') else None
    return render_template('home.html', user_name=user_name)

@app.route('/produits/')
def produits():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('/Dashboard/Tomates.html', user_name=session.get('user_name'))


# Ajouter plantes
@app.route('/plantes/Ad_plantes/', methods=['GET', 'POST'])
def Ajouter():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            # Récupération des données du formulaire
            parcelle_id = request.form['parcelle_id']  # Champ requis
            type_plante = request.form['type_plante']  # Champ requis
            date_plantation = request.form['date_plantation']  # Champ requis
            date_recolte = request.form.get('date_recolte')  # Optionnel
            croissance = int(request.form.get('croissance', 0))  # Valeur par défaut 0
            sante = request.form.get('sante', 'bonne')  # Valeur par défaut 'bonne'
            est_recoltee = 1 if request.form.get('est_recoltee') == 'on' else 0  # Checkbox

            # Validation des données
            if not parcelle_id or not type_plante or not date_plantation:
                flash('Veuillez remplir tous les champs obligatoires', 'danger')
                return redirect(url_for('Ajouter'))

            # Insertion dans la base de données
            cursor.execute("""
                INSERT INTO plantes 
                (parcelle_id, type_plante, date_plantation, date_recolte, 
                 croissance, sante, est_recoltee)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (parcelle_id, type_plante, date_plantation, date_recolte, 
                  croissance, sante, est_recoltee))
            
            db.commit()
            flash('Plante ajoutée avec succès!', 'success')
            return redirect(url_for('plantes'))

        # Pour la méthode GET - Récupération des parcelles disponibles
        cursor.execute("SELECT id, taille FROM parcelles ORDER BY id")
        parcelles = cursor.fetchall()

        return render_template('/Dashboard/Ad_plantes.html',
                            parcelles=parcelles,
                            date_aujourdhui=datetime.now().strftime('%Y-%m-%d'))

    except ValueError as e:
        db.rollback()
        flash('Valeur incorrecte pour la croissance', 'danger')
        return redirect(url_for('Ajouter'))
    except Exception as e:
        db.rollback()
        app.logger.error(f"Erreur lors de l'ajout: {str(e)}")
        flash("Une erreur s'est produite lors de l'ajout", 'danger')
        return redirect(url_for('Ajouter'))
    finally:
        cursor.close()
        db.close()


@app.route('/Dashboard/plantes/')
def Plantes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # Paramètres de pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre d'éléments par page

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # Compter le nombre total de plantes
        cursor.execute("SELECT COUNT(*) as total FROM plantes")
        total_plantes = cursor.fetchone()['total']
        total_pages = ceil(total_plantes / per_page)

        # Récupérer les plantes pour la page courante
        offset = (page - 1) * per_page
        cursor.execute("""
            SELECT p.id, p.type_plante, p.date_plantation, p.date_recolte,
                   p.croissance, p.sante, p.est_recoltee,
                   parc.id as parcelle_id
            FROM plantes p
            JOIN parcelles parc ON p.parcelle_id = parc.id
            ORDER BY p.date_plantation DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        plantes_data = cursor.fetchall()

        return render_template('/Dashboard/plantes.html',
                            plantes=plantes_data,
                            page=page,
                            total_pages=total_pages,
                            total_items=total_plantes,
                            user_name=session.get('user_name'))

    except Exception as e:
        app.logger.error(f"Erreur: {str(e)}")
        return render_template('error.html', message="Erreur de chargement"), 500
    finally:
        cursor.close()
        db.close()
# Routes pour plantes et parcelles avec utilisateur
@app.route('/Dashboard/plantes/')
def plantes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT pl.id, pl.type_plante, pl.date_plantation, pl.date_recolte,
               pl.croissance, pl.sante, pl.est_recoltee,
               p.id as parcelle_id, p.taille as parcelle_taille
        FROM plantes pl
        JOIN parcelles p ON pl.parcelle_id = p.id
        ORDER BY pl.date_plantation DESC
    """)
    plantes_data = cursor.fetchall()
    cursor.close()
    
    return render_template('Dashboard/plantes.html', 
                         plantes=plantes_data,
                         user_name=session.get('user_name'))


@app.route('/Parcelle/Ad_parcelle/', methods=['GET', 'POST'])
def ajouter_parcelle():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        db = None
        cursor = None
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Récupération de la taille
            taille = float(request.form['taille'])
            
            # Insertion (l'id est auto-incrémenté)
            cursor.execute("INSERT INTO parcelles (taille) VALUES (%s)", (taille,))
            
            db.commit()
            flash('Parcelle ajoutée avec succès!', 'success')
            return redirect(url_for('parcelle'))
            
        except ValueError as e:
            app.logger.error(f"Erreur de valeur: {str(e)}")
            flash('Veuillez entrer une taille valide (nombre positif)', 'danger')
        except Exception as e:
            if db:
                db.rollback()
            app.logger.error(f"Erreur ajout parcelle: {str(e)}")
            flash("Erreur lors de l'ajout", 'danger')
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    return render_template('/Dashboard/Ad_parcelle.html',
                         user_name=session.get('user_name'))
 # Données aleatoires 
from datetime import datetime
@app.route('/Dashboard/ventes', methods=['GET', 'POST'])
def ventes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Récupérer les plantes disponibles
    cursor.execute("SELECT DISTINCT type_plante FROM plantes WHERE est_recoltee = 1")
    types_plantes = [p['type_plante'] for p in cursor.fetchall()]

    if request.method == 'POST':
        try:
            date_vente = request.form['date_vente']
            type_plante = request.form['type_plante']
            quantite = float(request.form['quantite'])
            montant = float(request.form['montant'])

            cursor.execute("""
                INSERT INTO ventes (date_vente, type_plante, quantite, montant)
                VALUES (%s, %s, %s, %s)
            """, (date_vente, type_plante, quantite, montant))
            
            db.commit()
            flash('Vente enregistrée avec succès!', 'success')
            return redirect(url_for('ventes'))

        except ValueError:
            flash('Veuillez entrer des valeurs numériques valides', 'danger')
        except Exception as e:
            db.rollback()
            flash(f"Erreur: {str(e)}", 'danger')

    # Récupérer l'historique
    cursor.execute("""
        SELECT id, date_vente, type_plante, quantite, montant 
        FROM ventes 
        ORDER BY date_vente DESC
    """)
    ventes_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('/Dashboard/ventes.html',
                         types_plantes=types_plantes,
                         ventes=ventes_data,
                         user_name=session.get('user_name'))



    # Stock
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import check_password_hash

@app.route('/Dashboard/stock', methods=['GET', 'POST'])
def gestion_stock():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 1. Récupération des plantes disponibles avec leurs quantités totales
        cursor.execute("""
            SELECT 
                p.id AS plante_id,
                p.type_plante,
                COALESCE(SUM(r.quantite), 0) AS quantite_totale
            FROM plantes p
            LEFT JOIN recoltes r ON p.id = r.plante_id
            WHERE p.est_recoltee = 1
            GROUP BY p.id, p.type_plante
            HAVING quantite_totale > 0
            ORDER BY p.type_plante
        """)
        plantes_disponibles = cursor.fetchall()

        # 2. Récupération des dates de récolte valides par type de plante
        cursor.execute("""
            SELECT p.type_plante, r.date_recolte
            FROM recoltes r
            JOIN plantes p ON r.plante_id = p.id
            WHERE p.est_recoltee = 1
        """)
        recoltes = cursor.fetchall()

        from collections import defaultdict
        dates_par_plante = defaultdict(list)
        for r in recoltes:
            dates_par_plante[r['type_plante']].append(r['date_recolte'].strftime('%Y-%m-%d'))

        # 3. Gestion du formulaire
        if request.method == 'POST':
            type_plante = request.form['type_plante']
            quantite = float(request.form['quantite'])
            qualite = request.form['qualite']
            prix_base = float(request.form['prix_base'])
            date_recolte = request.form['date_recolte']

            # Vérification de la quantité disponible pour cette date
            cursor.execute("""
                SELECT COALESCE(SUM(r.quantite), 0) AS quantite_dispo
                FROM recoltes r
                JOIN plantes p ON r.plante_id = p.id
                WHERE p.type_plante = %s AND p.est_recoltee = 1
                AND r.date_recolte = %s
            """, (type_plante, date_recolte))
            quantite_dispo = cursor.fetchone()['quantite_dispo']

            if quantite > quantite_dispo:
                flash(f"Quantité insuffisante! Disponible: {quantite_dispo} kg", 'danger')
            else:
                # Insertion dans le stock
                cursor.execute("""
                    INSERT INTO stock (
                        type_plante, quantite, date_recolte, prix_base, qualite, plante_id
                    ) VALUES (%s, %s, %s, %s, %s,
                        (SELECT id FROM plantes WHERE type_plante = %s LIMIT 1)
                    )
                """, (type_plante, quantite, date_recolte, prix_base, qualite, type_plante))

                db.commit()
                flash('Stock mis à jour avec succès!', 'success')
                return redirect(url_for('gestion_stock'))

        # 4. Récupération du stock actuel
        cursor.execute("""
            SELECT 
                s.id, s.type_plante, s.qualite, s.prix_base,
                s.date_recolte, s.quantite,
                (s.quantite - COALESCE(
                    (SELECT SUM(v.quantite) 
                     FROM ventes v 
                     WHERE v.type_plante = s.type_plante
                     AND v.date_vente >= s.date_recolte
                ), 0)) AS quantite_restante
            FROM stock s
            ORDER BY s.date_recolte DESC
        """)
        stock_data = cursor.fetchall()

        return render_template(
            '/Dashboard/stock.html',
            plantes_disponibles=plantes_disponibles,
            stock=stock_data,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            user_name=session.get('user_name'),
            dates_par_plante=dict(dates_par_plante)  # pour le JS dynamique
        )

    except ValueError:
        flash('Veuillez entrer des valeurs numériques valides', 'danger')
    except Exception as e:
        db.rollback()
        flash(f"Erreur: {str(e)}", 'danger')
    finally:
        cursor.close()
        db.close()
@app.route('/Dashboard/recoltes/', methods=['GET', 'POST'])
def recoltes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 1. Récupération des plantes NON récoltées (pour le formulaire)
        cursor.execute("""
            SELECT id, type_plante
            FROM plantes
            WHERE est_recoltee = 0
            ORDER BY type_plante
        """)
        plantes_non_recoltees = cursor.fetchall()

        # 2. Récupération des plantes DÉJÀ récoltées (pour affichage)
        cursor.execute("""
            SELECT 
                p.id,
                p.type_plante,
                SUM(r.quantite) AS quantite_totale,
                MAX(r.date_recolte) AS derniere_recolte
            FROM plantes p
            JOIN recoltes r ON p.id = r.plante_id
            WHERE p.est_recoltee = 1
            GROUP BY p.id, p.type_plante
            ORDER BY derniere_recolte DESC
        """)
        plantes_recoltees = cursor.fetchall()

        # 3. Traitement du formulaire
        if request.method == 'POST':
            plante_id = request.form['plante_id']
            quantite = float(request.form['quantite'])
            date_recolte = request.form['date_recolte'] or datetime.now().date()
            qualite = request.form['qualite']

            # Validation
            if quantite <= 0:
                flash("La quantité doit être positive", "danger")
                return redirect(url_for('recoltes'))

            # Insertion
            cursor.execute("""
                INSERT INTO recoltes 
                (plante_id, quantite, date_recolte, qualite)
                VALUES (%s, %s, %s, %s)
            """, (plante_id, quantite, date_recolte, qualite))

            # Mise à jour du statut
            cursor.execute("""
                UPDATE plantes 
                SET est_recoltee = 1 
                WHERE id = %s
            """, (plante_id,))

            db.commit()
            flash("Récolte enregistrée avec succès!", "success")
            return redirect(url_for('recoltes'))

        # 4. Historique complet des récoltes
        cursor.execute("""
            SELECT 
                r.id, 
                p.type_plante,
                r.quantite,
                r.date_recolte,
                r.qualite,
                (SELECT COUNT(*) FROM stock WHERE plante_id = p.id) AS en_stock
            FROM recoltes r
            JOIN plantes p ON r.plante_id = p.id
            ORDER BY r.date_recolte DESC
            LIMIT 50
        """)
        historique = cursor.fetchall()

        return render_template(
            '/Dashboard/recoltes.html',
            plantes=plantes_non_recoltees,
            recoltees=plantes_recoltees,
            historique=historique,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            user_name=session.get('user_name')
        )

    except ValueError:
        flash("Valeurs numériques invalides", "danger")
        return redirect(url_for('recoltes'))
    except Exception as e:
        db.rollback()
        flash(f"Erreur technique: {str(e)}", "danger")
        app.logger.error(f"Erreur dans recoltes(): {str(e)}")
        return redirect(url_for('recoltes'))
    finally:
        cursor.close()
        db.close()


@app.route('/Dashboard/parcelles')
def parcelles():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # Debug: Vérifier la connexion
        app.logger.info("Connexion à la base de données établie")
        
        # Requête pour les parcelles
        cursor.execute("SELECT id, taille FROM parcelles ORDER BY id")
        parcelles_base = cursor.fetchall()
        app.logger.info(f"Parcelles récupérées: {parcelles_base}")  # Debug
        
        # Requête pour les plantes
        cursor.execute("""
            SELECT parcelle_id, type_plante as type, sante, date_plantation 
            FROM plantes
        """)
        plantes = cursor.fetchall()
        app.logger.info(f"Plantes récupérées: {plantes}")  # Debug
        
        # Organisation des données
        parcelles_organisees = []
        for parcelle in parcelles_base:
            plantes_parcelle = [p for p in plantes if p['parcelle_id'] == parcelle['id']]
            parcelles_organisees.append({
                'id': parcelle['id'],
                'taille': parcelle['taille'],
                'plantes': plantes_parcelle
            })
        
        app.logger.info(f"Données organisées: {parcelles_organisees}")  # Debug
        
        return render_template(
            'Dashboard/parcelles.html',
            parcelles=parcelles_organisees,
            user_name=session.get('user_name')
        )
    
    except Exception as e:
        app.logger.error(f"Erreur dans la route parcelles: {str(e)}", exc_info=True)
        return render_template('error.html', message="Une erreur s'est produite"), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()


            # Parties Vantes
@app.route('/Dashboard/ventes', methods=['GET', 'POST'])
def gestion_ventes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = BaseDeDonnees()
    
    if request.method == 'POST':
        recolte_id = int(request.form['recolte_id'])
        quantite = float(request.form['quantite'])
        prix = float(request.form['prix'])
        client = request.form.get('client', '')

        if db.ajouter_vente(recolte_id, quantite, prix, client):
            flash("Vente enregistrée avec succès!", 'success')
        else:
            flash("Erreur: quantité indisponible ou problème d'enregistrement", 'error')

    # Récupérer les données pour l'affichage
    recoltes_disponibles = db.get_recoltes_disponibles()
    historique_ventes = db.get_historique_ventes()
    db.fermer()

    return render_template('Dashboard/ventes.html',
                         recoltes=recoltes_disponibles,
                         ventes=historique_ventes,
                         user_name=session.get('user_name'))
class Plante:
    def __init__(self, type_plante: str, date_plantation: datetime.date):
        self.type_plante = type_plante
        self.date_plantation = date_plantation
        self.date_recolte = None
        self.croissance = 0.0
        self.sante = 100.0
        self.est_recoltee = False

class Parcelle:
    def __init__(self, id: int, taille: float):
        self.id = id
        self.taille = taille
        self.plantes: List[Plante] = []

class Produit:
    def __init__(self, type_plante: str, qualite: float, prix_base: float):
        self.type_plante = type_plante              # ex : "Tomate", "Pomme de terre"
        self.qualite = qualite                      # pourcentage ou note de qualité (ex : 85.0)
        self.prix_base = prix_base                  # prix de base par unité (kg, pièce, etc.)
        self.date_recolte: Optional[datetime.date] = None  # date de la récolte

class Vente:
    def __init__(self):
        self.ventes_realisees: List[Dict[str, any]] = []
        self.stock: Dict[str, List[Produit]] = {}

class BaseDeDonnees:
    """Gère la persistance des données dans MySQL"""
    def __init__(self):
        self.conn = get_db()
    
    def sauvegarder_parcelle(self, parcelle: Parcelle):
        """Sauvegarde une parcelle et ses plantes"""
        cursor = self.conn.cursor()
        
        # Sauvegarder la parcelle
        cursor.execute(
            "REPLACE INTO parcelles (id, taille) VALUES (%s, %s)",
            (parcelle.id, parcelle.taille)
        )
        
        # Supprimer les plantes existantes pour cette parcelle
        cursor.execute(
            "DELETE FROM plantes WHERE parcelle_id = %s",
            (parcelle.id,)
        )
        
        # Sauvegarder les plantes
        for plante in parcelle.plantes:
            cursor.execute(
                """INSERT INTO plantes (
                    parcelle_id, type_plante, date_plantation, date_recolte,
                    croissance, sante, est_recoltee
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    parcelle.id, plante.type_plante, plante.date_plantation.isoformat(),
                    plante.date_recolte.isoformat() if plante.date_recolte else None,
                    plante.croissance, plante.sante, int(plante.est_recoltee)
                )
            )
        
        self.conn.commit()
    
    def charger_parcelles(self) -> List[Parcelle]:
        """Charge toutes les parcelles depuis la base de données"""
        cursor = self.conn.cursor(dictionary=True)
        parcelles = []
        
        # Charger les parcelles
        cursor.execute("SELECT id, taille FROM parcelles")
        for row in cursor.fetchall():
            parcelle_id, taille = row['id'], row['taille']
            parcelle = Parcelle(parcelle_id, taille)
            
            # Charger les plantes de cette parcelle
            cursor.execute(
                """SELECT type_plante, date_plantation, date_recolte,
                          croissance, sante, est_recoltee
                FROM plantes WHERE parcelle_id = %s""",
                (parcelle_id,)
            )
            
            for plante_row in cursor.fetchall():
                plante = Plante(
                    plante_row['type_plante'],
                    datetime.date.fromisoformat(plante_row['date_plantation'])
                )
                plante.croissance = plante_row['croissance']
                plante.sante = plante_row['sante']
                plante.est_recoltee = bool(plante_row['est_recoltee'])
                if plante_row['date_recolte']:
                    plante.date_recolte = datetime.date.fromisoformat(plante_row['date_recolte'])
                parcelle.plantes.append(plante)
            
            parcelles.append(parcelle)
        
        return parcelles
    
    def sauvegarder_vente(self, vente: Vente):
        """Sauvegarde les ventes et le stock"""
        cursor = self.conn.cursor()
        
        # Vider les tables existantes
        cursor.execute("DELETE FROM ventes")
        cursor.execute("DELETE FROM stock")
        
        # Sauvegarder les ventes
        for v in vente.ventes_realisees:
            cursor.execute(
                "INSERT INTO ventes (date_vente, type_plante, quantite, montant) VALUES (%s, %s, %s, %s)",
                (v['date'].isoformat(), v['type'], v['quantite'], v['montant'])
            )
        
        # Sauvegarder le stock
        for type_plante, produits in vente.stock.items():
            for produit in produits:
                cursor.execute(
                    "INSERT INTO stock (type_plante, qualite, prix_base, date_recolte) VALUES (%s, %s, %s, %s)",
                    (produit.type_plante, produit.qualite, produit.prix_base, produit.date_recolte.isoformat())
                )
        
        self.conn.commit()
    
    def charger_vente(self) -> Vente:
        """Charge les données de vente depuis la base"""
        cursor = self.conn.cursor(dictionary=True)
        vente = Vente()
        
        # Charger les ventes
        cursor.execute("SELECT date_vente, type_plante, quantite, montant FROM ventes")
        for row in cursor.fetchall():
            vente.ventes_realisees.append({
                'date': datetime.date.fromisoformat(row['date_vente']),
                'type': row['type_plante'],
                'quantite': row['quantite'],
                'montant': row['montant']
            })
        
        # Charger le stock
        cursor.execute("SELECT type_plante, qualite, prix_base, date_recolte FROM stock")
        for row in cursor.fetchall():
            produit = Produit(row['type_plante'], row['qualite'], row['prix_base'])
            produit.date_recolte = datetime.date.fromisoformat(row['date_recolte'])
            
            if row['type_plante'] not in vente.stock:
                vente.stock[row['type_plante']] = []
            vente.stock[row['type_plante']].append(produit)
        
        return vente
    
    def fermer(self):
        """Ferme la connexion à la base de données"""
        self.conn.close()

if __name__ == "__main__":
    app.run(debug=True)