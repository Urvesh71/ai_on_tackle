import { HelpCircle, Terminal } from "lucide-react";

const ClarifyCard = ({ question, suggestions, onPick }) => {
  return (
    <div data-testid="clarify-card" className="flex items-start gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
        <Terminal className="w-4 h-4 text-blue-400" />
      </div>

      <div className="flex-1 max-w-[85%]">
        <div className="bg-black/60 border border-fuchsia-500/25 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2 bg-fuchsia-500/5 border-b border-fuchsia-500/10">
            <HelpCircle className="w-3.5 h-3.5 text-fuchsia-300/90" />
            <span className="text-xs font-medium text-fuchsia-300/90 uppercase tracking-wider">
              Clarification Needed
            </span>
          </div>

          <div className="px-5 py-4 space-y-3">
            <p
              data-testid="clarify-question"
              className="text-sm text-zinc-200 leading-relaxed"
            >
              {question}
            </p>

            {Array.isArray(suggestions) && suggestions.length > 0 ? (
              <div className="space-y-2">
                <p className="text-[11px] text-zinc-500 uppercase tracking-wider">
                  Did you mean:
                </p>
                <div className="flex flex-col gap-2">
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      data-testid={`clarify-suggestion-${i}`}
                      onClick={() => onPick && onPick(s)}
                      className="text-left px-3 py-2 rounded-lg bg-fuchsia-500/5 border border-fuchsia-500/20 hover:border-fuchsia-500/40 hover:bg-fuchsia-500/10 transition-colors"
                    >
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <code className="font-mono text-sm text-blue-300 break-all">
                          {s.command}
                        </code>
                        <span className="text-zinc-600 text-xs">→</span>
                        <code className="font-mono text-sm text-emerald-300 break-all">
                          {s.function}
                        </code>
                      </div>
                      {s.why ? (
                        <p className="text-[11px] text-zinc-400 mt-0.5 leading-relaxed">
                          {s.why}
                        </p>
                      ) : null}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-zinc-500">
                Please rephrase your request so I can find a matching command.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ClarifyCard;
