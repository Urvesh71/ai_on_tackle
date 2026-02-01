import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "./ui/button";

const ChatInput = ({ onSend, disabled }) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="glass rounded-full input-glow transition-all duration-300 focus-within:border-blue-500/50">
        <input
          data-testid="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your command... (e.g., 'go to grids, create table')"
          disabled={disabled}
          className="w-full bg-transparent px-6 py-4 pr-14 text-white placeholder:text-zinc-500 focus:outline-none disabled:opacity-50"
        />
        <Button
          data-testid="send-button"
          type="submit"
          disabled={disabled || !input.trim()}
          size="icon"
          className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-blue-500 hover:bg-blue-600 disabled:opacity-30 disabled:hover:bg-blue-500 transition-all duration-200"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
      <p className="text-xs text-zinc-600 mt-3 text-center">
        Press Enter to send • Supports single and multi-command sequences
      </p>
    </form>
  );
};

export default ChatInput;
