"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ShieldCheck } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

const DEMO_ACCOUNTS = [
  { email: "admin@upi-fip.dev", role: "Admin" },
  { email: "pm@upi-fip.dev", role: "Product Manager" },
  { email: "ops@upi-fip.dev", role: "Payment Ops" },
  { email: "engineer@upi-fip.dev", role: "Engineer" },
  { email: "support@upi-fip.dev", role: "Support" },
  { email: "viewer@upi-fip.dev", role: "Viewer" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("pm@upi-fip.dev");
  const [password, setPassword] = useState("Demo123!");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-5">
      <div className="hidden lg:flex lg:col-span-3 flex-col justify-between p-12 bg-bg-surface border-r border-border">
        <div className="flex items-center gap-2 text-text-primary font-semibold">
          <div className="w-7 h-7 rounded-control bg-accent/20 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-accent" />
          </div>
          UPI-FIP
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-semibold text-text-primary leading-tight">
            Detect. Diagnose. Intervene. Measure.
          </h1>
          <p className="mt-4 text-text-secondary leading-relaxed">
            Payment Failure Intelligence Platform — an internal console for finding where UPI
            payments are failing, why, and what to do about it.
          </p>
          <div className="mt-8 rounded-card border border-warning/30 bg-warning-bg px-4 py-3 text-sm text-warning">
            Synthetic/portfolio data only. This platform does not process real payments.
          </div>
        </div>
        <p className="text-xs text-text-tertiary">
          Built against a synthetic dataset with a deliberately injected failure pattern for demonstration.
        </p>
      </div>

      <div className="lg:col-span-2 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-semibold text-text-primary mb-1">Sign in</h2>
          <p className="text-sm text-text-secondary mb-6">Use a demo account below or your own.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1.5" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input w-full"
                autoComplete="email"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1.5" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input w-full"
                autoComplete="current-password"
              />
            </div>

            {error && (
              <p className="text-sm text-critical" role="alert">
                {error}
              </p>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "Signing in..." : "Sign in"}
              {!submitting && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-border">
            <p className="text-xs text-text-tertiary mb-3">
              Demo accounts (password: <span className="numeric">Demo123!</span>)
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map((acct) => (
                <button
                  key={acct.email}
                  type="button"
                  onClick={() => {
                    setEmail(acct.email);
                    setPassword("Demo123!");
                  }}
                  className="text-left px-2.5 py-2 rounded-control border border-border hover:border-accent/50 hover:bg-bg-surface-hover transition-colors"
                >
                  <div className="text-xs font-medium text-text-primary">{acct.role}</div>
                  <div className="text-[11px] text-text-tertiary numeric">{acct.email}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
