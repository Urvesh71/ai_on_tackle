import { useState } from "react";
import { Copy, Check, Terminal, AlertCircle, Code } from "lucide-react";
import { Button } from "./ui/button";
import { toast } from "sonner";

const FormulaCard = ({ userText, technical, isError }) => {
  const [copiedUser, setCopiedUser] = useState(false);
  const [copiedTech, setCopiedTech] = useState(false);

  const handleCopyUser = async () => {
    try {
      await navigator.clipboard.writeText(userText);
      setCopiedUser(true);
      toast.success("User text copied to clipboard");
      setTimeout(() => setCopiedUser(false), 2000);
    } catch (err) {
      toast.error("Failed to copy");
    }
  };

  const handleCopyTech = async () => {
    try {
      await navigator.clipboard.writeText(technical);
      setCopiedTech(true);
      toast.success("Technical functions copied to clipboard");
      setTimeout(() => setCopiedTech(false), 2000);
    } catch (err) {
      toast.error("Failed to copy");
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
          <p className="text-sm text-red-400">{userText}</p>
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

      {/* Formula cards container */}
      <div className="flex-1 max-w-[85%] space-y-4">
        {/* User Text Formula */}
        <div className="relative group bg-black/60 border border-blue-500/20 rounded-xl overflow-hidden formula-glow">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 bg-blue-500/5 border-b border-blue-500/10">
            <div className="flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-blue-400/80" />
              <span className="text-xs font-medium text-blue-400/80 uppercase tracking-wider">
                User Text
              </span>
            </div>
            <Button
              data-testid="copy-user-text-button"
              variant="ghost"
              size="icon"
              onClick={handleCopyUser}
              className="w-7 h-7 opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-blue-500/10"
            >
              {copiedUser ? (
                <Check className="w-3.5 h-3.5 text-green-400" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-blue-400" />
              )}
            </Button>
          </div>

          {/* User text content */}
          <div className="px-5 py-4">
            <code
              data-testid="user-text-formula"
              className="font-mono text-lg text-blue-300 tracking-wide break-all"
            >
              {userText}
            </code>
          </div>

          {/* Visual accent */}
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />
        </div>

        {/* Technical Functions */}
        <div className="relative group bg-black/60 border border-emerald-500/20 rounded-xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 bg-emerald-500/5 border-b border-emerald-500/10">
            <div className="flex items-center gap-2">
              <Code className="w-3.5 h-3.5 text-emerald-400/80" />
              <span className="text-xs font-medium text-emerald-400/80 uppercase tracking-wider">
                Technical Functions Executed in Backend
              </span>
            </div>
            <Button
              data-testid="copy-technical-button"
              variant="ghost"
              size="icon"
              onClick={handleCopyTech}
              className="w-7 h-7 opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-emerald-500/10"
            >
              {copiedTech ? (
                <Check className="w-3.5 h-3.5 text-green-400" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-emerald-400" />
              )}
            </Button>
          </div>

          {/* Technical content */}
          <div className="px-5 py-4">
            <code
              data-testid="technical-functions"
              className="font-mono text-lg text-emerald-300 tracking-wide break-all"
            >
              {technical}
            </code>
          </div>

          {/* Visual accent */}
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/30 to-transparent" />
        </div>

        {/* Command breakdown */}
        {userText && userText.includes(".") && (
          <div className="mt-3 space-y-2">
            <span className="text-xs text-zinc-500 uppercase tracking-wider">Execution Steps:</span>
            <div className="flex flex-wrap gap-2">
              {userText.split(".").map((cmd, index) => {
                const techCmd = technical ? technical.split(".")[index] : "";
                return (
                  <div
                    key={index}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-mono bg-zinc-800/50 border border-zinc-700/50 rounded-lg"
                  >
                    <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-[10px] font-semibold">
                      {index + 1}
                    </span>
                    <div className="flex flex-col">
                      <span className="text-zinc-300">{cmd}</span>
                      <span className="text-emerald-400/70 text-[10px]">{techCmd}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FormulaCard;
