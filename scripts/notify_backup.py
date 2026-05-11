"""
Envoie une notification email après la sauvegarde.
Usage : python3 notify_backup.py OK "message" | ECHEC "message"
"""
import sys, os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

status = sys.argv[1] if len(sys.argv) > 1 else 'INCONNU'
message = sys.argv[2] if len(sys.argv) > 2 else ''

smtp_host = os.getenv('SMTP_HOST', '')
smtp_port = int(os.getenv('SMTP_PORT', 587))
smtp_user = os.getenv('SMTP_USER', '')
smtp_pass = os.getenv('SMTP_PASSWORD', '')
smtp_from = os.getenv('SMTP_FROM', smtp_user)

# Destinataire : email DDFPT ou SMTP_USER
recipient = os.getenv('EMAIL_DDFPT', smtp_user)

if not all([smtp_host, smtp_user, smtp_pass, recipient]):
    sys.exit(0)  # Pas de config email, on ignore silencieusement

icon = '✅' if status == 'OK' else '❌'
subject = f"{icon} Meca Auto — Sauvegarde {status} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"

body = f"""
<html><body style="font-family:Arial,sans-serif; max-width:600px; margin:0 auto;">
<div style="background:{'#d4edda' if status == 'OK' else '#f8d7da'}; padding:1rem; border-radius:8px; margin-bottom:1rem;">
  <h2 style="margin:0; color:{'#155724' if status == 'OK' else '#721c24'};">{icon} Sauvegarde {status}</h2>
</div>
<p><strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}</p>
<p><strong>Détails :</strong> {message}</p>
<hr>
<small style="color:#666;">Meca Auto — Sauvegarde automatique</small>
</body></html>
"""

try:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_from
    msg['To'] = recipient
    msg.attach(MIMEText(body, 'html', 'utf-8'))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
except Exception as e:
    print(f"Notification email échouée : {e}", file=sys.stderr)
