import { User } from "lucide-react";

const ChatMessage = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div
      data-testid={`chat-message-${message.role}`}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`flex items-start gap-3 max-w-[80%] ${
          isUser ? "flex-row-reverse" : "flex-row"
        }`}
      >
        {/* Avatar */}
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${
            isUser
              ? "bg-blue-500/20 border border-blue-500/30"
              : "bg-zinc-800 border border-zinc-700"
          }`}
        >
          {isUser ? (
            <User className="w-4 h-4 text-blue-400" />
          ) : (
            <span className="text-xs font-mono text-zinc-400">AI</span>
          )}
        </div>

        {/* Message bubble */}
        <div
          className={`px-5 py-3 ${
            isUser
              ? "bg-blue-500/10 border border-blue-500/20 rounded-2xl rounded-tr-sm text-white"
              : "bg-zinc-800/50 border border-zinc-700/50 rounded-2xl rounded-tl-sm text-zinc-300"
          }`}
        >
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
