"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  api,
  LearnerProgress,
  LearnerStats,
  ScorePoint,
  TrainerStats,
  WeakTopicStat,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function practiceHref(topic: string, exerciseId?: string | null) {
  const params = new URLSearchParams({ topic });
  if (exerciseId) params.set("exercise", exerciseId);
  return `/exercises?${params.toString()}`;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [learner, setLearner] = useState<LearnerStats | null>(null);
  const [trainer, setTrainer] = useState<TrainerStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        if (user.role === "learner") {
          setLearner(await api.learnerStats());
          setTrainer(null);
          return;
        }
        setTrainer(await api.trainerStats());
        setLearner(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur dashboard");
      }
    })();
  }, [user]);

  const role = user?.role;
  const headerTitle = role === "learner" ? "Progression" : role === "admin" ? "Supervision" : "Pilotage";
  const headerSubtitle =
    role === "learner"
      ? "Ton entraînement, tes scores et tes points faibles."
      : role === "admin"
        ? "Vue globale sur l’usage et les difficultés récurrentes."
        : "Suivi du groupe, scores par apprenant et reporting.";

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

  const practiceTopics = learner?.practice_topics?.length
    ? learner.practice_topics
    : (learner?.weak_topics || []).map((topic) => ({ topic, count: 1 }));

  return (
    <div className="space-y-8 rise">
      <header>
        <h1 className="font-display text-4xl">{headerTitle}</h1>
        <p className="text-[var(--muted)] mt-2">{headerSubtitle}</p>
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

      {learner && practiceTopics.length > 0 && (
        <section className="surface p-6">
          <h2 className="font-display text-2xl mb-3">Points à retravailler</h2>
          <div className="flex flex-wrap gap-2">
            {practiceTopics.map((item) => (
              <PracticeChip key={item.topic} item={item} />
            ))}
          </div>
        </section>
      )}

      {learner && learner.recent_attempts.length > 0 && (
        <section className="surface p-6">
          <h2 className="font-display text-2xl mb-3">Dernières tentatives</h2>
          <ul className="space-y-2 text-sm">
            {learner.recent_attempts.map((attempt) => (
              <li key={attempt.id} className="flex justify-between gap-3">
                <span className="text-[var(--muted)]">
                  {new Date(attempt.created_at).toLocaleString("fr-FR")}
                </span>
                <span className="font-medium">
                  {attempt.score ?? "—"}/{attempt.max_score ?? "—"}
                </span>
              </li>
            ))}
          </ul>
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

          <div className="surface p-6">
            <h3 className="font-medium mb-4">Progression du groupe (14 jours)</h3>
            <ScoreChart points={trainer.score_over_time || []} />
          </div>

          <div className="surface p-6 overflow-x-auto">
            <h3 className="font-medium mb-4">Scores par apprenant</h3>
            <LearnerTable learners={trainer.learners || []} />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="surface p-6">
              <h3 className="font-medium mb-3">Difficultés récurrentes</h3>
              <ul className="space-y-2 text-sm">
                {(trainer.recurrent_weak_topics || []).length === 0 && (
                  <li className="text-[var(--muted)]">Pas encore de données</li>
                )}
                {(trainer.recurrent_weak_topics || []).map((w) => (
                  <li key={w.topic} className="flex justify-between gap-3 items-center">
                    <PracticeChip item={w} />
                    <span className="text-[var(--muted)] shrink-0">{w.count}</span>
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

function PracticeChip({ item }: { item: WeakTopicStat | { topic: string; count?: number; exercise_id?: string | null } }) {
  return (
    <Link
      href={practiceHref(item.topic, item.exercise_id)}
      className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[var(--accent-soft)] text-sm hover:bg-[var(--accent)] hover:text-white transition"
    >
      <span>{item.topic}</span>
      <span className="text-xs opacity-80">Retravailler</span>
    </Link>
  );
}

function LearnerTable({ learners }: { learners: LearnerProgress[] }) {
  if (learners.length === 0) {
    return <p className="text-sm text-[var(--muted)]">Aucun apprenant dans l’organisation.</p>;
  }
  return (
    <table className="w-full text-sm text-left">
      <thead>
        <tr className="text-[var(--muted)] border-b border-[var(--line)]">
          <th className="py-2 pr-3 font-medium">Apprenant</th>
          <th className="py-2 pr-3 font-medium">Tentatives</th>
          <th className="py-2 pr-3 font-medium">Moyenne</th>
          <th className="py-2 pr-3 font-medium">Dernière activité</th>
          <th className="py-2 font-medium">À retravailler</th>
        </tr>
      </thead>
      <tbody>
        {learners.map((row) => (
          <tr key={row.user_id} className="border-b border-[var(--line)]/70">
            <td className="py-3 pr-3">
              <div className="font-medium">{row.full_name}</div>
              <div className="text-xs text-[var(--muted)]">{row.email}</div>
            </td>
            <td className="py-3 pr-3">{row.attempts_count}</td>
            <td className="py-3 pr-3">{row.average_score != null ? `${row.average_score}%` : "—"}</td>
            <td className="py-3 pr-3 text-[var(--muted)]">
              {row.last_attempt_at ? new Date(row.last_attempt_at).toLocaleDateString("fr-FR") : "—"}
            </td>
            <td className="py-3">
              {row.weak_topics.length === 0 ? (
                <span className="text-[var(--muted)]">—</span>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {row.weak_topics.map((topic) => (
                    <Link
                      key={topic}
                      href={practiceHref(topic)}
                      className="px-2 py-0.5 rounded-md bg-[var(--accent-soft)] text-xs hover:underline"
                    >
                      {topic}
                    </Link>
                  ))}
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ScoreChart({ points }: { points: ScorePoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-[var(--muted)]">Pas encore de données.</p>;
  }
  const hasData = points.some((p) => p.attempts_count > 0);
  if (!hasData) {
    return <p className="text-sm text-[var(--muted)]">Aucune tentative sur les 14 derniers jours.</p>;
  }
  return (
    <div className="flex items-end gap-1 h-36">
      {points.map((point) => {
        const height = Math.max(point.average_score || 0, point.attempts_count ? 4 : 0);
        return (
          <div key={point.date} className="flex-1 min-w-0 flex flex-col items-center justify-end h-full gap-1">
            <div
              className="w-full max-w-6 rounded-t bg-[var(--accent)]/80"
              style={{ height: `${height}%` }}
              title={`${point.date} : ${point.average_score ?? "—"}% (${point.attempts_count} tentative(s))`}
            />
            <span className="text-[10px] text-[var(--muted)] truncate w-full text-center">
              {point.date.slice(8)}
            </span>
          </div>
        );
      })}
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
