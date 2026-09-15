"use client";

import { useState } from "react";
import { ArrowRight, Info, Sparkles, XCircle } from "lucide-react";
import Link from "next/link";

import { api, ApiError } from "@/lib/api";

interface AiAnalyzeResponse {
  question: string;
  intent: string;
  time_period: string;
  filters: Record<string, unknown>;
  metrics_used: string[];
  evidence: Record<string, unknown>[];
  limitations: string;
  answer: string;
  deep_link: string | null;
  llm_used: boolean;
}

const SUGGESTED_QUESTIONS = [
  "Why did PSR drop yesterday?",
  "Which bank contributed most to failures?",
  "What was the biggest failure fingerprint?",
  "What is the estimated value at risk?",
  "Did the intervention improve PSR?",
];

export default function AiAnalystPage() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<AiAnalyzeResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await api.post<AiAnalyzeResponse>("/api/ai/analyze", { question: q });
      setHistory((prev) => [resp, ...prev]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to get an answer.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-[800px] mx-auto">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="w-4 h-4 text-ai" />
        <h1 className="text-xl font-semibold text-text-primary">AI Analyst</h1>
      </div>
      <p className="text-sm text-text-secondary mb-6">Ask about your payment data in natural language.</p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="flex gap-2 mb-4"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your payment data..."
          className="input flex-1"
        />
        <button type="submit" disabled={loading || !question.trim()} className="btn-primary">
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {history.length === 0 && (
        <>
          <div className="text-xs text-text-tertiary mb-2">Suggested questions</div>
          <div className="space-y-2 mb-6">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => ask(q)}
                className="card w-full text-left px-3.5 py-2.5 text-sm text-text-secondary hover:border-accent/50 hover:text-text-primary transition-colors"
              >
                {q} <ArrowRight className="w-3 h-3 inline ml-1" />
              </button>
            ))}
          </div>
        </>
      )}

      <div className="space-y-4">
        {history.map((entry, i) => (
          <div key={i} className="card p-5 border-ai/30 bg-ai-bg/30">
            <div className="text-xs text-text-tertiary mb-2">{entry.question}</div>
            <p className="text-sm text-text-primary leading-relaxed mb-3">{entry.answer}</p>
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-tertiary pt-3 border-t border-border">
              <span className="badge bg-bg-surface-raised border border-border">{entry.time_period}</span>
              {entry.metrics_used.map((m) => (
                <span key={m} className="badge bg-bg-surface-raised border border-border numeric">
                  {m}
                </span>
              ))}
              {!entry.llm_used && (
                <span
                  className="badge bg-warning/15 text-warning"
                  title="No LLM API key configured; showing a template-based, data-grounded summary"
                >
                  template summary
                </span>
              )}
            </div>
            <div className="flex items-start gap-2 mt-3 text-xs text-text-tertiary">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              {entry.limitations}
            </div>
            {entry.deep_link && (
              <Link href={entry.deep_link} className="inline-flex items-center gap-1 mt-3 text-xs text-accent hover:underline">
                View analysis <ArrowRight className="w-3 h-3" />
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
