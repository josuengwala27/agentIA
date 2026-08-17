"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminUser, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";

const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  trainer: "Formateur",
  learner: "Apprenant",
};

export default function UsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("learner");
  const [password, setPassword] = useState("");
  const [secret, setSecret] = useState<{ email: string; password: string; action: string } | null>(null);

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.replace("/dashboard");
    }
  }, [user, router]);

  async function load() {
    setUsers(await api.users());
  }

  useEffect(() => {
    if (user?.role !== "admin") return;
    load().catch((e) => setError(e.message));
  }, [user]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api.createUser({
        email,
        full_name: fullName,
        role,
        password: password.trim() || undefined,
      });
      setEmail("");
      setFullName("");
      setPassword("");
      setRole("learner");
      if (created.temporary_password) {
        setSecret({
          email: created.email,
          password: created.temporary_password,
          action: "Compte créé — mot de passe temporaire",
        });
      }
      addToast({
        type: "success",
        title: "Compte créé",
        message: `${created.full_name} (${ROLE_LABEL[created.role] || created.role})`,
        ttlMs: 4500,
      });
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Création impossible";
      setError(msg);
      addToast({ type: "error", title: "Erreur", message: msg, ttlMs: 5500 });
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(target: AdminUser) {
    const next = !target.is_active;
    const ok = await confirm({
      title: next ? "Réactiver ce compte ?" : "Désactiver ce compte ?",
      description: next
        ? `${target.full_name} pourra à nouveau se connecter.`
        : `${target.full_name} ne pourra plus se connecter.`,
      danger: !next,
      confirmText: next ? "Réactiver" : "Désactiver",
      cancelText: "Annuler",
    });
    if (!ok) return;
    try {
      await api.setUserActive(target.id, next);
      addToast({
        type: "success",
        title: next ? "Compte réactivé" : "Compte désactivé",
        message: target.email,
        ttlMs: 4000,
      });
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Action impossible";
      addToast({ type: "error", title: "Erreur", message: msg, ttlMs: 5500 });
    }
  }

  async function resetPassword(target: AdminUser) {
    const ok = await confirm({
      title: "Réinitialiser le mot de passe ?",
      description: `Un mot de passe temporaire sera généré pour ${target.email}.`,
      danger: true,
      confirmText: "Réinitialiser",
      cancelText: "Annuler",
    });
    if (!ok) return;
    try {
      const result = await api.resetUserPassword(target.id);
      setSecret({
        email: target.email,
        password: result.temporary_password,
        action: "Mot de passe réinitialisé",
      });
      addToast({
        type: "success",
        title: "Mot de passe réinitialisé",
        message: "Copie le mot de passe temporaire affiché ci-dessous.",
        ttlMs: 5000,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Réinitialisation impossible";
      addToast({ type: "error", title: "Erreur", message: msg, ttlMs: 5500 });
    }
  }

  async function copySecret() {
    if (!secret) return;
    await navigator.clipboard.writeText(secret.password);
    addToast({ type: "success", title: "Copié", message: "Mot de passe copié dans le presse-papiers.", ttlMs: 3000 });
  }

  if (user && user.role !== "admin") {
    return <p className="text-[var(--muted)]">Redirection…</p>;
  }

  return (
    <div className="space-y-8 rise max-w-5xl">
      <header>
        <h1 className="font-display text-4xl">Comptes</h1>
        <p className="text-[var(--muted)] mt-2">
          Créer un apprenant ou un formateur, désactiver un accès, réinitialiser un mot de passe.
        </p>
      </header>
      {error && <p className="text-[var(--danger)]">{error}</p>}

      {secret && (
        <div className="rounded-xl border border-[var(--accent)] bg-[var(--accent-soft)] px-4 py-4 space-y-2">
          <p className="font-medium">{secret.action}</p>
          <p className="text-sm">
            {secret.email} — mot de passe : <code className="font-mono">{secret.password}</code>
          </p>
          <p className="text-xs text-[var(--muted)]">Note-le maintenant : il ne sera plus réaffiché.</p>
          <button type="button" className="btn btn-ghost" onClick={copySecret}>
            Copier
          </button>
        </div>
      )}

      <form onSubmit={onCreate} className="surface p-6 grid md:grid-cols-2 gap-4">
        <h2 className="font-display text-2xl md:col-span-2">Nouveau compte</h2>
        <label className="text-sm">
          Nom complet
          <input className="input mt-1" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </label>
        <label className="text-sm">
          Email
          <input
            className="input mt-1"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          Rôle
          <select className="input mt-1" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="learner">Apprenant</option>
            <option value="trainer">Formateur</option>
            <option value="admin">Administrateur</option>
          </select>
        </label>
        <label className="text-sm">
          Mot de passe (optionnel)
          <input
            className="input mt-1"
            type="text"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Laissé vide = mot de passe temporaire"
          />
        </label>
        <div className="md:col-span-2">
          <button className="btn" disabled={busy} type="submit">
            {busy ? "Création…" : "Créer le compte"}
          </button>
        </div>
      </form>

      <section className="surface p-6 overflow-x-auto">
        <h2 className="font-display text-2xl mb-4">Utilisateurs de l’organisation</h2>
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="text-[var(--muted)] border-b border-[var(--line)]">
              <th className="py-2 pr-3 font-medium">Personne</th>
              <th className="py-2 pr-3 font-medium">Rôle</th>
              <th className="py-2 pr-3 font-medium">Statut</th>
              <th className="py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((row) => (
              <tr key={row.id} className="border-b border-[var(--line)]/70">
                <td className="py-3 pr-3">
                  <div className="font-medium">{row.full_name}</div>
                  <div className="text-xs text-[var(--muted)]">{row.email}</div>
                </td>
                <td className="py-3 pr-3">{ROLE_LABEL[row.role] || row.role}</td>
                <td className="py-3 pr-3">{row.is_active ? "Actif" : "Désactivé"}</td>
                <td className="py-3">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn btn-ghost text-xs"
                      disabled={row.id === user?.id && row.is_active}
                      onClick={() => toggleActive(row)}
                    >
                      {row.is_active ? "Désactiver" : "Réactiver"}
                    </button>
                    <button type="button" className="btn btn-ghost text-xs" onClick={() => resetPassword(row)}>
                      Réinit. MDP
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
