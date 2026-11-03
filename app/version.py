"""Version installée (commit git) et comparaison avec GitHub."""
import json
import os
import subprocess
import time
import urllib.request

REPO = 'cv2b79/meca-auto'
BRANCH = 'main'
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_local = None
_remote_cache = {'at': 0, 'data': None}


def _git(*args):
    # Le service systemd a un PATH réduit au venv : essayer aussi /usr/bin/git
    for exe in ('git', '/usr/bin/git'):
        try:
            out = subprocess.run([exe, '-C', APP_ROOT, *args], capture_output=True,
                                 text=True, encoding='utf-8', errors='replace', timeout=5)
            if out.returncode == 0:
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def local_version():
    """{'sha', 'short', 'date', 'subject'} du commit installé, calculé une fois au démarrage."""
    global _local
    if _local is None:
        out = _git('log', '-1', '--format=%H|%h|%cd|%s', '--date=format:%d/%m/%Y %H:%M')
        if out:
            sha, short, date, subject = out.split('|', 3)
            _local = {'sha': sha, 'short': short, 'date': date, 'subject': subject}
        else:
            _local = {'sha': '', 'short': 'inconnue', 'date': '', 'subject': ''}
    return _local


def github_version(max_age=600):
    """Dernier commit de main sur GitHub (mis en cache 10 min), ou None si injoignable."""
    now = time.time()
    if _remote_cache['data'] and now - _remote_cache['at'] < max_age:
        return _remote_cache['data']
    try:
        req = urllib.request.Request(
            f'https://api.github.com/repos/{REPO}/commits/{BRANCH}',
            headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'meca-auto'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            c = json.load(resp)
        from datetime import datetime, timezone
        date = datetime.strptime(c['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ')
        date = date.replace(tzinfo=timezone.utc).astimezone()
        data = {'sha': c['sha'], 'short': c['sha'][:7], 'date': date.strftime('%d/%m/%Y %H:%M'),
                'subject': c['commit']['message'].split('\n')[0]}
    except Exception:
        return None
    _remote_cache.update(at=now, data=data)
    return data


def version_status():
    """Infos pour la page Administration."""
    local = local_version()
    remote = github_version()
    if not remote or not local['sha']:
        etat = 'inconnu'
    elif remote['sha'] == local['sha']:
        etat = 'a_jour'
    else:
        etat = 'different'
    return {'local': local, 'remote': remote, 'etat': etat}
