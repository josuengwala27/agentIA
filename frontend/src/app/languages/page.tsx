"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, DocumentItem } from "@/lib/api";

export default function LanguagesPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [text, setText] = useState("Je suis aller au centre de formation hier.");
  const [grammar, setGrammar] = useState<{ corrected_text: string; explanations: string[] } | null>(
    null
  );
  const [docId, setDocId] = useState("");
  const [comprehension, setComprehension] = useState<Record<string, unknown> | null>(null);
  const [reference, setReference] = useState("Bonjour, je m'appelle Marie et j'apprends le français.");
  const [audio, setAudio] = useState<File | null>(null);
  const [pronunciation, setPronunciation] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .documents()
      .then((d) => {
        const indexed = d.filter((x) => x.status === "indexed");
        setDocuments(indexed);
        if (indexed[0]) setDocId(indexed[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function onGrammar(e: FormEvent) {
    e.preventDefault();
    setBusy("grammar");
    setError("");
    try {
      setGrammar(await api.grammar(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy("");
    }
  }

  async function onComprehension(e: FormEvent) {
    e.preventDefault();
    setBusy("comp");
    setError("");
    try {
      setComprehension(await api.comprehension(docId, 3));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy("");
    }
  }

  async function onPronunciation(e: FormEvent) {
    e.preventDefault();
    setBusy("pron");
    setError("");
    try {
      setPronunciation(await api.pronunciation(reference, audio || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-8 rise max-w-4xl">
      <header>
        <h1 className="font-display text-4xl">Module langues</h1>
        <p className="text-[var(--muted)] mt-2">
          Correction écrite, compréhension, et analyse de prononciation (Whisper local optionnel).
        </p>
      </header>
      {error && <p className="text-[var(--danger)]">{error}</p>}

      {documents.length === 0 && (
        <div className="rounded-xl border border-[var(--warn)] bg-[#fff7ed] px-4 py-3 text-sm">
          La compréhension écrite nécessite un support <strong>indexed</strong>. La grammaire et la
          prononciation (texte) peuvent être testées sans document.
        </div>
      )}

      <form onSubmit={onGrammar} className="surface p-6 space-y-3">
        <h2 className="font-display text-2xl">Orthographe & grammaire</h2>
        <textarea className="input min-h-28" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn" disabled={busy === "grammar"} type="submit">
          {busy === "grammar" ? "Correction…" : "Corriger"}
        </button>
        {grammar && (
          <div className="bg-[var(--accent-soft)] rounded-xl p-4 space-y-2">
            <p className="font-medium">{grammar.corrected_text}</p>
            <ul className="text-sm list-disc pl-5">
              {grammar.explanations.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        )}
      </form>

      <form onSubmit={onComprehension} className="surface p-6 space-y-3">
        <h2 className="font-display text-2xl">Compréhension écrite</h2>
        <select className="input" value={docId} onChange={(e) => setDocId(e.target.value)} required>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <button className="btn" disabled={busy === "comp" || !docId} type="submit">
          {busy === "comp" ? "Génération…" : "Générer un exercice"}
        </button>
        {comprehension && (
          <pre className="text-xs whitespace-pre-wrap bg-white/70 p-4 rounded-xl overflow-auto">
            {JSON.stringify(comprehension, null, 2)}
          </pre>
        )}
      </form>

      <form onSubmit={onPronunciation} className="surface p-6 space-y-3">
        <h2 className="font-display text-2xl">Prononciation / fluidité</h2>
        <label className="block text-sm">
          Texte de référence
          <textarea
            className="input mt-1 min-h-20"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Audio (optionnel, nécessite faster-whisper)
          <input
            type="file"
            accept="audio/*"
            className="mt-1 block"
            onChange={(e) => setAudio(e.target.files?.[0] || null)}
          />
        </label>
        <button className="btn" disabled={busy === "pron"} type="submit">
          {busy === "pron" ? "Analyse…" : "Analyser"}
        </button>
        {pronunciation && (
          <pre className="text-xs whitespace-pre-wrap bg-white/70 p-4 rounded-xl overflow-auto">
            {JSON.stringify(pronunciation, null, 2)}
          </pre>
        )}
      </form>
    </div>
  );
}
