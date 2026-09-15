import type { LucideIcon } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string;
  change?: string | null;
  changeDirection?: "up" | "down" | "neutral";
  changeIsGood?: boolean;
  icon?: LucideIcon;
  tone?: "default" | "critical" | "warning" | "success";
}

const TONE_BORDER: Record<string, string> = {
  default: "border-border",
  critical: "border-critical/40",
  warning: "border-warning/40",
  success: "border-success/40",
};

export default function KpiCard({
  label,
  value,
  change,
  changeDirection = "neutral",
  changeIsGood = true,
  icon: Icon,
  tone = "default",
}: KpiCardProps) {
  const changeColor =
    changeDirection === "neutral" ? "text-text-tertiary" : changeIsGood ? "text-success" : "text-critical";

  const arrow = changeDirection === "up" ? "↑" : changeDirection === "down" ? "↓" : "";

  return (
    <div className={`card px-4 py-3.5 ${TONE_BORDER[tone]}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-secondary">{label}</span>
        {Icon && <Icon className="w-3.5 h-3.5 text-text-tertiary" />}
      </div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-text-primary numeric">{value}</span>
        {change && (
          <span className={`text-xs numeric ${changeColor}`}>
            {arrow} {change}
          </span>
        )}
      </div>
    </div>
  );
}
