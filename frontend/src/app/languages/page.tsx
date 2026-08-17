"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  api,
  ComprehensionExercise,
  DocumentItem,
  PronunciationResult,
} from "@/lib/api";
import { useToast } from "@/components/ToastProvider";

const SPEECH_LANG: Record<string, string> = {
  fr: "fr-FR",
  en: "en-US",
  es: "es-ES",
  de: "de-DE",
  it: "it-IT",
  pt: "pt-PT",
  ar: "ar-SA",
  zh: "zh-CN",
  ru: "ru-RU",
};

function speak(text: string, language = "fr") {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = SPEECH_LANG[language] || "fr-FR";
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

export default function LanguagesPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const { addToast } = useToast();
  const [text, setText] = useState("Je suis aller au centre de formation hier.");
  const [grammar, setGrammar] = useState<{ corrected_text: string; explanations: string[] } | null>(
    null
  );
  const [docId, setDocId] = useState("");
  const [comprehension, setComprehension] = useState<ComprehensionExercise | null>(null);
  const [compAnswers, setCompAnswers] = useState<Record<string, number>>({});
  const [compChecked, setCompChecked] = useState(false);
  const [reference, setReference] = useState("A phrasal verb is a verb plus a particle.");
  const [spoken, setSpoken] = useState("");
  const [audio, setAudio] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const [whisper, setWhisper] = useState<boolean | null>(null);
  const [pronunciation, setPronunciation] = useState<PronunciationResult | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    Promise.all([api.documents(), api.languagesStatus().catch(() => ({ whisper: false }))])
      .then(([docs, status]) => {
        const indexed = docs.filter((x) => x.status === "indexed");
        setDocuments(indexed);
        if (indexed[0]) setDocId(indexed[0].id);
        setWhisper(status.whisper);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function onGrammar(e: FormEvent) {
    e.preventDefault();
    setBusy("grammar");
    setError("");
    try {
      setGrammar(await api.grammar(text));
      addToast({
        type: "success",
        title: "Correction terminée",
        message: "Ta phrase a été corrigée.",
        ttlMs: 4200,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setError(msg);
      addToast({ type: "error", title: "Erreur correction", message: msg, ttlMs: 5500 });
    } finally {
      setBusy("");
    }
  }

  async function onComprehension(e: FormEvent) {
    e.preventDefault();
    setBusy("comp");
    setError("");
    try {
      if (!docId) {
        const msg = "Choisis un document indexé.";
        setError(msg);
        addToast({ type: "warning", title: "Document requis", message: msg, ttlMs: 4500 });
        setBusy("");
        return;
      }
      const exercise = await api.comprehension(docId, 3);
      setComprehension(exercise);
      setCompAnswers({});
      setCompChecked(false);
      addToast({
        type: "success",
        title: "Exercice généré",
        message: "Compréhension écrite générée à partir du document.",
        ttlMs: 4500,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setError(msg);
      addToast({ type: "error", title: "Erreur compréhension", message: msg, ttlMs: 5500 });
    } finally {
      setBusy("");
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const file = new File([blob], "shadowing.webm", { type: blob.type });
        setAudio(file);
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      addToast({
        type: "error",
        title: "Micro inaccessible",
        message: "Autorise le micro ou importe un fichier audio.",
        ttlMs: 5000,
      });
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }

  async function onPronunciation(e: FormEvent) {
    e.preventDefault();
    setBusy("pron");
    setError("");
    try {
      const result = await api.pronunciation(reference, audio || undefined, spoken.trim() || undefined);
      setPronunciation(result);
      addToast({
        type: "success",
        title: "Analyse terminée",
        message: `Précision ${(result.accuracy * 100).toFixed(0)} % — ${result.engine === "manual" ? "transcription saisie" : result.engine}.`,
        ttlMs: 4200,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setError(msg);
      addToast({ type: "error", title: "Erreur analyse", message: msg, ttlMs: 5500 });
    } finally {
      setBusy("");
    }
  }

  const wordClass: Record<string, string> = {
    match: "bg-emerald-100 text-emerald-900",
    missed: "bg-red-100 text-red-800 line-through",
    replaced: "bg-amber-100 text-amber-900",
    extra: "bg-slate-200 text-slate-700 italic",
  };

  return (
    <div className="space-y-8 rise max-w-4xl">
      <header>
        <h1 className="font-display text-4xl">Module langues</h1>
        <p className="text-[var(--muted)] mt-2">
          Correction écrite, compréhension, shadowing et analyse de prononciation.
        </p>
      </header>
      {error && <p className="text-[var(--danger)]">{error}</p>}

      {documents.length === 0 && (
        <div className="rounded-xl border border-[var(--warn)] bg-[#fff7ed] px-4 py-3 text-sm">
          La compréhension écrite nécessite un support <strong>indexed</strong>. La grammaire et le
          shadowing peuvent être testés sans document.
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
          <div className="space-y-4">
            <p className="bg-white/70 rounded-xl p-4 text-sm whitespace-pre-wrap">{comprehension.passage}</p>
            {(comprehension.questions || []).map((q) => (
              <div key={q.id} className="space-y-2 border-t border-[var(--line)] pt-3">
                <p className="font-medium">{q.stem}</p>
                {(q.choices || []).map((choice, idx) => {
                  const selected = compAnswers[q.id] === idx;
                  const correct = compChecked && idx === q.correct_index;
                  const wrong = compChecked && selected && idx !== q.correct_index;
                  return (
                    <label
                      key={idx}
                      className={`flex gap-2 items-center text-sm px-2 py-1 rounded-lg ${
                        correct ? "bg-emerald-100" : wrong ? "bg-red-100" : ""
                      }`}
                    >
                      <input
                        type="radio"
                        name={q.id}
                        checked={selected}
                        onChange={() => setCompAnswers((a) => ({ ...a, [q.id]: idx }))}
                        disabled={compChecked}
                      />
                      {choice}
                    </label>
                  );
                })}
                {compChecked && q.explanation && (
                  <p className="text-xs text-[var(--muted)]">{q.explanation}</p>
                )}
              </div>
            ))}
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setCompChecked(true)}
              disabled={compChecked}
            >
              Vérifier
            </button>
          </div>
        )}
      </form>

      <form onSubmit={onPronunciation} className="surface p-6 space-y-3">
        <h2 className="font-display text-2xl">Prononciation / shadowing</h2>
        <p className="text-sm text-[var(--muted)]">
          Écoute le modèle, répète, puis analyse. Whisper local :{" "}
          {whisper ? "disponible" : "non installé — utilise la transcription saisie"}.
        </p>
        <label className="block text-sm">
          Texte de référence
          <textarea
            className="input mt-1 min-h-20"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => speak(reference, pronunciation?.language || "en")}
          >
            Écouter le modèle
          </button>
          {!recording ? (
            <button type="button" className="btn btn-ghost" onClick={startRecording}>
              Enregistrer
            </button>
          ) : (
            <button type="button" className="btn" onClick={stopRecording}>
              Stop
            </button>
          )}
        </div>
        <label className="block text-sm">
          Audio (fichier ou enregistrement)
          <input
            type="file"
            accept="audio/*"
            className="mt-1 block"
            onChange={(e) => setAudio(e.target.files?.[0] || null)}
          />
          {audio && <span className="text-xs text-[var(--muted)]">{audio.name}</span>}
        </label>
        <label className="block text-sm">
          Transcription de ce que tu as lu (si pas de Whisper)
          <textarea
            className="input mt-1 min-h-16"
            value={spoken}
            onChange={(e) => setSpoken(e.target.value)}
            placeholder="Ex. A phrasal verb is a verb plus a particule."
          />
        </label>
        <button className="btn" disabled={busy === "pron"} type="submit">
          {busy === "pron" ? "Analyse…" : "Analyser"}
        </button>
        {pronunciation && (
          <div className="space-y-3 bg-white/70 rounded-xl p-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <p>
                Précision : <strong>{Math.round(pronunciation.accuracy * 100)}%</strong>
              </p>
              <p>
                Fluidité : <strong>{Math.round(pronunciation.fluency * 100)}%</strong>
              </p>
            </div>
            <p className="text-sm">{pronunciation.feedback}</p>
            <div className="flex flex-wrap gap-1">
              {pronunciation.words.map((item, idx) => (
                <span key={`${item.word}-${idx}`} className={`px-2 py-0.5 rounded-md text-sm ${wordClass[item.status] || ""}`}>
                  {item.word}
                </span>
              ))}
            </div>
            <p className="text-sm">{pronunciation.shadowing_tip}</p>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => speak(pronunciation.shadowing_text, pronunciation.language)}
            >
              Écouter les mots à retravailler
            </button>
            <p className="text-xs text-[var(--muted)]">
              Moteur : {pronunciation.engine} — transcrit : {pronunciation.transcript}
            </p>
          </div>
        )}
      </form>
    </div>
  );
}
