"""
SERVEUR DE LICENCES STOCKPRO — Version Railway
===============================================
Hébergé en ligne 24h/24 sur Railway.app
Panel admin : https://TON-APP.railway.app/admin
"""

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from functools import wraps
import secrets, os

app = Flask(__name__)

# Railway fournit automatiquement DATABASE_URL et SECRET_KEY via les variables d'environnement
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stockpro-licence-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///licences.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Si PostgreSQL (Railway), corriger le préfixe
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)

# Mot de passe admin — défini via variable d'environnement sur Railway
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'stockpro_admin_2024')

# ─── MODÈLES ───────────────────────────────────────────────────────────────────

class Licence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cle = db.Column(db.String(64), unique=True, nullable=False)
    client_nom = db.Column(db.String(100), nullable=False)
    client_telephone = db.Column(db.String(50))
    client_ville = db.Column(db.String(100))
    client_secteur = db.Column(db.String(100))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_expiration = db.Column(db.Date, nullable=False)
    statut = db.Column(db.String(20), default='active')
    montant_mensuel = db.Column(db.Integer, default=25000)
    notes = db.Column(db.Text)
    derniere_verification = db.Column(db.DateTime)
    nb_verifications = db.Column(db.Integer, default=0)
    ip_derniere = db.Column(db.String(50))

    def jours_restants(self):
        return max(0, (self.date_expiration - date.today()).days)

    def statut_display(self):
        if self.statut == 'suspendue': return 'SUSPENDUE'
        if self.date_expiration < date.today(): return 'EXPIREE'
        if self.jours_restants() <= 5: return 'EXPIRE BIENTOT'
        return 'ACTIVE'

# ─── UTILS ─────────────────────────────────────────────────────────────────────

def generer_cle():
    r = secrets.token_hex(8).upper()
    return f"SP-{r[:4]}-{r[4:8]}-{r[8:12]}-{r[12:16]}"

