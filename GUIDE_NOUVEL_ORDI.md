# Guide de démarrage — nouvel ordinateur (Formia)

Ce document explique **comment installer et lancer le projet** sur un autre PC après l’avoir récupéré via Git, pour obtenir le **même fonctionnement** que sur la machine de développement d’origine.

Lis-le jusqu’au bout la première fois. Ensuite, tu pourras te contenter de la section « démarrage quotidien » en bas.

---

## 1. Ce que Git te donne (et ce qu’il ne te donne pas)

Quand tu clones ou tires le projet avec Git, tu récupères surtout le **code source** : backend FastAPI, frontend Next.js, Docker Compose, README, fichier d’exemple `sample_cours.txt`, etc.

Tu ne récupères **pas** automatiquement :

- la base de données PostgreSQL (supports déjà indexés, conversations, exercices passés) ;
- le dossier `node_modules` du frontend ;
- l’environnement virtuel Python `.venv` du backend ;
- les fichiers secrets / locaux `.env` et `.env.local` (volontairement exclus de Git) ;
- Ollama et ses modèles IA, qui s’installent à part sur chaque machine.

Donc : **même application**, mais au premier lancement la base est « neuve ». Les **trois comptes démo** sont recréés automatiquement au démarrage de l’API. Les supports pédagogiques, eux, devront être réimportés si tu en as besoin.

---

## 2. Prérequis logiciels (à installer une seule fois)

Avant toute commande, installe les outils suivants sur le nouvel ordinateur.

### 2.1 Docker Desktop

Docker sert à faire tourner **PostgreSQL avec l’extension pgvector** (recherche sémantique pour le RAG).

- Installe Docker Desktop pour Windows.
- Lance Docker Desktop et attends qu’il soit bien démarré (icône stable).
- Vérifie dans un terminal :

```powershell
docker --version
```

Sans Docker, la base ne démarrera pas correctement avec la config prévue du projet.

### 2.2 Node.js (version 20 ou plus)

Node.js sert à installer et lancer le **frontend** Next.js.

```powershell
node -v
npm -v
```

Si la commande est introuvable, installe Node.js LTS depuis le site officiel, puis **ouvre un nouveau terminal**.

### 2.3 Python (version 3.12 ou plus recommandé)

Python sert à lancer le **backend** FastAPI.

```powershell
python --version
```

Si plusieurs Python sont installés, assure-toi d’utiliser une version récente compatible avec les dépendances du fichier `backend/requirements.txt`.

### 2.4 Ollama (obligatoire pour l’IA)

Ollama fait tourner **localement** et gratuitement :

- le modèle de chat (`llama3.2`) pour tuteur, exercices, grammaire, etc. ;
- le modèle d’embeddings (`nomic-embed-text`) pour indexer et rechercher dans les documents.

Sans Ollama :

- tu pourras te connecter et naviguer dans l’interface ;
- mais l’**indexation**, le **chat**, la **génération d’exercices** et une partie du module **langues** échoueront.

Installe Ollama depuis https://ollama.com, puis **lance l’application Ollama** et laisse-la ouverte.

Vérifie :

```powershell
ollama --version
```

Si Windows répond que `ollama` n’est pas reconnu, ferme tous les terminaux, rouvre-en un nouveau, ou utilise le chemin complet :

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
```

---

## 3. Récupérer le projet avec Git

Place-toi dans le dossier où tu veux le projet, puis clone (ou `git pull` si le dépôt est déjà là) :

```powershell
cd $HOME\Documents
git clone <URL_DE_TON_DEPOT>
cd <nom-du-dossier-du-projet>
```

### Note importante sur les chemins Windows avec accents

Si le nom du dossier contient des accents ou une apostrophe (par exemple « évaluation »), certains terminaux ou outils peuvent planter. Dans ce cas, crée une **jonction** avec un chemin simple :

```powershell
cmd /c mklink /J "%USERPROFILE%\Documents\agent-formation" "%USERPROFILE%\Documents\<nom-du-dossier-avec-accents>"
cd $HOME\Documents\agent-formation
```

Travaille ensuite préférentiellement via `agent-formation`.

### Vérifier que le frontend est bien présent

Après correction du dépôt (frontend inclus correctement dans Git), tu dois voir notamment :

- `frontend/package.json`
- `frontend/src/`
- `backend/app/main.py`
- `docker-compose.yml`

Si `frontend/package.json` manque encore, ton `git pull` n’est pas à jour ou le push depuis l’autre machine n’a pas été fait. Dans ce cas, mets à jour le dépôt distant puis refais un `git pull` sur ce PC.

---

## 4. Télécharger les modèles Ollama (une seule fois par machine)

Ollama installé ne suffit pas : il faut **télécharger les modèles** utilisés par Formia.

Dans un terminal :

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
ollama list
```

