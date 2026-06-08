import { useState } from "react";
import { Copy, Check, ListOrdered, Code, Terminal } from "lucide-react";
import { Button } from "./ui/button";
import { toast } from "sonner";

const PlanCard = ({ steps, confirmationMessage, onConfirm }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyAll = async () => {
    const all = (steps || [])
      .map((s) => `${s.n}. ${s.command}  ->  ${s.function}`)
      .join("\n");
    try {
      await navigator.clipboard.writeText(all);
      setCopied(true);
      toast.success("Plan copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      toast.error("Failed to copy");
    }
  };

  return (
    <div data-testid="plan-card" className="flex items-start gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
        <Terminal className="w-4 h-4 text-blue-400" />
      </div>

      <div className="flex-1 max-w-[85%] space-y-3">
        <div className="bg-black/60 border border-amber-500/25 rounded-xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 bg-amber-500/5 border-b border-amber-500/10">
            <div className="flex items-center gap-2">
              <ListOrdered className="w-3.5 h-3.5 text-amber-300/90" />
              <span className="text-xs font-medium text-amber-300/90 uppercase tracking-wider">
                Proposed Plan — Awaiting Your Confirmation
              </span>
            </div>
            <Button
              data-testid="copy-plan-button"
              variant="ghost"
              size="icon"
              onClick={handleCopyAll}
              className="w-7 h-7 hover:bg-amber-500/10"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-green-400" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-amber-300/90" />
              )}
            </Button>
          </div>

          {/* Steps */}
          <ol className="px-5 py-4 space-y-2" data-testid="plan-steps">
            {(steps || []).map((s) => (
              <li
                key={s.n}
                data-testid={`plan-step-${s.n}`}
                className="flex items-start gap-3"
              >
                <span className="mt-0.5 w-6 h-6 shrink-0 rounded-full bg-amber-500/15 border border-amber-500/25 text-amber-300 text-[11px] font-semibold flex items-center justify-center font-mono">
                  {s.n}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <code className="font-mono text-sm text-blue-300 break-all">
                      {s.command}
                    </code>
                    <span className="text-zinc-600 text-xs">→</span>
                    <code className="font-mono text-sm text-emerald-300 break-all">
                      {s.function}
                    </code>
                  </div>
                  {s.description ? (
                    <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">
                      {s.description}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </div>

        {/* Confirmation prompt */}
        <div
          data-testid="plan-confirmation-message"
          className="px-4 py-3 bg-amber-500/5 border border-amber-500/20 rounded-lg"
        >
          <p className="text-sm text-amber-200/90 leading-relaxed">
            {confirmationMessage ||
              "Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."}
          </p>
          <p className="text-[11px] text-zinc-500 mt-1.5">
            Tip: reply <span className="text-amber-300 font-mono">yes</span> /{" "}
            <span className="text-amber-300 font-mono">ok</span> /{" "}
            <span className="text-amber-300 font-mono">proceed</span>, or type
            something like <em>&quot;swap step 2 and 3&quot;</em> to modify.
          </p>
          {onConfirm ? (
            <button
              data-testid="plan-confirm-button"
              onClick={onConfirm}
              className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 text-xs font-medium transition-colors"
            >
              <Check className="w-3.5 h-3.5" /> Confirm &amp; execute
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default PlanCard;
