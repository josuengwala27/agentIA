"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("apprenant@demo.local");
  const [password, setPassword] = useState("learner123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de connexion");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <section className="relative overflow-hidden px-8 py-16 md:px-14 flex flex-col justify-end min-h-[42vh] lg:min-h-screen">
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(145deg, #0f6b5c 0%, #1a4d42 42%, #243b2f 100%), radial-gradient(circle at 20% 20%, rgba(255,255,255,.18), transparent 40%)",
          }}
        />
        <div className="relative rise text-white max-w-xl">
          <p className="font-display text-5xl md:text-6xl leading-none mb-4">Formia</p>
          <p className="text-lg text-white/85">
            L’agent pédagogique qui entraîne et évalue à partir de vos supports — sans inventer le
            cours.
          </p>
        </div>
      </section>
      <section className="flex items-center justify-center px-6 py-12">
        <form onSubmit={onSubmit} className="surface w-full max-w-md p-8 rise space-y-4">
          <h1 className="font-display text-3xl">Connexion</h1>
          <p className="text-sm text-[var(--muted)]">
            Comptes démo : apprenant@demo.local / learner123
          </p>
          <label className="block text-sm">
            Email
            <input className="input mt-1" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block text-sm">
            Mot de passe
            <input
              type="password"
              className="input mt-1"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <button className="btn w-full" disabled={busy} type="submit">
            {busy ? "Connexion…" : "Entrer"}
          </button>
        </form>
      </section>
    </div>
  );
}