Tu dois voir les deux modèles dans la liste.

**Machine avec peu de RAM** : tu peux utiliser un modèle plus petit, par exemple `llama3.2:1b`, puis mettre dans `backend/.env` :

```env
OLLAMA_LLM_MODEL=llama3.2:1b
```

La qualité des réponses et des exercices sera plus faible, mais l’application restera utilisable.

---

## 5. Créer les fichiers de configuration locaux

Ces fichiers ne sont en général **pas** versionnés (sécurité / machine locale). Tu dois les créer une fois sur chaque PC.

### 5.1 Backend : `backend/.env`

À la racine backend, copie l’exemple :

```powershell
cd backend
copy .env.example .env
```

Puis ouvre `backend/.env` et vérifie qu’il ressemble à ceci :

```env
DATABASE_URL=postgresql+psycopg://agent:agent@localhost:5433/agent_formation
SECRET_KEY=change-me-in-production-use-long-random-string
CORS_ORIGINS=http://localhost:3000
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2
OLLAMA_EMBED_MODEL=nomic-embed-text
EMBEDDING_DIM=768
CHUNK_SIZE=800
CHUNK_OVERLAP=120
UPLOAD_DIR=uploads
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Explications brèves :

- `DATABASE_URL` : connexion à Postgres. Le port hôte est **5433** (pas 5432) pour éviter le conflit avec un PostgreSQL Windows déjà installé sur certaines machines.
- `OLLAMA_BASE_URL` : adresse locale d’Ollama.
- `SECRET_KEY` : secret JWT. Change-le si tu exposes l’app hors de ta machine.
- `CORS_ORIGINS` : autorise le frontend `http://localhost:3000` à appeler l’API.

Reviens à la racine du projet ensuite :

```powershell
cd ..
```

### 5.2 Frontend : `frontend/.env.local`

Crée le fichier `frontend/.env.local` avec ce contenu :

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Cela indique au navigateur où se trouve l’API. Sans ce fichier (ou avec une mauvaise URL), tu auras des erreurs du type **Failed to fetch**.

---

## 6. Démarrer PostgreSQL avec Docker

À la racine du projet :

```powershell
docker compose up -d postgres
```

Vérifie que le conteneur tourne :

```powershell
docker ps
```

Tu dois voir un conteneur nommé en général `agent_formation_db`, basé sur l’image `pgvector/pgvector:pg16`, avec le port **5433→5432**.

Attends quelques secondes que le healthcheck passe (statut healthy / Up).

Si le port 5433 est déjà utilisé sur cette machine, tu devras adapter :

1. le mapping de ports dans `docker-compose.yml` ;
2. le `DATABASE_URL` dans `backend/.env`.

---

## 7. Démarrer le backend (API FastAPI)

Ouvre un **premier terminal**, place-toi dans le projet, puis :

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Explications :

- `python -m venv .venv` crée un environnement virtuel isolé (une seule fois).
- `.\.venv\Scripts\activate` l’active (à refaire à chaque nouveau terminal).
- `pip install -r requirements.txt` installe FastAPI, SQLAlchemy, pgvector, etc. (une seule fois, ou après mise à jour des deps).
- `uvicorn ... --reload --port 8000` lance l’API avec rechargement auto en développement.

Laisse ce terminal **ouvert**.

### Vérifications backend

- Santé : http://localhost:8000/api/health → tu dois voir `{"status":"ok"}`
- Documentation interactive : http://localhost:8000/docs

Au démarrage, l’API initialise la base (extension `vector`, tables) et **ensemence les comptes démo** s’ils n’existent pas encore.

---

## 8. Démarrer le frontend (Next.js)

Ouvre un **second terminal** (laisse le backend tourner dans le premier) :

```powershell
cd frontend
npm install
npm run dev
```

Explications :

- `npm install` télécharge les dépendances listées dans `package.json` (une seule fois, ou après `git pull` qui change les deps).
- `npm run dev` démarre le serveur de développement Next.js, en général sur le port **3000**.

Ouvre ensuite : http://localhost:3000

Laisse ce terminal **ouvert** aussi.

---

## 9. Comptes de démonstration

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Administrateur | `admin@demo.local` | `admin123` |
| Formateur | `formateur@demo.local` | `trainer123` |
| Apprenant | `apprenant@demo.local` | `learner123` |

Ces comptes sont créés automatiquement par le seed au lancement de l’API. Tu n’as pas besoin de les recréer à la main.

---

## 10. Premier usage correct (très important)

Même si l’application démarre, **l’IA a besoin d’un support indexé**.

Ordre recommandé pour un formateur :

