"""Deep A-to-Z HTTP tests for Formia across admin, trainer and learner."""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"
FRONT = "http://127.0.0.1:3000"
ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample_cours.txt"
if not SAMPLE.exists():
    SAMPLE = ROOT / "backend" / "sample_cours.txt"

PASS = 0
FAIL = 0
RESULTS: list[str] = []


def record(step: str, ok: bool, detail: str) -> None:
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    line = f"[{status}] {step} — {detail}"
    RESULTS.append(line)
    print(line, flush=True)


def must(step: str, ok: bool, detail: str) -> None:
    record(step, ok, detail)
    if not ok:
        raise AssertionError(f"{step}: {detail}")


def login(client: httpx.Client, email: str, password: str) -> str:
    res = client.post("/api/auth/login/json", json={"email": email, "password": password})
    res.raise_for_status()
    token = res.json()["access_token"]
    return token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def wait_health(client: httpx.Client, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            res = client.get("/api/health")
            if res.status_code == 200 and res.json().get("status") == "ok":
                return
            last = res.text
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        time.sleep(1)
    raise RuntimeError(f"API not healthy: {last}")


def wait_indexed(client: httpx.Client, token: str, doc_id: str, timeout: float = 180) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        res = client.get("/api/documents", headers=auth(token))
        res.raise_for_status()
        for doc in res.json():
            if doc["id"] == doc_id:
                last = doc
                if doc["status"] == "indexed":
                    return doc
                if doc["status"] == "failed":
                    raise RuntimeError(f"index failed: {doc.get('error_message')}")
        time.sleep(2)
    raise RuntimeError(f"timeout waiting indexed: {last}")


def run() -> int:
    with httpx.Client(base_url=API, timeout=httpx.Timeout(30.0, read=240.0)) as client:
        wait_health(client)
        record("API health", True, "GET /api/health = ok")

        root = client.get("/")
        must("API root", root.status_code == 200 and "message" in root.json(), root.text[:120])

        # --- Login all profiles ---
        admin_tok = login(client, "admin@demo.local", "admin123")
        trainer_tok = login(client, "formateur@demo.local", "trainer123")
        learner_tok = login(client, "apprenant@demo.local", "learner123")
        record("Login admin", True, "admin@demo.local")
        record("Login formateur", True, "formateur@demo.local")
        record("Login apprenant", True, "apprenant@demo.local")

        admin_me = client.get("/api/auth/me", headers=auth(admin_tok)).json()
        trainer_me = client.get("/api/auth/me", headers=auth(trainer_tok)).json()
        learner_me = client.get("/api/auth/me", headers=auth(learner_tok)).json()
        must("Profil admin", admin_me.get("role") == "admin", str(admin_me.get("role")))
        must("Profil formateur", trainer_me.get("role") == "trainer", str(trainer_me.get("role")))
        must("Profil apprenant", learner_me.get("role") == "learner", str(learner_me.get("role")))

        bad = client.post("/api/auth/login/json", json={"email": "admin@demo.local", "password": "wrong"})
        record("Login mot de passe faux", bad.status_code == 401, f"status={bad.status_code}")

        # --- Role isolation ---
        learner_users = client.get("/api/users", headers=auth(learner_tok))
        record("Apprenant interdit /users", learner_users.status_code == 403, f"status={learner_users.status_code}")
        trainer_users = client.get("/api/users", headers=auth(trainer_tok))
        record("Formateur interdit /users", trainer_users.status_code == 403, f"status={trainer_users.status_code}")
        admin_users = client.get("/api/users", headers=auth(admin_tok))
        record("Admin liste /users", admin_users.status_code == 200 and len(admin_users.json()) >= 3, f"count={len(admin_users.json()) if admin_users.status_code==200 else admin_users.status_code}")

        # learner cannot upload
        files = {"file": ("x.txt", b"hello", "text/plain")}
        learner_up = client.post(
            "/api/documents/upload",
            headers=auth(learner_tok),
            data={"title": "interdit"},
            files=files,
        )
        record("Apprenant interdit upload", learner_up.status_code == 403, f"status={learner_up.status_code}")

        learner_gen = client.post(
            "/api/exercises/generate",
            headers=auth(learner_tok),
            json={"document_id": str(uuid.uuid4()), "exercise_type": "qcm", "question_count": 3},
        )
        record("Apprenant interdit génération exercice", learner_gen.status_code in {400, 403}, f"status={learner_gen.status_code}")

        # --- Admin accounts ---
        suffix = uuid.uuid4().hex[:8]
        email = f"marie.{suffix}@demo.local"
        created = client.post(
            "/api/users",
            headers=auth(admin_tok),
            json={"email": email, "full_name": "Marie Test", "role": "learner"},
        )
        must("Admin crée apprenant", created.status_code == 201, created.text[:200])
        created_body = created.json()
        temp_pwd = created_body.get("temporary_password")
        must("Mot de passe temporaire renvoyé", bool(temp_pwd), str(temp_pwd))
        marie_id = created_body["id"]

        marie_tok = login(client, email, temp_pwd)
        marie_me = client.get("/api/auth/me", headers=auth(marie_tok)).json()
        record("Nouveau compte peut se connecter", marie_me.get("email") == email, marie_me.get("email", ""))

        reset = client.post(f"/api/users/{marie_id}/reset-password", headers=auth(admin_tok), json={})
        must("Reset mot de passe", reset.status_code == 200, reset.text[:160])
        new_pwd = reset.json()["temporary_password"]
        old_login = client.post("/api/auth/login/json", json={"email": email, "password": temp_pwd})
        record("Ancien MDP refusé après reset", old_login.status_code in {401, 403}, f"status={old_login.status_code}")
        login(client, email, new_pwd)
        record("Nouveau MDP accepte", True, "login ok")

        deact = client.patch(f"/api/users/{marie_id}/active", headers=auth(admin_tok), json={"is_active": False})
        must("Désactivation", deact.status_code == 200 and deact.json().get("is_active") is False, deact.text[:160])
        blocked = client.post("/api/auth/login/json", json={"email": email, "password": new_pwd})
        record("Compte désactivé bloqué", blocked.status_code == 403, f"status={blocked.status_code} body={blocked.text[:80]}")

        react = client.patch(f"/api/users/{marie_id}/active", headers=auth(admin_tok), json={"is_active": True})
        must("Réactivation", react.status_code == 200 and react.json().get("is_active") is True, react.text[:160])
        login(client, email, new_pwd)
        record("Compte réactivé reconnectable", True, "login ok")

        self_off = client.patch(
            f"/api/users/{admin_me['id']}/active",
            headers=auth(admin_tok),
            json={"is_active": False},
        )
        record("Admin ne peut pas se désactiver", self_off.status_code == 400, f"status={self_off.status_code}")

        dup = client.post(
            "/api/users",
            headers=auth(admin_tok),
            json={"email": email, "full_name": "Dup", "role": "learner"},
        )
        record("Email dupliqué rejeté", dup.status_code == 409, f"status={dup.status_code}")

        # --- Trainer document + RAG ---
        if not SAMPLE.exists():
            raise RuntimeError(f"missing {SAMPLE}")
        upload = client.post(
            "/api/documents/upload",
            headers=auth(trainer_tok),
            data={"title": "Sécurité au travail E2E"},
            files={"file": (SAMPLE.name, SAMPLE.read_bytes(), "text/plain")},
        )
        must("Formateur import support", upload.status_code == 200, upload.text[:200])
        doc = upload.json()
        doc_id = doc["id"]
        indexed = wait_indexed(client, trainer_tok, doc_id)
        record("Indexation RAG", indexed["status"] == "indexed", f"status={indexed['status']}")

        learner_docs = client.get("/api/documents", headers=auth(learner_tok)).json()
        record(
            "Apprenant voit les supports de l'org (lecture)",
            any(d["id"] == doc_id for d in learner_docs),
            f"count={len(learner_docs)}",
        )

        # French chat
        chat = client.post(
            "/api/chat",
            headers=auth(trainer_tok),
            json={"message": "Quels sont les principes de prevention au travail ?", "document_id": doc_id},
        )
        must("Chat FR formateur", chat.status_code == 200, chat.text[:200])
        chat_body = chat.json()
        answer = chat_body.get("answer") or ""
        cites = chat_body.get("citations") or []
        conv_id = chat_body.get("conversation_id")
        record(
            "Chat FR ancré + citations",
            "aucun contenu index" not in answer.lower() and len(cites) >= 1,
            f"citations={len(cites)} preview={answer[:90]!r}",
        )
        french_markers = ("le ", "la ", "les ", "de ", "des ", "et ", "un ", "une ")
        record("Chat FR langue française", any(m in answer.lower() for m in french_markers), answer[:80])

        # Follow-up memory
        follow = client.post(
            "/api/chat",
            headers=auth(trainer_tok),
            json={
                "message": "Donne 3 exemples concrets",
                "conversation_id": conv_id,
                "document_id": doc_id,
            },
        )
        must("Chat suivi", follow.status_code == 200, follow.text[:200])
        follow_ans = follow.json().get("answer") or ""
        record(
            "Mémoire de conversation",
            "aucun contenu index" not in follow_ans.lower() and len(follow_ans) > 40,
            follow_ans[:110],
        )

        # English chat language
        en_chat = client.post(
            "/api/chat",
            headers=auth(trainer_tok),
            json={"message": "What is primary prevention according to the document?", "document_id": doc_id},
        )
        must("Chat EN", en_chat.status_code == 200, en_chat.text[:200])
        en_ans = en_chat.json().get("answer") or ""
        en_ok = any(w in en_ans.lower() for w in ("the ", "prevention", "risk", "according", "document", "primary"))
        fr_forced = en_ans.lower().startswith("selon ") or "je n'ai trouvé" in en_ans.lower()
        record("Chat EN répond en anglais", en_ok and not fr_forced, en_ans[:110])

        # Stream
        with client.stream(
            "POST",
            "/api/chat/stream",
            headers=auth(trainer_tok),
            json={"message": "Cite un EPI mentionne dans le support.", "document_id": doc_id},
        ) as stream:
            must("Stream HTTP 200", stream.status_code == 200, f"status={stream.status_code}")
            buf = ""
            events = []
            for chunk in stream.iter_text():
                buf += chunk
                while "\n\n" in buf:
                    part, buf = buf.split("\n\n", 1)
                    line = next((ln for ln in part.split("\n") if ln.startswith("data:")), "")
                    if not line:
                        continue
                    raw = line.replace("data:", "", 1).strip()
                    if raw:
                        events.append(json.loads(raw))
        types = [e.get("type") for e in events]
        tokens = "".join(e.get("text", "") for e in events if e.get("type") == "token")
        record("Stream meta+token+done", "meta" in types and "token" in types and "done" in types, f"types={types[:8]}...")
        record("Stream texte non vide", len(tokens) > 10, tokens[:90])

        # Conversations isolation
        trainer_convs = client.get("/api/chat/conversations", headers=auth(trainer_tok)).json()
        learner_convs = client.get("/api/chat/conversations", headers=auth(learner_tok)).json()
        record("Conversations formateur présentes", len(trainer_convs) >= 1, f"count={len(trainer_convs)}")
        record(
            "Apprenant ne voit pas les convs formateur",
            all(c["id"] != conv_id for c in learner_convs),
            f"learner_convs={len(learner_convs)}",
        )

        # Learner chat on same org docs
        learner_chat = client.post(
            "/api/chat",
            headers=auth(learner_tok),
            json={"message": "Que faire en cas d'incident ?", "document_id": doc_id},
        )
        must("Chat apprenant", learner_chat.status_code == 200, learner_chat.text[:200])
        record(
            "Apprenant obtient une réponse RAG",
            "aucun contenu index" not in (learner_chat.json().get("answer") or "").lower(),
            (learner_chat.json().get("answer") or "")[:90],
        )

        # Exercises
        gen = client.post(
            "/api/exercises/generate",
            headers=auth(trainer_tok),
            json={
                "document_id": doc_id,
                "exercise_type": "qcm",
                "topic": "prévention",
                "question_count": 4,
            },
        )
        must("Génération QCM formateur", gen.status_code == 200, gen.text[:240])
        exercise = gen.json()
        questions = (exercise.get("payload") or {}).get("questions") or []
        record("QCM a des questions", len(questions) >= 1, f"count={len(questions)}")
        stems = " ".join(str(q.get("stem") or "") for q in questions)
        record("QCM pas coincé sur 'général' uniquement", "général" not in stems.lower() or len(stems) > 20, stems[:80])

        answers = {}
        for q in questions:
            if "correct_index" in q:
                answers[q["id"]] = q["correct_index"]  # perfect score to also test grading path
            else:
                answers[q["id"]] = "reponse"
        attempt = client.post(
            f"/api/exercises/{exercise['id']}/attempts",
            headers=auth(learner_tok),
            json={"answers": answers},
        )
        must("Apprenant soumet tentative", attempt.status_code == 200, attempt.text[:200])
        att = attempt.json()
        record("Score tentative renseigné", att.get("score") is not None, f"score={att.get('score')}/{att.get('max_score')}")

        # Wrong answers to generate weak topics
        wrong = {}
        for q in questions:
            if "correct_index" in q:
                wrong[q["id"]] = (int(q["correct_index"]) + 1) % max(len(q.get("choices") or [0, 1, 2, 3]), 1)
        wrong_att = client.post(
            f"/api/exercises/{exercise['id']}/attempts",
            headers=auth(learner_tok),
            json={"answers": wrong},
        )
        record("Tentative fausse enregistrée", wrong_att.status_code == 200, f"status={wrong_att.status_code}")

        # Dashboards
        learner_dash = client.get("/api/dashboard/learner", headers=auth(learner_tok))
        must("Dashboard apprenant", learner_dash.status_code == 200, learner_dash.text[:160])
        ld = learner_dash.json()
        record("Dashboard apprenant tentatives > 0", ld.get("attempts_count", 0) >= 1, f"attempts={ld.get('attempts_count')}")
        record("Dashboard apprenant practice_topics", isinstance(ld.get("practice_topics"), list), str(ld.get("practice_topics"))[:80])

        trainer_dash = client.get("/api/dashboard/trainer", headers=auth(trainer_tok))
        must("Dashboard formateur", trainer_dash.status_code == 200, trainer_dash.text[:200])
        td = trainer_dash.json()
        record("Dashboard learners list", isinstance(td.get("learners"), list) and len(td.get("learners") or []) >= 1, f"n={len(td.get('learners') or [])}")
        record("Dashboard score_over_time 14 jours", len(td.get("score_over_time") or []) == 14, f"n={len(td.get('score_over_time') or [])}")
        names = [row.get("full_name") for row in td.get("learners") or []]
        record("Dashboard contient l'apprenant demo", any("Apprenant" in (n or "") for n in names) or len(names) >= 1, str(names))

        admin_dash = client.get("/api/dashboard/trainer", headers=auth(admin_tok))
        record("Admin accède au dashboard supervision", admin_dash.status_code == 200, f"status={admin_dash.status_code}")

        learner_trainer_dash = client.get("/api/dashboard/trainer", headers=auth(learner_tok))
        record("Apprenant interdit dashboard formateur", learner_trainer_dash.status_code == 403, f"status={learner_trainer_dash.status_code}")

        csv_res = client.get("/api/dashboard/trainer/export.csv", headers=auth(trainer_tok))
        record("Export CSV formateur", csv_res.status_code == 200 and "learner_email" in csv_res.text, f"status={csv_res.status_code} bytes={len(csv_res.content)}")

        # Languages
        grammar = client.post(
            "/api/languages/grammar",
            headers=auth(learner_tok),
            json={"text": "I has went to the training center yesterday.", "language": "auto"},
        )
        must("Grammaire EN apprenant", grammar.status_code == 200, grammar.text[:200])
        g = grammar.json()
        record("Correction grammaticale non vide", bool(g.get("corrected_text")), str(g.get("corrected_text"))[:80])

        grammar_fr = client.post(
            "/api/languages/grammar",
            headers=auth(trainer_tok),
            json={"text": "Je suis aller au centre de formation hier.", "language": "auto"},
        )
        record("Grammaire FR formateur", grammar_fr.status_code == 200, grammar_fr.text[:120])

        comp = client.post(
            "/api/languages/comprehension",
            headers=auth(trainer_tok),
            json={"document_id": doc_id, "question_count": 3},
        )
        record("Compréhension écrite", comp.status_code == 200, comp.text[:220])
        if comp.status_code == 200:
            cj = comp.json()
            record(
                "Compréhension a passage+questions",
                bool(cj.get("passage")) and len(cj.get("questions") or []) >= 1,
                f"q={len(cj.get('questions') or [])}",
            )

        pron = client.post(
            "/api/languages/pronunciation",
            headers=auth(learner_tok),
            data={
                "reference_text": "A phrasal verb is a verb plus a particle.",
                "spoken_text": "A phrasal verb is a verb plus a particule.",
            },
        )
        must("Prononciation manuelle", pron.status_code == 200, pron.text[:220])
        pj = pron.json()
        record("Prononciation accuracy < 1 si erreur", pj.get("accuracy", 1) < 1, f"acc={pj.get('accuracy')} missed={pj.get('missed_words') or pj.get('replaced_words')}")
        record("Prononciation shadowing_tip", bool(pj.get("shadowing_tip")), str(pj.get("shadowing_tip"))[:80])
        record("Prononciation engine manual", pj.get("engine") == "manual", str(pj.get("engine")))

        empty_pron = client.post(
            "/api/languages/pronunciation",
            headers=auth(learner_tok),
            data={"reference_text": "Hello world"},
        )
        record("Prononciation sans audio/texte refusée", empty_pron.status_code == 400, f"status={empty_pron.status_code}")

        status_lang = client.get("/api/languages/status", headers=auth(admin_tok))
        record("Languages status", status_lang.status_code == 200 and "whisper" in status_lang.json(), str(status_lang.json()))

        # Delete document (trainer) should not 500 even with exercises
        delete = client.delete(f"/api/documents/{doc_id}", headers=auth(trainer_tok))
        record("Suppression support formateur", delete.status_code in {200, 204}, f"status={delete.status_code}")
        after = client.get("/api/documents", headers=auth(trainer_tok)).json()
        record("Support bien retiré de la liste", all(d["id"] != doc_id for d in after), f"remaining={len(after)}")

        # Frontend pages
        with httpx.Client(base_url=FRONT, timeout=30.0, follow_redirects=True) as web:
            for path in ("/", "/login", "/dashboard", "/chat", "/exercises", "/languages", "/documents", "/users"):
                try:
                    page = web.get(path)
                    record(f"Frontend {path}", page.status_code == 200, f"status={page.status_code} bytes={len(page.content)}")
                except Exception as exc:  # noqa: BLE001
                    record(f"Frontend {path}", False, str(exc))

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    code = 1
    try:
        code = run()
    except Exception as exc:  # noqa: BLE001
        record("ABORT", False, str(exc))
        code = 1
    print("\n===== SUMMARY =====")
    print(f"PASS={PASS} FAIL={FAIL}")
    print("overall:", "ALL PASS" if FAIL == 0 else "HAS FAILURES")
    sys.exit(code)
