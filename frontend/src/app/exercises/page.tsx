"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, AttemptItem, DocumentItem, ExerciseItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Question = {
  id: string;
  stem?: string;
  choices?: string[];
  correct_index?: number;
  type?: string;
  expected_points?: string[];
  max_score?: number;
};

export default function ExercisesPage() {
  const { user } = useAuth();
  const [exercises, setExercises] = useState<ExerciseItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selected, setSelected] = useState<ExerciseItem | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<AttemptItem | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [genType, setGenType] = useState("qcm");
  const [genDoc, setGenDoc] = useState("");
  const [genTopic, setGenTopic] = useState("");
  const [genCount, setGenCount] = useState(5);

  async function load() {
    const [ex, docs] = await Promise.all([api.exercises(), api.documents()]);
    setExercises(ex);
    setDocuments(docs.filter((d) => d.status === "indexed"));
    if (!genDoc && docs[0]) setGenDoc(docs.find((d) => d.status === "indexed")?.id || "");
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  const questions: Question[] = useMemo(() => {
    if (!selected) return [];
    if (selected.exercise_type === "case") {
      const c = selected.payload.case as { questions?: Question[] } | undefined;
      return c?.questions || [];
    }
    return (selected.payload.questions as Question[]) || [];
  }, [selected]);

  const caseBrief =
    selected?.exercise_type === "case"
      ? ((selected.payload.case as { brief?: string })?.brief || "")
      : "";

  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.generateExercise({
        document_id: genDoc,
        exercise_type: genType,
        topic: genTopic || undefined,
        question_count: genCount,
        time_limit_seconds: genType === "exam" ? 1800 : undefined,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Génération échouée");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const attempt = await api.submitAttempt(selected.id, answers);
      setResult(attempt);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Soumission échouée");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8 rise">
      <header>
        <h1 className="font-display text-4xl">Exercices & évaluations</h1>
        <p className="text-[var(--muted)] mt-2">
          QCM, questions ouvertes, études de cas et simulations d’examen.
        </p>
      </header>

      {(user?.role === "trainer" || user?.role === "admin") && (
        <form onSubmit={generate} className="surface p-6 grid md:grid-cols-2 gap-4">
          {documents.length === 0 && (
            <div className="md:col-span-2 rounded-xl border border-[var(--warn)] bg-[#fff7ed] px-4 py-3 text-sm">
              Aucun document <strong>indexed</strong>. Importez d’abord un support dans{" "}
              <a className="underline text-[var(--accent)]" href="/documents">
                Supports
              </a>
              , puis revenez générer un exercice.
            </div>
          )}
          <label className="text-sm">
            Document source
            <select
              className="input mt-1"
              value={genDoc}
              onChange={(e) => setGenDoc(e.target.value)}
              required
              disabled={documents.length === 0}
            >
              <option value="">Choisir…</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Type
            <select className="input mt-1" value={genType} onChange={(e) => setGenType(e.target.value)}>
              <option value="qcm">QCM</option>
              <option value="open">Questions ouvertes</option>
              <option value="case">Étude de cas</option>
              <option value="exam">Simulation d’examen</option>
            </select>
          </label>
          <label className="text-sm">
            Thème (optionnel)
            <input className="input mt-1" value={genTopic} onChange={(e) => setGenTopic(e.target.value)} />
          </label>
          <label className="text-sm">
            Nombre de questions
            <input
              type="number"
              min={1}
              max={20}
              className="input mt-1"
              value={genCount}
              onChange={(e) => setGenCount(Number(e.target.value))}
            />
          </label>
          <div className="md:col-span-2">
            <button className="btn" disabled={busy || documents.length === 0 || !genDoc} type="submit">
              {busy ? "Génération…" : "Générer depuis le contenu"}
            </button>
          </div>
        </form>
      )}

      {error && <p className="text-[var(--danger)]">{error}</p>}

      <div className="grid lg:grid-cols-[280px_1fr] gap-6">
        <ul className="space-y-2">
          {exercises.map((ex) => (
            <li key={ex.id}>
              <button
                type="button"
                className={`w-full text-left surface p-4 ${
                  selected?.id === ex.id ? "ring-2 ring-[var(--accent)]" : ""
                }`}
                onClick={() => {
                  setSelected(ex);
                  setAnswers({});
                  setResult(null);
                }}
              >
                <p className="font-medium">{ex.title}</p>
                <p className="text-xs text-[var(--muted)] uppercase mt-1">{ex.exercise_type}</p>
              </button>
            </li>
          ))}
        </ul>

        <div className="surface p-6 space-y-5">
          {!selected && <p className="text-[var(--muted)]">Sélectionnez un exercice.</p>}
          {selected && (
            <>
              <h2 className="font-display text-2xl">{selected.title}</h2>
              {caseBrief && <p className="text-sm bg-[var(--accent-soft)] p-4 rounded-xl">{caseBrief}</p>}
              {selected.time_limit_seconds && (
                <p className="text-sm text-[var(--warn)]">
                  Temps indicatif : {Math.round(selected.time_limit_seconds / 60)} min
                </p>
              )}
              {questions.map((q) => (
                <div key={q.id} className="space-y-2 border-t border-[var(--line)] pt-4">
                  <p className="font-medium">{q.stem}</p>
                  {q.choices ? (
                    <div className="space-y-2">
                      {q.choices.map((choice, idx) => (
                        <label key={idx} className="flex gap-2 items-center text-sm">
                          <input
                            type="radio"
                            name={q.id}
                            checked={answers[q.id] === idx}
                            onChange={() => setAnswers((a) => ({ ...a, [q.id]: idx }))}
                          />
                          {choice}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <textarea
                      className="input min-h-24"
                      value={(answers[q.id] as string) || ""}
                      onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    />
                  )}
                </div>
              ))}
              <button type="button" className="btn" disabled={busy} onClick={submit}>
                {busy ? "Correction…" : "Soumettre"}
              </button>
              {result && (
                <div className="bg-[var(--accent-soft)] rounded-xl p-4 space-y-2">
                  <p className="font-medium">
                    Score : {result.score}/{result.max_score}
                  </p>
                  {result.weak_topics && result.weak_topics.length > 0 && (
                    <p className="text-sm">Faiblesses : {result.weak_topics.join(", ")}</p>
                  )}
                  <pre className="text-xs whitespace-pre-wrap overflow-auto">
                    {JSON.stringify(result.feedback, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
