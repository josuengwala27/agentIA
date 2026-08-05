"use client";

import { useEffect, useState } from "react";
import { api, LearnerStats, TrainerStats } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user } = useAuth();
  const [learner, setLearner] = useState<LearnerStats | null>(null);
  const [trainer, setTrainer] = useState<TrainerStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        setLearner(await api.learnerStats());
        if (user.role === "trainer" || user.role === "admin") {
          setTrainer(await api.trainerStats());
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur dashboard");
      }
    })();
  }, [user]);

  async function downloadCsv() {
    const token = localStorage.getItem("access_token");
    const res = await fetch(api.exportCsvUrl(), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rapport-formation.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-8 rise">
      <header>
        <h1 className="font-display text-4xl">Tableau de bord</h1>
        <p className="text-[var(--muted)] mt-2">Progression, difficultés et activité récente.</p>
      </header>
      {error && <p className="text-[var(--danger)]">{error}</p>}

      {learner && (
        <section className="grid md:grid-cols-3 gap-4">
          <Stat label="Tentatives" value={String(learner.attempts_count)} />
          <Stat
            label="Score moyen"
            value={learner.average_score != null ? `${learner.average_score}%` : "—"}
          />
          <Stat label="Supports indexés" value={String(learner.documents_available)} />
        </section>
      )}

      {learner && learner.weak_topics.length > 0 && (
        <section className="surface p-6">
          <h2 className="font-display text-2xl mb-3">Points à retravailler</h2>
          <div className="flex flex-wrap gap-2">
            {learner.weak_topics.map((t) => (
              <span key={t} className="px-3 py-1 rounded-lg bg-[var(--accent-soft)] text-sm">
                {t}
              </span>
            ))}
          </div>
        </section>
      )}

      {trainer && (
        <section className="space-y-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <h2 className="font-display text-2xl">Vue formateur</h2>
            <button type="button" className="btn btn-ghost" onClick={downloadCsv}>
              Export CSV
            </button>
          </div>
          <div className="grid md:grid-cols-4 gap-4">
            <Stat label="Apprenants" value={String(trainer.learners_count)} />
            <Stat label="Documents" value={`${trainer.indexed_documents}/${trainer.documents_count}`} />
            <Stat label="Tentatives groupe" value={String(trainer.attempts_count)} />
            <Stat
              label="Moyenne groupe"
              value={trainer.average_score != null ? `${trainer.average_score}%` : "—"}
            />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="surface p-6">
              <h3 className="font-medium mb-3">Difficultés récurrentes</h3>
              <ul className="space-y-2 text-sm">
                {trainer.recurrent_weak_topics.length === 0 && (
                  <li className="text-[var(--muted)]">Pas encore de données</li>
                )}
                {trainer.recurrent_weak_topics.map((w) => (
                  <li key={w.topic} className="flex justify-between">
                    <span>{w.topic}</span>
                    <span className="text-[var(--muted)]">{w.count}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="surface p-6">
              <h3 className="font-medium mb-3">Scores par type</h3>
              <ul className="space-y-2 text-sm">
                {trainer.score_by_exercise_type.length === 0 && (
                  <li className="text-[var(--muted)]">Pas encore de données</li>
                )}
                {trainer.score_by_exercise_type.map((s) => (
                  <li key={s.exercise_type} className="flex justify-between">
                    <span className="uppercase">{s.exercise_type}</span>
                    <span>{s.average_score}%</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface p-5">
      <p className="text-sm text-[var(--muted)]">{label}</p>
      <p className="font-display text-3xl mt-1">{value}</p>
    </div>
  );
}