1. Connecte-toi avec `formateur@demo.local` / `trainer123`.
2. Va dans **Supports**.
3. Titre par exemple : `Sécurité au travail`.
4. Importe le fichier `sample_cours.txt` présent à la racine du projet.
5. Clique **Importer et indexer** et attends le statut **`indexed`**.
6. Seulement ensuite utilise :
   - **Tuteur IA** (de préférence via **Nouvelle conversation**) ;
   - **Exercices** ;
   - **Compréhension écrite** dans Langues.

### Règles d’or pour éviter les erreurs déjà rencontrées

1. Pas de chat / génération d’exercices tant que le document n’est pas **`indexed`**.
2. Après un nouvel import, utilise **Nouvelle conversation** (ne reste pas sur un vieux fil d’erreur).
3. Ollama en local peut prendre **20 à 90 secondes** (parfois plus) : **ne recharge pas** la page pendant la génération.
4. Garde **Ollama ouvert** pendant que tu indexes ou que tu utilises le tuteur.

---

## 11. Démarrage quotidien (une fois tout installé)

Chaque fois que tu veux travailler sur ce PC :

1. Allumer **Docker Desktop**.
2. Allumer **Ollama**.
3. Dans un terminal, à la racine du projet :

```powershell
docker compose up -d postgres
```

4. Terminal 1 — backend :

```powershell
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

5. Terminal 2 — frontend :

```powershell
cd frontend
npm run dev
```

6. Ouvrir http://localhost:3000

Tu n’as en principe **pas** besoin de refaire `pip install`, `npm install` ou `ollama pull` à chaque fois, sauf après une mise à jour du projet ou des modèles.

---

## 12. Après un `git pull` (mises à jour)

Quand tu récupères de nouveaux commits :

```powershell
git pull
```

Puis, selon ce qui a changé :

```powershell
# Si requirements backend ont changé
cd backend
.\.venv\Scripts\activate
pip install -r requirements.txt

# Si package.json frontend a changé
cd ..\frontend
npm install
```

Relance ensuite API + front comme d’habitude.

---

## 13. Problèmes fréquents et solutions

### `ollama` n’est pas reconnu

Ollama est installé mais pas dans le PATH du terminal actuel.

- Ferme et rouvre le terminal (ou Cursor).
- Ou utilise le chemin complet vers `ollama.exe` (voir section 2.4).

### Port 8000 déjà utilisé / WinError 10013

Une ancienne instance d’uvicorn tourne encore.

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Puis relance uvicorn.

### `Failed to fetch` dans le navigateur

En général :

- l’API n’est pas démarrée sur `:8000` ;
- ou `frontend/.env.local` est absent / incorrect ;
- ou CORS / mauvaise URL.

Vérifie http://localhost:8000/api/health puis recharge le front.

### Document en statut `failed`

Ollama n’est pas lancé, ou les modèles manquent. Vérifie `ollama list`, relance Ollama, réimporte le fichier.

### Chat : « aucun contenu indexé »

Aucun document `indexed`, ou tu es sur une ancienne conversation. Importe un support, attends `indexed`, puis **Nouvelle conversation**.

### Conflit Git au `pull` (fichiers untracked would be overwritten)

Sur le nouvel ordi, si d’anciens fichiers locaux non suivis bloquent le merge, supprime les fichiers listés par Git puis refais `git pull`. La version distante est la référence.

### Chemin avec accents qui casse le terminal

Utilise la jonction `Documents\agent-formation` (section 3).

---

## 14. Récapitulatif de l’architecture locale

```text
Navigateur (localhost:3000)
    → Frontend Next.js
        → API FastAPI (localhost:8000)
            → PostgreSQL + pgvector (Docker, port hôte 5433)
            → Ollama (localhost:11434) pour LLM + embeddings
```

Tout est conçu pour tourner **en local** et **sans coût d’API cloud**, à condition qu’Ollama et Docker soient opérationnels.

---

## 15. Checklist finale « je suis prêt »

Coche mentalement avant de tester le produit :

- [ ] Docker Desktop démarré
- [ ] `docker compose up -d postgres` OK
- [ ] Ollama ouvert + `llama3.2` et `nomic-embed-text` présents
- [ ] `backend/.env` créé
- [ ] `frontend/.env.local` créé
- [ ] API répond sur `/api/health`
- [ ] Front accessible sur http://localhost:3000
- [ ] Login formateur OK
- [ ] Au moins un support au statut **`indexed`** avant d’utiliser le tuteur

Quand cette checklist est verte, tu as sur le nouvel ordinateur le même socle fonctionnel que sur la machine d’origine.

---

*Document destiné au projet Formia — Agent IA de formation et d’évaluation pédagogique.*
