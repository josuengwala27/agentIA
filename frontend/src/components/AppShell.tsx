"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/documents", label: "Supports", roles: ["admin", "trainer"] },
  { href: "/chat", label: "Tuteur IA" },
  { href: "/exercises", label: "Exercices" },
  { href: "/languages", label: "Langues" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [loading, user, pathname, router]);

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-[var(--muted)]">
        Chargement…
      </div>
    );
  }

  if (!user && pathname !== "/login") {
    return (
      <div className="min-h-screen grid place-items-center text-[var(--muted)]">
        Redirection…
      </div>
    );
  }

  if (pathname === "/login") return <>{children}</>;

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-64 shrink-0 border-r border-[var(--line)] bg-[var(--panel)]/80 backdrop-blur-md px-5 py-6">
        <div className="mb-8">
          <p className="font-display text-2xl tracking-tight text-[var(--ink)]">Formia</p>
          <p className="text-sm text-[var(--muted)] mt-1">Agent pédagogique</p>
        </div>
        <nav className="flex md:flex-col gap-2 overflow-x-auto pb-2">
          {links
            .filter((l) => !l.roles || (user && l.roles.includes(user.role)))
            .map((l) => {
              const active = pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`px-3 py-2 rounded-lg text-sm whitespace-nowrap transition ${
                    active
                      ? "bg-[var(--accent)] text-white"
                      : "text-[var(--ink)] hover:bg-[var(--accent-soft)]"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
        </nav>
        {user && (
          <div className="mt-8 pt-6 border-t border-[var(--line)] text-sm">
            <p className="font-medium text-[var(--ink)]">{user.full_name}</p>
            <p className="text-[var(--muted)] capitalize">{user.role}</p>
            <button
              type="button"
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="mt-3 text-[var(--accent)] underline-offset-2 hover:underline"
            >
              Déconnexion
            </button>
          </div>
        )}
      </aside>
      <main className="flex-1 px-5 py-8 md:px-10 md:py-10">{children}</main>
    </div>
  );
}
