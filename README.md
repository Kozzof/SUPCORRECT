# SUPCORRECT - Correcteur automatique

Projet de correction automatique de programmes C et Python. Les soumissions passent par une file SQL, sont évaluées par un worker non privilégié, puis supprimées.

## Démarrage local

Prérequis : Python 3.12 ou plus récent.

Depuis le dossier extrait de l'archive :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m app.supcorrect.init_db
flask --app app.supcorrect run --debug
```

Le worker réel exige Linux, `bubblewrap`, `gcc` et Python. Sous Windows, utiliser uniquement l'interface locale et les tests unitaires :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Le mode local utilise SQLite. La cible de livraison utilise MariaDB et les configurations de `infra/`. Le chargement de `.env` est assuré par `python-dotenv`.

## Arborescence

- `app/` : application web et worker.
- `tests/reference/` : énoncés et cas de test privés du correcteur.
- `infra/` : Apache, HAProxy, MariaDB et systemd.
- `scripts/` : installation et contrôles de déploiement.
- `docs/` : architecture, sécurité et exploitation.
