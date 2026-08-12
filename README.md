# Agent Formation (Formia)

Application web d'accompagnement et d'évaluation pédagogique basée sur vos supports (RAG local).

## Prérequis
- Docker Desktop
- Node.js 20+
- Python 3.12+
- [Ollama](https://ollama.com) **obligatoire** pour chat / indexation / exercices

## Modèles Ollama
```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

RAM limitée : `ollama pull llama3.2:1b` puis `OLLAMA_LLM_MODEL=llama3.2:1b` dans `backend/.env`.

## Démarrage

```bash
# Base PostgreSQL + pgvector (port hôte 5433 pour éviter un Postgres local sur 5432)
docker compose up -d postgres

# API
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (autre terminal)
cd frontend
npm install
npm run dev
```

- App : http://localhost:3000  
- API docs : http://localhost:8000/docs  
- Fichier démo à importer : `sample_cours.txt`

## Comptes démo

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Admin | admin@demo.local | admin123 |
| Formateur | formateur@demo.local | trainer123 |
| Apprenant | apprenant@demo.local | learner123 |

## Fonctionnalités MVP
- Import PDF / DOCX / TXT + indexation RAG (pgvector + Ollama)
- Chat tuteur avec citations
- Exercices : QCM, ouvertes, études de cas, simulation d'examen
- Dashboards apprenant / formateur + export CSV
- Module langues : grammaire, compréhension écrite, prononciation (Whisper optionnel via `pip install faster-whisper`)

## Guide complet (Git → lancement → tests A→Z)
Voir **[GUIDE_COMPLET_INSTALLATION_ET_TESTS.md](./GUIDE_COMPLET_INSTALLATION_ET_TESTS.md)** — récupération depuis Git, installation, démarrage de tous les services, puis parcours de test détaillé formateur / apprenant / admin avec résultats attendus (toasts, modales, menus par rôle, RAG, exercices, langues).

Pour un démarrage « nouvel ordinateur » plus court : **[GUIDE_NOUVEL_ORDI.md](./GUIDE_NOUVEL_ORDI.md)**.

## Tests

### Lancer les tests unitaires FastAPI (sans Postgres)

Le backend supporte `SKIP_DB_INIT=1` pour permettre de tester les endpoints sans dépendre de la base.

```bash
cd backend
.\\.venv\\Scripts\\activate
pytest -q
```

Les tests actuels couvrent au minimum :
- `GET /api/health`
- `GET /` (endpoint root)

### Lancer les tests E2E

Utilise le script `formia_e2e.ps1` (présent dans le dépôt) si tu veux rejouer un parcours complet de validation.

## Architecture
Next.js ↔ FastAPI ↔ PostgreSQL/pgvector ↔ Ollama (hôte)

## Note chemin Windows
Si le dossier projet avec accents pose problème en terminal, utilisez la jonction :
`C:\Users\josue\Documents\agent-formation`