def admin_requis(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_connecte'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─── API VÉRIFICATION ──────────────────────────────────────────────────────────

@app.route('/api/verifier', methods=['POST'])
def verifier_licence():
    data = request.get_json()
    if not data or 'cle' not in data:
        return jsonify({'valide': False, 'message': 'Cle manquante'}), 400

    cle = data.get('cle', '').strip().upper()
    ip = request.remote_addr
    licence = Licence.query.filter_by(cle=cle).first()

    if not licence:
        return jsonify({
            'valide': False,
            'message': 'Licence inconnue. Contactez votre revendeur.',
            'jours_restants': 0
        })

    licence.derniere_verification = datetime.utcnow()
    licence.nb_verifications = (licence.nb_verifications or 0) + 1
    licence.ip_derniere = ip

    if licence.statut == 'suspendue':
        db.session.commit()
        return jsonify({
            'valide': False,
            'message': 'Licence suspendue. Contactez votre revendeur pour regulariser.',
            'jours_restants': 0,
            'suspendue': True
        })

    if licence.date_expiration < date.today():
        licence.statut = 'expiree'
        db.session.commit()
        return jsonify({
            'valide': False,
            'message': 'Licence expiree. Veuillez renouveler votre abonnement.',
            'jours_restants': 0,
            'expiree': True
        })

    jr = licence.jours_restants()
    db.session.commit()
    return jsonify({
        'valide': True,
        'message': f'Licence active - {jr} jour(s) restant(s)',
        'jours_restants': jr,
        'client': licence.client_nom,
        'expiration': licence.date_expiration.strftime('%d/%m/%Y')
    })

@app.route('/')
def index():
    return jsonify({
        'service': 'StockPro Licence Server',
        'version': '1.0',
        'status': 'running',
        'admin': '/admin'
    })

# ─── PANEL ADMIN ───────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>Admin — StockPro Licences</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e);display:flex;align-items:center;justify-content:center;min-height:100vh}.box{background:white;border-radius:20px;padding:48px 40px;width:420px;box-shadow:0 20px 60px rgba(0,0,0,0.3)}.logo{font-size:30px;font-weight:900;color:#16a085;margin-bottom:4px}.sub{font-size:13px;color:#9ca3af;margin-bottom:32px}label{font-size:12px;font-weight:700;color:#374151;display:block;margin-bottom:8px}input{width:100%;padding:12px 14px;border:1.5px solid #d1d5db;border-radius:10px;font-size:14px;margin-bottom:20px;transition:border .2s}input:focus{outline:none;border-color:#16a085}button{width:100%;padding:14px;background:#16a085;color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer}.err{background:#fee2e2;border-left:4px solid #ef4444;padding:12px;border-radius:8px;font-size:13px;color:#991b1b;margin-bottom:20px}</style>
</head><body><div class="box">
<div class="logo">StockPro</div><div class="sub">Serveur de licences — Panel Admin</div>
{% if erreur %}<div class="err">{{ erreur }}</div>{% endif %}
<form method="POST"><label>Mot de passe administrateur</label><input type="password" name="password" required autofocus placeholder="••••••••••"><button type="submit">Connexion →</button></form>
</div></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StockPro — Licences</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#f4f6fb}
.topbar{background:#1a1a2e;padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}
.brand{color:#16a085;font-size:20px;font-weight:900}
.brand span{color:rgba(255,255,255,.6);font-weight:400;font-size:13px;margin-left:10px}
.logout{color:rgba(255,255,255,.5);font-size:13px;text-decoration:none;padding:6px 12px;border:1px solid rgba(255,255,255,.2);border-radius:6px}
.content{padding:24px;max-width:1400px;margin:0 auto}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.metric{background:white;border-radius:12px;padding:20px;border:1px solid #e8ecf4}
.metric-label{font-size:12px;color:#6b7280;margin-bottom:8px;font-weight:500}
.metric-value{font-size:26px;font-weight:800;color:#1a1a2e}
.green{color:#059669}.red{color:#dc2626}.blue{color:#2563eb}
.card{background:white;border-radius:14px;border:1px solid #e8ecf4;padding:22px;margin-bottom:20px}
.card-title{font-size:15px;font-weight:700;color:#1a1a2e;margin-bottom:18px}
.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.fg{display:flex;flex-direction:column;gap:5px}
.fg.full{grid-column:1/-1}
label{font-size:12px;font-weight:600;color:#374151}
input,select{padding:9px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:13px;width:100%}
input:focus,select:focus{outline:none;border-color:#16a085}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:10px 12px;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #e8ecf4;background:#f8fafc;white-space:nowrap}
td{padding:11px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:last-child td{border-bottom:none}tr:hover td{background:#fafbfc}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700}
.b-ok{background:#d1fae5;color:#065f46}.b-sus{background:#fee2e2;color:#991b1b}
.b-exp{background:#f3f4f6;color:#6b7280}.b-warn{background:#fef3c7;color:#92400e}
.btn{display:inline-flex;align-items:center;padding:7px 14px;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid #d1d5db;background:white;color:#374151;text-decoration:none;margin-right:4px;white-space:nowrap}
.btn-green{background:#16a085;color:white;border-color:#16a085}
.btn-red{background:#ef4444;color:white;border-color:#ef4444}
.btn-orange{background:#f59e0b;color:white;border-color:#f59e0b}
.flash{padding:14px 18px;border-radius:10px;margin-bottom:20px;font-size:13px;font-weight:600;display:flex;align-items:center;gap:10px}
.flash-ok{background:#d1fae5;color:#065f46;border:1px solid #6ee7b7}
.cle-section{background:#f0fdf9;border:2px solid #16a085;border-radius:12px;padding:20px;margin-bottom:20px}
.cle-label{font-size:13px;font-weight:700;color:#065f46;margin-bottom:10px}
.cle-val{font-family:monospace;font-size:22px;font-weight:900;color:#065f46;letter-spacing:3px;background:white;padding:14px 20px;border-radius:8px;border:1px dashed #16a085;text-align:center;margin-bottom:10px}
.cle-hint{font-size:12px;color:#6b7280}
</style></head><body>
<div class="topbar">
  <div class="brand">StockPro <span>Serveur de Licences</span></div>
  <a href="/admin/logout" class="logout">⏻ Déconnexion</a>
</div>
<div class="content">

{% if flash_msg %}
<div class="flash flash-ok">✓ {{ flash_msg }}</div>
{% endif %}

{% if nouvelle_cle %}
<div class="cle-section">
  <div class="cle-label">✓ Licence créée pour {{ nouvelle_cle_client }}</div>
  <div class="cle-val" id="cle-display">{{ nouvelle_cle }}</div>
  <div style="text-align:center;margin-bottom:10px">
    <button class="btn btn-green" onclick="copier()">📋 Copier la clé</button>
  </div>
  <div class="cle-hint">⚠ Donnez cette clé au client pour activer StockPro. Elle ne s'affiche qu'une seule fois ici.</div>
</div>
{% endif %}

<div class="metrics">
  <div class="metric"><div class="metric-label">Total clients</div><div class="metric-value">{{ total }}</div></div>
  <div class="metric"><div class="metric-label">Licences actives</div><div class="metric-value green">{{ actives }}</div></div>
  <div class="metric"><div class="metric-label">Suspendues / Expirées</div><div class="metric-value red">{{ inactives }}</div></div>
  <div class="metric"><div class="metric-label">CA mensuel estimé</div><div class="metric-value blue">{{ ca_mensuel }} FCFA</div></div>
</div>

<div class="card">
  <div class="card-title">➕ Créer une nouvelle licence</div>
  <form method="POST" action="/admin/creer">
    <div class="form-grid">
      <div class="fg"><label>Nom du client *</label><input type="text" name="client_nom" required placeholder="Nom ou raison sociale"></div>
      <div class="fg"><label>Téléphone</label><input type="text" name="client_telephone" placeholder="+228..."></div>
      <div class="fg"><label>Ville</label><input type="text" name="client_ville" placeholder="Lomé, Kara, Sokodé..."></div>
      <div class="fg"><label>Secteur d'activité</label>
        <select name="client_secteur">
          <option>Quincaillerie</option><option>Pharmacie</option><option>Alimentaire</option>
          <option>Commerce général</option><option>BTP / Matériaux</option>
          <option>Informatique</option><option>Mode / Textile</option>
          <option>Agriculture</option><option>Autre</option>
        </select>
      </div>
      <div class="fg"><label>Durée de la licence</label>
        <select name="duree_mois">
          <option value="1">1 mois</option><option value="3">3 mois</option>
          <option value="6">6 mois</option><option value="12" selected>12 mois</option>
        </select>
      </div>
      <div class="fg"><label>Montant mensuel (FCFA)</label><input type="number" name="montant_mensuel" value="25000" min="0"></div>
      <div class="fg full"><label>Notes</label><input type="text" name="notes" placeholder="Adresse, remarques..."></div>
    </div>
    <div style="margin-top:18px"><button type="submit" class="btn btn-green" style="padding:11px 28px;font-size:14px">Générer la licence →</button></div>
  </form>
</div>

<div class="card">
  <div class="card-title">📋 Liste des licences ({{ total }})</div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr>
      <th>Clé</th><th>Client</th><th>Ville / Secteur</th>
      <th>Expiration</th><th>Jours restants</th><th>Statut</th>
      <th>Mensuel</th><th>Dernière vérif.</th><th>Actions</th>
    </tr></thead>
    <tbody>
    {% for l in licences %}
    <tr>
      <td style="font-family:monospace;font-size:11px;color:#9ca3af">{{ l.cle }}</td>
      <td>
        <strong style="color:#1a1a2e">{{ l.client_nom }}</strong><br>
        <span style="font-size:11px;color:#9ca3af">{{ l.client_telephone or '' }}</span>
      </td>
      <td style="font-size:12px">
        {{ l.client_ville or '—' }}<br>
        <span style="color:#9ca3af">{{ l.client_secteur or '' }}</span>
      </td>
      <td>{{ l.date_expiration.strftime('%d/%m/%Y') }}</td>
      <td>
        {% set jr = l.jours_restants() %}
        <strong style="color:{% if jr==0 %}#dc2626{% elif jr<=5 %}#d97706{% else %}#059669{% endif%;font-size:15px">
          {{ jr }}j
        </strong>
      </td>
      <td>
        {% set s = l.statut_display() %}
        {% if s=='ACTIVE' %}<span class="badge b-ok">✓ Active</span>
        {% elif s=='SUSPENDUE' %}<span class="badge b-sus">✗ Suspendue</span>
        {% elif s=='EXPIREE' %}<span class="badge b-exp">Expirée</span>
        {% else %}<span class="badge b-warn">⚠ Bientôt</span>{% endif %}
      </td>
      <td style="font-weight:700">{{ l.montant_mensuel|int }} FCFA</td>
      <td style="font-size:11px;color:#9ca3af">
        {{ l.derniere_verification.strftime('%d/%m %H:%M') if l.derniere_verification else 'Jamais' }}
      </td>
      <td>
        {% if l.statut == 'active' %}
          <form method="POST" action="/admin/suspendre/{{ l.id }}" style="display:inline"
                onsubmit="return confirm('Couper la licence de {{ l.client_nom }} ?\\nL\\'app sera bloquée dans max 1 heure.')">
            <button class="btn btn-red">✕ Couper</button>
          </form>
        {% else %}
          <form method="POST" action="/admin/reactiver/{{ l.id }}" style="display:inline">
            <button class="btn btn-green">✓ Réactiver</button>
          </form>
        {% endif %}
        <form method="POST" action="/admin/renouveler/{{ l.id }}" style="display:inline">
          <button class="btn btn-orange">+1 mois</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="9" style="text-align:center;padding:32px;color:#9ca3af">
      Aucune licence créée. Créez la première licence ci-dessus.
    </td></tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
</div>

<script>
function copier() {
  const cle = document.getElementById('cle-display').textContent.trim();
  navigator.clipboard.writeText(cle).then(() => alert('Clé copiée : ' + cle));
}
</script>
</body></html>"""


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    erreur = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_connecte'] = True
            return redirect(url_for('admin_panel'))
        erreur = 'Mot de passe incorrect.'
    return render_template_string(LOGIN_HTML, erreur=erreur)

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_requis
def admin_panel():
    licences = Licence.query.order_by(Licence.date_creation.desc()).all()
    total = len(licences)
    actives = sum(1 for l in licences if l.statut=='active' and l.date_expiration>=date.today())
    inactives = sum(1 for l in licences if l.statut=='suspendue' or l.date_expiration<date.today())
    ca_mensuel = f"{sum(l.montant_mensuel for l in licences if l.statut=='active'):,}".replace(',',' ')
    flash_msg = session.pop('flash_msg', None)
    nouvelle_cle = session.pop('nouvelle_cle', None)
    nouvelle_cle_client = session.pop('nouvelle_cle_client', None)
    return render_template_string(ADMIN_HTML,
        licences=licences, total=total, actives=actives, inactives=inactives,
        ca_mensuel=ca_mensuel, flash_msg=flash_msg,
        nouvelle_cle=nouvelle_cle, nouvelle_cle_client=nouvelle_cle_client)

@app.route('/admin/creer', methods=['POST'])
@admin_requis
def admin_creer():
    duree = int(request.form.get('duree_mois', 1))
    cle = generer_cle()
    l = Licence(
        cle=cle,
        client_nom=request.form['client_nom'].strip(),
        client_telephone=request.form.get('client_telephone', ''),
        client_ville=request.form.get('client_ville', ''),
        client_secteur=request.form.get('client_secteur', ''),
        date_expiration=date.today() + timedelta(days=duree * 30),
        montant_mensuel=int(request.form.get('montant_mensuel', 25000)),
        notes=request.form.get('notes', '')
    )
    db.session.add(l)
    db.session.commit()
    session['nouvelle_cle'] = cle
    session['nouvelle_cle_client'] = l.client_nom
    session['flash_msg'] = f'Licence créée pour {l.client_nom} — expire le {l.date_expiration.strftime("%d/%m/%Y")}'
    return redirect(url_for('admin_panel'))

@app.route('/admin/suspendre/<int:id>', methods=['POST'])
@admin_requis
def admin_suspendre(id):
    l = Licence.query.get_or_404(id)
    l.statut = 'suspendue'
    db.session.commit()
    session['flash_msg'] = f'Licence de {l.client_nom} COUPÉE. App bloquée dans max 1 heure.'
    return redirect(url_for('admin_panel'))

@app.route('/admin/reactiver/<int:id>', methods=['POST'])
@admin_requis
def admin_reactiver(id):
    l = Licence.query.get_or_404(id)
    l.statut = 'active'
    if l.date_expiration < date.today():
        l.date_expiration = date.today() + timedelta(days=30)
    db.session.commit()
    session['flash_msg'] = f'Licence de {l.client_nom} RÉACTIVÉE — expire le {l.date_expiration.strftime("%d/%m/%Y")}.'
    return redirect(url_for('admin_panel'))

@app.route('/admin/renouveler/<int:id>', methods=['POST'])
@admin_requis
def admin_renouveler(id):
    l = Licence.query.get_or_404(id)
    base = max(l.date_expiration, date.today())
    l.date_expiration = base + timedelta(days=30)
    l.statut = 'active'
    db.session.commit()
    session['flash_msg'] = f'Licence de {l.client_nom} prolongée jusqu\'au {l.date_expiration.strftime("%d/%m/%Y")}.'
    return redirect(url_for('admin_panel'))

# ─── INIT ──────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7000))
    print(f"Serveur de licences StockPro — port {port}")
    print(f"Panel admin : http://localhost:{port}/admin")
    app.run(host='0.0.0.0', port=port, debug=False)
