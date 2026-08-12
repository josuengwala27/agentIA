# Guide complet — Récupérer Formia depuis Git, tout lancer, puis tester de A à Z

Ce document est le **parcours unique** à suivre sur un ordinateur Windows pour :

1. récupérer le projet depuis Git ;
2. installer et démarrer tous les services (Docker, PostgreSQL, API, frontend, Ollama) ;
3. vérifier que l’application fonctionne **de bout en bout**, profil par profil, avec les **résultats attendus** à chaque étape.

Lis-le une première fois en entier. Ensuite, tu pourras te contenter de la **checklist rapide** en fin de document pour les relances quotidiennes.

Le ton est volontairement détaillé : chaque commande est expliquée, et chaque test indique clairement ce que tu dois **voir à l’écran** si tout va bien.

---

## Table des matières

1. [Ce que tu vas obtenir](#1-ce-que-tu-vas-obtenir)
2. [Ce que Git te donne (et ce qu’il ne te donne pas)](#2-ce-que-git-te-donne-et-ce-quil-ne-te-donne-pas)
3. [Prérequis logiciels (une seule fois)](#3-prérequis-logiciels-une-seule-fois)
4. [Récupérer le projet avec Git](#4-récupérer-le-projet-avec-git)
5. [Configurer Ollama et les modèles IA](#5-configurer-ollama-et-les-modèles-ia)
6. [Créer les fichiers de configuration locaux](#6-créer-les-fichiers-de-configuration-locaux)
7. [Lancer PostgreSQL, l’API et le frontend](#7-lancer-postgresql-lapi-et-le-frontend)
8. [Vérifications de santé avant les tests métier](#8-vérifications-de-santé-avant-les-tests-métier)
9. [Comptes de démonstration](#9-comptes-de-démonstration)
10. [Règles d’or pour des tests fiables](#10-règles-dor-pour-des-tests-fiables)
11. [Parcours de test A → Z (formateur)](#11-parcours-de-test-a--z-formateur)
12. [Parcours de test apprenant](#12-parcours-de-test-apprenant)
13. [Parcours de test administrateur](#13-parcours-de-test-administrateur)
14. [Tests techniques (pytest)](#14-tests-techniques-pytest)
15. [Démarrage quotidien et après un git pull](#15-démarrage-quotidien-et-après-un-git-pull)
16. [Problèmes fréquents et solutions](#16-problèmes-fréquents-et-solutions)
17. [Checklist finale](#17-checklist-finale)

---

## 1. Ce que tu vas obtenir

À la fin de ce guide, tu auras sur ton ordinateur :

- une **base PostgreSQL** avec l’extension **pgvector** (recherche sémantique) ;
- une **API FastAPI** sur le port `8000` ;
- une **interface Next.js** sur le port `3000` ;
- une **IA locale via Ollama** (chat + embeddings) ;
- trois comptes démo (admin, formateur, apprenant) ;
- la confirmation visuelle que les toasts, modales, menus par rôle et parcours métier fonctionnent.

Tout tourne **en local**, sans payer d’API cloud, à condition que Docker et Ollama soient bien démarrés.

---

## 2. Ce que Git te donne (et ce qu’il ne te donne pas)

Quand tu clones ou tires le projet avec Git, tu récupères le **code source** : backend, frontend, Docker Compose, exemples (`sample_cours.txt`), documentation, scripts de test, etc.

Tu ne récupères **pas** automatiquement :

- la base de données déjà remplie (supports indexés, conversations, exercices) ;
- le dossier `node_modules` du frontend ;
- l’environnement virtuel Python `.venv` du backend ;
- les fichiers secrets locaux `.env` et `.env.local` (exclus volontairement de Git) ;
- Ollama et ses modèles, qui s’installent à part sur chaque machine.

Conséquence pratique : **même application**, mais au premier lancement la base est « neuve ». Les trois comptes démo sont **recréés automatiquement** au démarrage de l’API. Les supports pédagogiques devront être **réimportés** si tu en as besoin.

---

## 3. Prérequis logiciels (une seule fois)

Avant toute commande liée au projet, installe et vérifie les outils suivants.

### 3.1 Docker Desktop

Docker sert à faire tourner **PostgreSQL avec pgvector**.

1. Installe Docker Desktop pour Windows.
2. Lance Docker Desktop et attends que l’icône soit stable (moteur démarré).
3. Dans un terminal PowerShell, vérifie :

```powershell
docker --version
```

**Résultat attendu :** une ligne avec le numéro de version Docker.  
Si la commande est introuvable, Docker n’est pas installé correctement ou le terminal a été ouvert avant l’installation : ferme et rouvre le terminal.

### 3.2 Node.js (version 20 ou plus)

Node.js sert à installer et lancer le **frontend** Next.js.

```powershell
node -v
npm -v
```

**Résultat attendu :** une version Node `v20` ou supérieure, et une version npm associée.  
Sinon, installe Node.js LTS depuis le site officiel, puis ouvre un **nouveau** terminal.

### 3.3 Python (version 3.12 ou plus recommandé)

Python sert à lancer le **backend** FastAPI.

```powershell
python --version
```

**Résultat attendu :** `Python 3.12.x` (ou une version récente compatible avec `backend/requirements.txt`).

### 3.4 Git

```powershell
git --version
```

**Résultat attendu :** une version Git affichée. Sans Git, tu ne pourras pas cloner ni tirer le projet.

### 3.5 Ollama (obligatoire pour l’IA)

Ollama fait tourner **localement** :

- le modèle de chat (`llama3.2`) pour le tuteur, les exercices, la grammaire, etc. ;
- le modèle d’embeddings (`nomic-embed-text`) pour indexer et rechercher dans les documents.

Sans Ollama, tu pourras te connecter et naviguer, mais l’**indexation**, le **chat**, la **génération d’exercices** et une partie du module **langues** échoueront.

1. Installe Ollama depuis https://ollama.com
2. Lance l’application Ollama et **laisse-la ouverte**
3. Vérifie :

```powershell
ollama --version
```

Si Windows répond que `ollama` n’est pas reconnu, ferme tous les terminaux, rouvre-en un, ou utilise le chemin complet :

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
```

---

## 4. Récupérer le projet avec Git

### 4.1 Premier clone (nouvel ordinateur)

Place-toi dans le dossier où tu veux le projet, puis clone :

```powershell
cd $HOME\Documents
git clone <URL_DE_TON_DEPOT>
cd <nom-du-dossier-du-projet>
```

Remplace `<URL_DE_TON_DEPOT>` par l’URL HTTPS ou SSH de ton dépôt GitHub (ou autre).  
Remplace `<nom-du-dossier-du-projet>` par le nom du dossier créé par `git clone`.

**Résultat attendu :** le dossier contient au minimum :

- `frontend/package.json`
- `frontend/src/`
- `backend/app/main.py`
- `docker-compose.yml`
- `sample_cours.txt`
- `README.md`

Si `frontend/package.json` est absent, ton dépôt distant n’est pas à jour ou le clone est incomplet : mets à jour le dépôt depuis la machine de référence, puis refais un `git pull` / un nouveau clone.

### 4.2 Projet déjà présent : mettre à jour avec git pull

```powershell
cd <chemin-vers-le-projet>
git status
git pull
```

**Résultat attendu :** Git récupère les derniers commits sans erreur.  
Si un conflit apparaît (fichiers locaux non suivis qui bloqueraient l’écrasement), lis le message Git, retire ou sauvegarde les fichiers locaux listés, puis refais `git pull`. La version distante est la référence.

### 4.3 Note importante sur les chemins Windows avec accents

Si le nom du dossier contient des accents ou une apostrophe (par exemple « évaluation »), certains terminaux ou outils peuvent planter. Dans ce cas, crée une **jonction** avec un chemin simple :

```powershell
cmd /c mklink /J "%USERPROFILE%\Documents\agent-formation" "%USERPROFILE%\Documents\<nom-du-dossier-avec-accents>"
cd $HOME\Documents\agent-formation
```

Travaille ensuite préférentiellement via `agent-formation`.

---

## 5. Configurer Ollama et les modèles IA

Ollama installé ne suffit pas : il faut **télécharger les modèles** utilisés par Formia (une seule fois par machine).

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
ollama list
```

**Résultat attendu :** `ollama list` affiche au moins `llama3.2` et `nomic-embed-text`.

**Machine avec peu de RAM :** tu peux utiliser un modèle plus petit :

```powershell
ollama pull llama3.2:1b
```

Puis dans `backend/.env` :

```env
OLLAMA_LLM_MODEL=llama3.2:1b
```

La qualité des réponses sera plus faible, mais l’application restera utilisable.

**Important :** laisse l’application Ollama **ouverte** pendant toute la durée des tests d’indexation, de chat et d’exercices.

---

## 6. Créer les fichiers de configuration locaux

Ces fichiers ne sont en général **pas** versionnés. Tu dois les créer une fois sur chaque PC.

### 6.1 Backend : `backend/.env`

```powershell
cd backend
copy .env.example .env
```

Ouvre ensuite `backend/.env` et vérifie qu’il contient bien (ou équivalent) :

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

Explications :

- `DATABASE_URL` : connexion à Postgres. Le port hôte est **5433** (pas 5432) pour éviter le conflit avec un PostgreSQL Windows déjà installé.
- `OLLAMA_BASE_URL` : adresse locale d’Ollama.
- `SECRET_KEY` : secret JWT. Change-le si tu exposes l’app hors de ta machine.
- `CORS_ORIGINS` : autorise le frontend `http://localhost:3000` à appeler l’API.

Reviens à la racine du projet :

```powershell
cd ..
```

### 6.2 Frontend : `frontend/.env.local`

Crée le fichier `frontend/.env.local` avec :

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Sans ce fichier (ou avec une mauvaise URL), tu auras des erreurs du type **Failed to fetch** dans le navigateur.

---

## 7. Lancer PostgreSQL, l’API et le frontend

Tu as besoin de **trois éléments actifs** en parallèle : Postgres (Docker), API (terminal 1), frontend (terminal 2).

### 7.1 Démarrer PostgreSQL

À la racine du projet :

```powershell
docker compose up -d postgres
docker ps
```

**Résultat attendu :** un conteneur nommé en général `agent_formation_db`, image `pgvector/pgvector:pg16`, port **5433→5432**, statut Up / healthy après quelques secondes.

Si le port 5433 est déjà utilisé, adapte le mapping dans `docker-compose.yml` **et** le `DATABASE_URL` dans `backend/.env`.

### 7.2 Démarrer le backend (terminal 1)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Explications :

- `python -m venv .venv` crée un environnement virtuel isolé (**une seule fois**).
- `.\.venv\Scripts\activate` l’active (**à chaque nouveau terminal**).
- `pip install -r requirements.txt` installe les dépendances (**une seule fois**, ou après mise à jour des deps).
- `uvicorn ... --reload --port 8000` lance l’API avec rechargement automatique.

Laisse ce terminal **ouvert**. Au démarrage, l’API applique les migrations (Alembic) ou initialise le schéma, puis **ensemence les comptes démo** s’ils n’existent pas encore.

### 7.3 Démarrer le frontend (terminal 2)

Dans un **second** terminal :

```powershell
cd frontend
npm install
npm run dev
```

Explications :

- `npm install` télécharge les dépendances listées dans `package.json` (**une seule fois**, ou après un `git pull` qui change les deps).
- `npm run dev` démarre Next.js, en général sur le port **3000**.

Ouvre ensuite : http://localhost:3000

Laisse ce terminal **ouvert** aussi.

---

## 8. Vérifications de santé avant les tests métier

Ne commence les tests métier que si ces trois points sont verts.

### 8.1 Santé de l’API

Ouvre http://localhost:8000/api/health

**Résultat attendu :** `{"status":"ok"}`

Tu peux aussi ouvrir http://localhost:8000/docs pour voir la documentation interactive Swagger.

### 8.2 Frontend accessible

Ouvre http://localhost:3000

**Résultat attendu :** la page de connexion Formia s’affiche (pas d’écran d’erreur Next.js, pas de « Failed to fetch » immédiat).

### 8.3 Ollama joignable

```powershell
ollama list
```

**Résultat attendu :** les modèles listés, et l’application Ollama toujours ouverte.

---

## 9. Comptes de démonstration

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Administrateur | `admin@demo.local` | `admin123` |
| Formateur | `formateur@demo.local` | `trainer123` |
| Apprenant | `apprenant@demo.local` | `learner123` |

Ces comptes sont créés automatiquement par le seed au lancement de l’API. Tu n’as pas besoin de les créer à la main.

---

## 10. Règles d’or pour des tests fiables

1. **Pas de chat / exercices / compréhension** tant qu’aucun document n’est au statut **`indexed`**.
2. Après un nouvel import, utilise **Nouvelle conversation** (ne reste pas sur un vieux fil d’erreur).
3. Ollama en local peut prendre **20 à 90 secondes** (parfois plus) : **ne recharge pas** la page pendant la génération.
4. Garde **Ollama ouvert** pendant l’indexation et l’usage du tuteur.
5. Les confirmations importantes passent par une **modale moderne** dans la page, pas par la boîte native du navigateur.
6. Les succès et erreurs s’affichent en **toasts** (notifications en haut à droite), pas en `alert()`.

---

## 11. Parcours de test A → Z (formateur)

Ce parcours est le plus complet. Il valide l’UX professionnelle, l’indexation, le RAG, les exercices, les langues et le dashboard.

Connecte-toi avec :

- email : `formateur@demo.local`
- mot de passe : `trainer123`

### Étape A — Connexion et navigation formateur

1. Sur http://localhost:3000, saisis les identifiants formateur.
2. Valide la connexion.

**Résultat attendu :**

- tu arrives sur le tableau de bord ;
- le titre de page est **Pilotage** (pas « Progression » ni « Supervision ») ;
- la sidebar affiche exactement :
  - **Pilotage**
  - **Supports**
  - **Tuteur IA**
  - **Exercices & évals**
  - **Langues**

### Étape B — Import et indexation d’un support

1. Clique sur **Supports**.
2. Titre du document : `Sécurité au travail`.
3. Choisis le fichier `sample_cours.txt` situé à la **racine du projet**.
4. Clique sur **Importer et indexer**.

**Résultat attendu immédiat :**

- une **notification toast verte** apparaît en haut à droite (titre du type « Support importé ») ;
- le document apparaît dans la liste avec un statut en cours / en attente d’indexation.

**Résultat attendu après quelques secondes à quelques minutes :**

- le statut passe à **`indexed`** (indicateur vert / succès) ;
- si Ollama est arrêté ou les modèles manquent, le statut peut passer à **`failed`** : dans ce cas, lance Ollama, vérifie `ollama list`, puis réimporte.

Ne continue **pas** tant que le statut n’est pas `indexed`.

### Étape C — Toast et modale sur la suppression (UX)

Pour valider le remplacement des `confirm()` / `alert()` natifs :

1. Clique sur **Supprimer** sur un document (idéalement un doublon, ou le même après un second import de test).
2. Une **modale** s’ouvre dans la page (fond grisé), avec un titre du type « Supprimer le support ? », une description, et deux boutons **Annuler** / **Supprimer**.

**Résultat attendu :**

- **Annuler** ferme la modale sans supprimer ;
- **Supprimer** confirme, puis un **toast vert** « Support supprimé » apparaît ;
- **aucun** dialogue natif du navigateur du type « This page says… ».

Si tu as vraiment besoin du document pour la suite, réimporte `sample_cours.txt` et attends à nouveau `indexed`.

### Étape D — Tuteur IA (chat RAG)

1. Va dans **Tuteur IA**.
2. Si l’historique est vide, tu dois voir un **état vide / placeholder** invitant à poser une première question (par exemple « Commence par une question »).
3. Clique sur **Nouvelle conversation** si un ancien fil existe.
4. Pose une question liée au cours, par exemple :  
   `Quels sont les principes de prévention au travail selon le support ?`
5. Envoie le message et **attends** (20–90 s), sans F5.

**Résultat attendu :**

- ton message utilisateur apparaît immédiatement ;
- la réponse de l’assistant arrive ensuite dans le fil (parfois après un court polling) ;
- la réponse s’appuie sur le contenu du support et peut afficher des **citations** / extraits ;
- en cas d’échec Ollama / API, un **toast rouge** d’erreur apparaît (pas un crash silencieux).

### Étape E — Effacer l’historique (modale)

1. Clique sur **Effacer l’historique** (ou action équivalente).

**Résultat attendu :**

- une **modale** « Effacer l’historique ? » s’affiche ;
- Annuler ne change rien ;
- confirmer affiche un **toast vert** du type « Historique supprimé » et vide le fil.

### Étape F — Exercices et évaluation

1. Va dans **Exercices & évals**.
2. Choisis le document source `Sécurité au travail` (ou le titre que tu as donné).
3. Type d’exercice : par exemple **QCM**.
4. Thème (si demandé) : `prévention`.
5. Lance la **génération** et attends la fin (peut être long).

**Résultat attendu :**

- un **toast vert** « Exercice généré » (ou message équivalent) ;
- l’exercice apparaît dans la liste ;
- les sujets / thèmes ne doivent pas rester uniquement sur un vague « général » si le contenu du support permet mieux.

6. Sélectionne l’exercice, réponds aux questions, clique sur **Soumettre**.

**Résultat attendu :**

- un **toast vert** « Correction effectuée » (ou équivalent) avec le score ;
- le feedback / score est visible dans l’interface.

### Étape G — Module langues

Va dans **Langues**.

#### G1 — Grammaire

1. Laisse la phrase d’exemple fautive (ou saisis une phrase avec une faute).
2. Clique sur **Corriger**.

**Résultat attendu :** toast vert « Correction terminée » et affichage de la correction.

#### G2 — Compréhension écrite

1. Sélectionne le document `Sécurité au travail`.
2. Clique sur **Générer un exercice**.

**Résultat attendu :** toast vert « Exercice généré » et un exercice de compréhension basé sur le support.  
Sans document sélectionné : toast d’avertissement (pas un plantage).

#### G3 — Prononciation

1. Utilise l’action **Analyser** selon l’UI (avec ou sans audio selon ton installation).

**Résultat attendu :** toast vert « Analyse terminée » (la partie audio avancée peut être un stub / limitée selon les dépendances optionnelles).

### Étape H — Dashboard formateur

1. Retourne sur **Pilotage**.

**Résultat attendu :**

- le titre reste **Pilotage** ;
- des indicateurs / statistiques liés au suivi de groupe ou à l’activité sont visibles (même s’ils sont encore partiels selon les données générées) ;
- l’export CSV, s’il est proposé, télécharge un fichier sans erreur.

---

## 12. Parcours de test apprenant

1. Déconnecte-toi (lien en bas de la sidebar).
2. Connecte-toi avec `apprenant@demo.local` / `learner123`.

### 12.1 Navigation apprenant

**Résultat attendu — sidebar uniquement :**

- **Progression**
- **Tuteur IA**
- **S’entraîner**
- **Langues**

Il ne doit **pas** y avoir de menu **Supports** : l’apprenant n’importe pas les contenus pédagogiques.

### 12.2 Dashboard

Le titre de page doit être **Progression**, avec un sous-titre orienté entraînement personnel (pas « Pilotage »).

### 12.3 Tuteur et entraînement

1. **Tuteur IA** : pose une question sur le cours déjà indexé par le formateur.  
   **Résultat attendu :** réponse contextuelle (si le document est toujours `indexed` dans l’organisation).
2. **S’entraîner** : génère ou ouvre un exercice, soumets une tentative.  
   **Résultat attendu :** toast de succès / score affiché.

### 12.4 Langues

Refais rapidement grammaire / compréhension (avec doc) / analyse : les toasts doivent être identiques à ceux du formateur.

---

## 13. Parcours de test administrateur

1. Déconnecte-toi.
2. Connecte-toi avec `admin@demo.local` / `admin123`.

### 13.1 Navigation admin

**Résultat attendu — sidebar :**

- **Supervision**
- **Gestion supports**
- **Assistance pédagogique**
- **Exercices**
- **Langues**

### 13.2 Dashboard

Le titre doit être **Supervision**, avec une formulation de suivi global / organisation.

### 13.3 Contrôle rapide des écrans

Ouvre successivement Gestion supports, Assistance pédagogique, Exercices, Langues.

**Résultat attendu :**

- les pages se chargent sans erreur ;
- les actions destructives utilisent des **modales** ;
- les succès / erreurs utilisent des **toasts**.

---

## 14. Tests techniques (pytest)

Ces tests vérifient que l’API de base répond, **sans dépendre** de Postgres grâce à `SKIP_DB_INIT`.

Dans un terminal (tu peux temporairement arrêter uvicorn, ou utiliser un autre shell) :

```powershell
cd backend
.\.venv\Scripts\activate
pytest -q
```

**Résultat attendu :**

- au moins **2 tests verts** (`test_api_health` et `test_api_root`) ;
- aucune erreur d’import ;
- pas de dépendance obligatoire à une base live pour ces tests.

Optionnel : le script PowerShell `formia_e2e.ps1` à la racine peut rejouer un parcours automatisé si tu l’utilises dans ton environnement.

---

## 15. Démarrage quotidien et après un git pull

### 15.1 Chaque jour (une fois l’installation faite)

1. Allumer **Docker Desktop**.
2. Allumer **Ollama**.
3. À la racine du projet :

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

Tu n’as en principe **pas** besoin de refaire `pip install`, `npm install` ou `ollama pull` à chaque fois.

### 15.2 Après un `git pull`

```powershell
git pull
```

Puis, selon ce qui a changé :

```powershell
# Backend
cd backend
.\.venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ..\frontend
npm install
```

Relance ensuite API + front comme d’habitude. Si `backend/.env.example` a changé, compare-le avec ton `.env` local et ajoute les nouvelles variables manquantes.

---

## 16. Problèmes fréquents et solutions

### `ollama` n’est pas reconnu

- Ferme et rouvre le terminal (ou Cursor).
- Ou utilise le chemin complet vers `ollama.exe` (section 3.5).

### Port 8000 déjà utilisé / WinError 10013

Une ancienne instance d’uvicorn tourne encore.

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Puis relance uvicorn.

### `Failed to fetch` dans le navigateur

Causes les plus fréquentes :

- l’API n’est pas démarrée sur `:8000` ;
- `frontend/.env.local` absent ou incorrect ;
- mauvais CORS / mauvaise URL.

Vérifie http://localhost:8000/api/health, corrige `.env.local`, recharge le front.

### Document en statut `failed`

Ollama n’est pas lancé, ou les modèles manquent. Vérifie `ollama list`, relance Ollama, réimporte le fichier.

### Chat : « aucun contenu indexé »

Aucun document `indexed`, ou tu es sur une ancienne conversation. Importe un support, attends `indexed`, puis **Nouvelle conversation**.

### Pas de toast / pas de modale moderne

Recharge la page (F5) pour prendre le dernier build frontend. Vérifie que tu es bien sur le code à jour (`git pull`).

### Sidebar identique pour tous les rôles

Recharge après connexion avec le bon compte. Chaque rôle a ses propres libellés (Pilotage / Progression / Supervision).

### Conflit Git au `pull`

Des fichiers locaux non suivis bloquent l’écriture. Supprime ou déplace les fichiers listés par Git, puis refais `git pull`.

### Chemin avec accents qui casse le terminal

Utilise la jonction `Documents\agent-formation` (section 4.3).

---

## 17. Checklist finale

Coche mentalement avant de considérer que « tout marche » :

### Installation

- [ ] Docker Desktop démarré
- [ ] `docker compose up -d postgres` OK
- [ ] Ollama ouvert + `llama3.2` et `nomic-embed-text` présents
- [ ] `backend/.env` créé
- [ ] `frontend/.env.local` créé
- [ ] API répond sur `/api/health`
- [ ] Front accessible sur http://localhost:3000

### UX professionnelle

- [ ] Toasts verts / rouges en haut à droite
- [ ] Plus de `confirm()` / `alert()` natifs sur suppression et effacement d’historique
- [ ] Menus différents formateur / apprenant / admin
- [ ] Titres dashboard : Pilotage / Progression / Supervision

### Parcours métier

- [ ] Login formateur OK
- [ ] Au moins un support au statut **`indexed`**
- [ ] Chat tuteur avec réponse (sans F5)
- [ ] Exercice généré + tentative notée
- [ ] Module langues : toasts OK
- [ ] Login apprenant : pas de menu Supports
- [ ] Login admin : Supervision visible
- [ ] `pytest -q` : tests verts

Quand cette checklist est verte, tu as sur l’ordinateur le même socle fonctionnel que sur la machine de référence, prêt pour une démo de A à Z.

---

## Architecture locale (rappel)

```text
Navigateur (localhost:3000)
    → Frontend Next.js
        → API FastAPI (localhost:8000)
            → PostgreSQL + pgvector (Docker, port hôte 5433)
            → Ollama (localhost:11434) pour LLM + embeddings
```

---

*Document Formia — Agent IA de formation et d’évaluation pédagogique.*  
*Guide unique : récupération Git, lancement, et tests A→Z avec résultats attendus.*
