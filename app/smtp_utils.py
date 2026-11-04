"""Envoi SMTP commun : SSL direct sur le port 465, STARTTLS sinon, toujours avec un délai max."""
import smtplib

SMTP_TIMEOUT = 20  # secondes : sans délai, un serveur muet bloque l'envoi indéfiniment


def smtp_send(msg, host, port, user, password):
    """Envoie `msg` (email.message) ; lève l'exception smtplib en cas d'échec."""
    port = int(port or 587)
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT)
    else:
        server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)
        server.starttls()
    try:
        server.ehlo_or_helo_if_needed()
        if 'plain' in server.esmtp_features.get('auth', '').lower():
            # login() enchaînerait sur AUTH LOGIN après un refus : Gmail coupe alors la
            # connexion et l'erreur devient "Connection unexpectedly closed" au lieu de 535
            server.user, server.password = user, password
            server.auth('PLAIN', server.auth_plain)
        else:
            server.login(user, password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass
