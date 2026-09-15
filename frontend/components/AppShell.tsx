"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Stethoscope,
  AlertTriangle,
  Wrench,
  FlaskConical,
  Sparkles,
  Settings,
  LogOut,
  Circle,
} from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { DataFreshness } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/failures", label: "Failure Explorer", icon: Search },
  { href: "/rca", label: "RCA", icon: Stethoscope },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/interventions", label: "Interventions", icon: Wrench },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/ai-analyst", label: "AI Analyst", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [freshness, setFreshness] = useState<DataFreshness | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    api
      .get<DataFreshness>("/api/data-freshness")
      .then(setFreshness)
      .catch(() => setFreshness(null));
  }, [user]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-text-secondary text-sm">
        Loading...
      </div>
    );
  }

  if (!user) return null;

  const freshnessLabel = freshness?.last_run
    ? `Data fresh as of ${new Date(freshness.last_run.completed_at).toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })}`
    : "No successful pipeline run yet";

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 shrink-0 border-r border-border bg-bg-surface flex flex-col">
        <div className="h-14 flex items-center px-4 border-b border-border font-semibold text-text-primary">
          <span className="w-2 h-2 rounded-full bg-accent mr-2" />
          UPI-FIP
        </div>
        <nav className="flex-1 py-3 px-2 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-control text-sm transition-colors ${
                  active
                    ? "bg-accent-bg text-accent font-medium"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover"
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-2 px-1 mb-1">
            <Circle className="w-2 h-2 fill-success text-success" />
            <span className="text-xs text-text-tertiary truncate">{freshnessLabel}</span>
          </div>
          <div className="flex items-center justify-between px-1 pt-2">
            <div className="min-w-0">
              <div className="text-xs font-medium text-text-primary truncate">{user.display_name}</div>
              <div className="text-[11px] text-text-tertiary capitalize">{user.role}</div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="p-1.5 rounded-control text-text-tertiary hover:text-text-primary hover:bg-bg-surface-hover"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-14 shrink-0 border-b border-border flex items-center justify-between px-6 bg-bg">
          <div className="flex items-center gap-3">
            <span className="badge bg-bg-surface-raised text-text-secondary border border-border">
              local / synthetic data
            </span>
          </div>
          <div className="text-xs text-text-tertiary numeric">{freshnessLabel}</div>
        </header>
        <main className="flex-1 min-w-0 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
