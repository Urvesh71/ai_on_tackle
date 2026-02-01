import { useState } from "react";
import { Copy, Check, Terminal, AlertCircle } from "lucide-react";
import { Button } from "./ui/button";
import { toast } from "sonner";

const FormulaCard = ({ formula, isError }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formula);
      setCopied(true);
      toast.success("Formula copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error("Failed to copy formula");
    }
  };

  if (isError) {
    return (
      <div
        data-testid="formula-error"
        className="flex items-start gap-3"
      >
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-red-500/20 border border-red-500/30 flex items-center justify-center">
          <AlertCircle className="w-4 h-4 text-red-400" />
        </div>
        <div className="px-5 py-4 bg-red-500/10 border border-red-500/20 rounded-2xl rounded-tl-sm">
          <p className="text-sm text-red-400">{formula}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="formula-output"
      className="flex items-start gap-3"
    >
      {/* AI Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
        <Terminal className="w-4 h-4 text-blue-400" />
      </div>

      {/* Formula card */}
      <div className="flex-1 max-w-[85%]">
        <div className="relative group bg-black/60 border border-blue-500/20 rounded-xl overflow-hidden formula-glow">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 bg-blue-500/5 border-b border-blue-500/10">
            <span className="text-xs font-medium text-blue-400/80 uppercase tracking-wider">
              Generated Formula
            </span>
            <Button
              data-testid="copy-formula-button"
              variant="ghost"
              size="icon"
              onClick={handleCopy}
              className="w-7 h-7 opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-blue-500/10"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-green-400" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-blue-400" />
              )}
            </Button>
          </div>

          {/* Formula content */}
          <div className="px-5 py-4">
            <code
              data-testid="formula-text"
              className="font-mono text-lg text-blue-300 tracking-wide break-all"
            >
              {formula}
            </code>
          </div>

          {/* Visual accent */}
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />
        </div>

        {/* Formula breakdown */}
        {formula && formula.includes(".") && (
          <div className="mt-3 flex flex-wrap gap-2">
            {formula.split(".").map((cmd, index) => (
              <span
                key={index}
                className="inline-flex items-center px-2.5 py-1 text-xs font-mono bg-zinc-800/50 border border-zinc-700/50 rounded-md text-zinc-400"
              >
                <span className="w-4 h-4 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-[10px] mr-2">
                  {index + 1}
                </span>
                {cmd}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default FormulaCard;
