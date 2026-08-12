"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, Citation, ConversationItem, DocumentItem, MessageItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";

export default function ChatPage() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeId, setActiveId] = useState<string | undefined>();
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("");
  const activeIdRef = useRef<string | undefined>(undefined);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const confirm = useConfirm();
  const { addToast } = useToast();

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  const refreshConversations = useCallback(async () => {
    const list = await api.conversations();
    setConversations(list);
    return list;
  }, []);

  const loadMessages = useCallback(async (id: string) => {
    const msgs = await api.messages(id);
    setMessages(msgs);
    return msgs;
  }, []);

  useEffect(() => {
    Promise.all([api.conversations(), api.documents()])
      .then(([c, d]) => {
        setConversations(c);
        const indexed = d.filter((x) => x.status === "indexed");
        setDocuments(indexed);
        if (indexed[0]) setDocumentId(indexed[0].id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setReady(true));
  }, []);

  // While waiting for Ollama, poll the server so a page remount / slow UI still shows the answer.
  useEffect(() => {
    if (!busy) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      const id = activeIdRef.current;
      if (!id) return;
      try {
        const msgs = await api.messages(id);
        setMessages(msgs);
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          setBusy(false);
          setStatus("");
          await refreshConversations();
        }
      } catch {
        /* ignore transient poll errors */
      }
    }, 2500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [busy, refreshConversations]);

  const hasIndexed = documents.length > 0;
  const canChat = hasIndexed && !busy;

  async function openConversation(id: string) {
    setActiveId(id);
    setError("");
    setStatus("");
    await loadMessages(id);
  }

  async function clearHistory() {
    const ok = await confirm({
      title: "Effacer l’historique ?",
      description: "Toutes tes conversations et messages seront supprimés.",
      danger: true,
      confirmText: "Effacer",
      cancelText: "Annuler",
    });
    if (!ok) return;
    setError("");
    try {
      await api.deleteAllConversations();
      setConversations([]);
      setActiveId(undefined);
      setMessages([]);
      setStatus("Historique effacé.");
      addToast({ type: "success", title: "OK", message: "Historique supprimé.", ttlMs: 3500 });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Suppression impossible";
      setError(msg);
      addToast({ type: "error", title: "Erreur", message: msg, ttlMs: 5500 });
    }
  }

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || !canChat) return;
    const userMsg = input.trim();
    setInput("");
    setBusy(true);
    setError("");
    setStatus("Génération en cours (Ollama local : 20 à 90 s). Ne rechargez pas la page…");

    // Optimistic user bubble
    setMessages((m) => [
      ...m,
      {
        id: `local-${Date.now()}`,
        role: "user",
        content: userMsg,
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      const res = await api.chat(userMsg, activeId, documentId || undefined);
      setActiveId(res.conversation_id);
      activeIdRef.current = res.conversation_id;
      // Source of truth = server (fixes “answer only after refresh”)
      const msgs = await loadMessages(res.conversation_id);
      if (!msgs.some((m) => m.role === "assistant" && m.content === res.answer)) {
        setMessages((m) => [
          ...m,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: res.answer,
            citations: res.citations,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      await refreshConversations();
      setStatus("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur chat";
      setError(msg);
      addToast({ type: "error", title: "Chat impossible", message: msg, ttlMs: 6000 });
      setStatus("");
      const id = activeIdRef.current;
      if (id) {
        try {
          await loadMessages(id);
        } catch {
          /* ignore */
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid lg:grid-cols-[240px_1fr] gap-6 rise min-h-[70vh]">
      <aside className="surface p-4 space-y-2">
        <button
          type="button"
          className="btn btn-ghost w-full"
          disabled={busy}
          onClick={() => {
            setActiveId(undefined);
            setMessages([]);
            setError("");
            setStatus("");
          }}
        >
          Nouvelle conversation
        </button>
        <button type="button" className="btn btn-ghost w-full text-[var(--danger)]" disabled={busy} onClick={clearHistory}>
          Effacer l’historique
        </button>
        {conversations.map((c) => (
          <div key={c.id} className="flex gap-1 items-stretch">
            <button
              type="button"
              onClick={() => openConversation(c.id)}
              className={`flex-1 text-left text-sm px-3 py-2 rounded-lg ${
                activeId === c.id ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--accent-soft)]/50"
              }`}
            >
              {c.title}
            </button>
            <button
              type="button"
              title="Supprimer"
              className="px-2 text-xs text-[var(--danger)]"
              disabled={busy}
              onClick={async () => {
                await api.deleteConversation(c.id);
                if (activeId === c.id) {
                  setActiveId(undefined);
                  setMessages([]);
                }
                await refreshConversations();
              }}
            >
              ×
            </button>
          </div>
        ))}
      </aside>

      <section className="surface p-5 flex flex-col min-h-[60vh]">
        <header className="mb-4">
          <h1 className="font-display text-3xl">Tuteur IA</h1>
          <p className="text-sm text-[var(--muted)]">Réponses ancrées dans vos documents, avec citations.</p>

          {ready && !hasIndexed && (
            <div className="mt-3 rounded-xl border border-[var(--warn)] bg-[#fff7ed] px-4 py-3 text-sm">
              <p className="font-medium text-[var(--warn)]">Aucun support indexé</p>
              <p className="text-[var(--muted)] mt-1">
                {user && ["admin", "trainer"].includes(user.role) ? (
                  <>
                    Allez dans <Link className="underline text-[var(--accent)]" href="/documents">Supports</Link> avant de chatter.
                  </>
                ) : (
                  <>Demandez à un formateur d’importer un support.</>
                )}
              </p>
            </div>
          )}

          {hasIndexed && (
            <p className="mt-2 text-xs text-[var(--accent)]">
              {documents.length} support(s) prêt(s). La génération locale peut prendre jusqu’à 1–2 minutes.
            </p>
          )}

          <select
            className="input mt-3 max-w-md"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            disabled={!hasIndexed || busy}
          >
            <option value="">Tous les documents de l’organisation</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto mb-4">
          {messages.length === 0 && (
            <div className="surface p-6 text-sm text-[var(--muted)]">
              <div className="font-medium text-[var(--ink)]">Commence par une question</div>
              <div className="mt-2">
                Pose une question sur le support <strong>{documents[0]?.title || "indexé"}</strong> afin que le tuteur puisse répondre avec des citations.
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`max-w-3xl ${m.role === "user" ? "ml-auto text-right" : ""}`}>
              <div
                className={`inline-block text-left px-4 py-3 rounded-2xl ${
                  m.role === "user" ? "bg-[var(--accent)] text-white" : "bg-[var(--accent-soft)]"
                }`}
              >
                <p className="whitespace-pre-wrap">{m.content}</p>
              </div>
              {m.citations && m.citations.length > 0 && <Citations citations={m.citations} />}
            </div>
          ))}
          {busy && (
            <div className="text-sm text-[var(--muted)] animate-pulse">
              L’IA rédige la réponse… {status}
            </div>
          )}
        </div>

        {status && !busy && <p className="text-sm text-[var(--accent)] mb-2">{status}</p>}
        {error && <p className="text-sm text-[var(--danger)] mb-2">{error}</p>}
        <form onSubmit={onSend} className="flex gap-2">
          <input
            className="input"
            placeholder={hasIndexed ? "Posez votre question…" : "Importez d’abord un support indexé…"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!canChat}
          />
          <button className="btn min-w-28" disabled={!canChat || !input.trim()} type="submit">
            {busy ? "Attente…" : "Envoyer"}
          </button>
        </form>
      </section>
    </div>
  );
}

function Citations({ citations }: { citations: Citation[] }) {
  return (
    <div className="mt-2 text-left text-xs text-[var(--muted)] space-y-1">
      {citations.map((c, i) => (
        <p key={`${c.document_id}-${c.chunk_index}-${i}`}>
          [{i + 1}] {c.document_title} — {c.excerpt}
        </p>
      ))}
    </div>
  );
}
