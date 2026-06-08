import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import ChatInput from "../components/ChatInput";
import ChatMessage from "../components/ChatMessage";
import FormulaCard from "../components/FormulaCard";
import PlanCard from "../components/PlanCard";
import ClarifyCard from "../components/ClarifyCard";
import { Terminal, Sparkles } from "lucide-react";
import { ScrollArea } from "../components/ui/scroll-area";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Safe UUID generator that works on HTTP / non-secure contexts
// (crypto.randomUUID is only available on HTTPS or localhost).
const generateUUID = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch (e) {
      // fallthrough to manual generator
    }
  }
  // RFC4122 v4 fallback using Math.random
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const ChatPage = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => generateUUID());
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSendMessage = async (message) => {
    if (!message.trim() || isLoading) return;

    const userMessage = {
      id: generateUUID(),
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/chat`, {
        message,
        session_id: sessionId,
      });

      const data = response.data || {};
      const mode = data.mode || "answer";

      const assistantMessage = {
        id: data.message_id || generateUUID(),
        role: "assistant",
        mode,
        // answer
        user_text: data.user_text,
        technical: data.technical,
        steps: data.steps,
        // plan
        confirmation_message: data.confirmation_message,
        // clarify
        question: data.question,
        suggestions: data.suggestions,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (data.session_id) {
        setSessionId(data.session_id);
      }
    } catch (error) {
      console.error("Chat error:", error);
      toast.error("Failed to process command. Please try again.");
      const errorMessage = {
        id: generateUUID(),
        role: "assistant",
        mode: "answer",
        user_text: "Error processing your request. Please try again.",
        isError: true,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const renderAssistant = (msg) => {
    if (msg.mode === "plan") {
      return (
        <PlanCard
          steps={msg.steps}
          confirmationMessage={msg.confirmation_message}
          onConfirm={() => handleSendMessage("yes")}
        />
      );
    }
    if (msg.mode === "clarify") {
      return (
        <ClarifyCard
          question={msg.question}
          suggestions={msg.suggestions}
          onPick={(s) => handleSendMessage(s.command)}
        />
      );
    }
    // answer
    if (msg.user_text) {
      return (
        <FormulaCard
          userText={msg.user_text}
          technical={msg.technical}
          steps={msg.steps}
          isError={msg.isError}
        />
      );
    }
    return <ChatMessage message={{ ...msg, content: msg.user_text || "" }} />;
  };

  return (
    <div
      data-testid="chat-page"
      className="min-h-screen bg-[#09090b] relative overflow-hidden"
    >
      <div
        className="absolute inset-0 bg-texture opacity-5 mix-blend-overlay pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 grid-pattern pointer-events-none"
        aria-hidden="true"
      />

      <div className="relative z-10 flex flex-col h-screen">
        <header className="flex items-center gap-4 px-6 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
              <Terminal className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-white font-mono">
                Command Interpreter
              </h1>
              <p className="text-xs text-zinc-500">
                AI-powered formula generator
              </p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
            <Sparkles className="w-3 h-3 text-blue-400" />
            <span>Powered by Llama 3.1:8b from Ollama</span>
          </div>
        </header>

        <ScrollArea className="flex-1 px-4 md:px-8 lg:px-12">
          <div className="max-w-4xl mx-auto py-8 space-y-6">
            {messages.length === 0 ? (
              <div
                data-testid="empty-state"
                className="flex flex-col items-center justify-center h-[60vh] text-center"
              >
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/20 flex items-center justify-center mb-6">
                  <Terminal className="w-8 h-8 text-blue-400" />
                </div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  Start with a command
                </h2>
                <p className="text-zinc-500 max-w-md mb-8 leading-relaxed">
                  Type your request and I&apos;ll convert it into a hierarchical formula.
                  For multi-step requests I&apos;ll propose a plan and ask you to confirm.
                </p>
                <div className="grid gap-3 text-left">
                  <ExamplePrompt
                    text="Show blue zone"
                    onClick={() => handleSendMessage("Show blue zone")}
                  />
                  <ExamplePrompt
                    text="Open grid, create table in A5:E12, apply borders"
                    onClick={() =>
                      handleSendMessage(
                        "Open grid, create table in A5:E12, apply borders"
                      )
                    }
                  />
                  <ExamplePrompt
                    text="Copy and paste"
                    onClick={() => handleSendMessage("Copy and paste")}
                  />
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className="message-animate">
                  {msg.role === "user" ? (
                    <ChatMessage message={msg} />
                  ) : (
                    renderAssistant(msg)
                  )}
                </div>
              ))
            )}

            {isLoading && (
              <div className="flex items-center gap-2 px-6 py-4 glass rounded-2xl rounded-tl-sm max-w-[80%]">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-blue-400 typing-dot" />
                  <div className="w-2 h-2 rounded-full bg-blue-400 typing-dot" />
                  <div className="w-2 h-2 rounded-full bg-blue-400 typing-dot" />
                </div>
                <span className="text-sm text-zinc-400">Processing...</span>
              </div>
            )}

            <div ref={scrollRef} />
          </div>
        </ScrollArea>

        <div className="px-4 pb-8 pt-4">
          <div className="max-w-3xl mx-auto">
            <ChatInput onSend={handleSendMessage} disabled={isLoading} />
          </div>
        </div>
      </div>
    </div>
  );
};

const ExamplePrompt = ({ text, onClick }) => (
  <button
    data-testid={`example-prompt-${text.toLowerCase().replace(/\s+/g, "-").slice(0, 30)}`}
    onClick={onClick}
    className="text-left px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-sm text-zinc-400 hover:bg-white/10 hover:text-zinc-300 hover:border-blue-500/30 transition-all duration-200"
  >
    <span className="text-blue-400 mr-2">→</span>
    {text}
  </button>
);

export default ChatPage;
