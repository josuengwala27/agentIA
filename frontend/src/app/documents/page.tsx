"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, DocumentItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";

export default function DocumentsPage() {
  const { user } = useAuth();
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const confirm = useConfirm();
  const { addToast } = useToast();

  async function load() {
    setDocs(await api.documents());
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file || !title) return;
    setBusy(true);
    setError("");
    try {
      await api.uploadDocument(title, file);
      setTitle("");
      setFile(null);
      await load();
      addToast({
        type: "success",
        title: "Support importé",
        message: "L’indexation a été lancée. Vérifie le statut du document dans la liste.",
        ttlMs: 4500,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Échec upload";
      setError(msg);
      addToast({ type: "error", title: "Import échoué", message: msg, ttlMs: 5500 });
    } finally {
      setBusy(false);
    }
  }

  if (user && !["admin", "trainer"].includes(user.role)) {
    return <p>Accès réservé aux formateurs.</p>;
  }

  return (
    <div className="space-y-8 rise max-w-4xl">
      <header>
        <h1 className="font-display text-4xl">Supports pédagogiques</h1>
        <p className="text-[var(--muted)] mt-2">
          Importez PDF, DOCX ou TXT. L’agent indexe le contenu sans générer le cours.
        </p>
        <p className="text-sm mt-2 text-[var(--accent)]">
          Règle d’or : n’utilisez le Tuteur / Exercices / Compréhension qu’après le statut{" "}
          <strong>indexed</strong> (pas pending, pas failed).
        </p>
      </header>

      <form onSubmit={onUpload} className="surface p-6 space-y-4">
        <label className="block text-sm">
          Titre
          <input className="input mt-1" value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="block text-sm">
          Fichier
          <input
            className="mt-1 block w-full text-sm"
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
        </label>
        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        <button className="btn" disabled={busy} type="submit">
          {busy ? "Indexation en cours…" : "Importer et indexer"}
        </button>
      </form>

      <ul className="space-y-3">
        {docs.map((d) => (
          <li key={d.id} className="surface p-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium">{d.title}</p>
              <p className="text-sm text-[var(--muted)]">
                {d.filename} ·{" "}
                <span
                  className={
                    d.status === "indexed"
                      ? "text-[var(--accent)] font-semibold"
                      : d.status === "failed"
                        ? "text-[var(--danger)] font-semibold"
                        : "text-[var(--warn)] font-semibold"
                  }
                >
                  {d.status}
                </span>
                {d.error_message ? ` — ${d.error_message}` : ""}
              </p>
              {d.status === "indexed" && (
                <p className="text-xs text-[var(--muted)] mt-1">
                  Prêt pour le Tuteur IA et la génération d’exercices.
                </p>
              )}
              {d.status === "failed" && (
                <p className="text-xs text-[var(--danger)] mt-1">
                  Vérifiez qu’Ollama tourne (`llama3.2` + `nomic-embed-text`), puis réimportez.
                </p>
              )}
            </div>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={async () => {
                const ok = await confirm({
                  title: "Supprimer le support ?",
                  description: `Les exercices liés seront conservés sans ce document.\n\nSupport : ${d.title}`,
                  danger: true,
                  confirmText: "Supprimer",
                  cancelText: "Annuler",
                });
                if (!ok) return;
                setBusy(true);
                setError("");
                try {
                  await api.deleteDocument(d.id);
                  await load();
                  addToast({
                    type: "success",
                    title: "Support supprimé",
                    message: "Le support a été supprimé de l’organisation.",
                    ttlMs: 4200,
                  });
                } catch (err) {
                  const msg = err instanceof Error ? err.message : "Suppression impossible";
                  setError(msg);
                  addToast({ type: "error", title: "Suppression échouée", message: msg, ttlMs: 5500 });
                } finally {
                  setBusy(false);
                }
              }}
            >
              Supprimer
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
