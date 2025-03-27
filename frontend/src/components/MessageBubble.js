import React from "react";
import { Bot, User2 } from "lucide-react";

const MessageBubble = ({ message }) => (
  <div
    className={`flex items-start gap-4 mb-6 ${
      message.type === "user" ? "justify-end" : "justify-start"
    }`}
  >
    {message.type === "assistant" && (
      <div className="w-7 h-7 rounded-full bg-blue-500/10 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-blue-500" />
      </div>
    )}
    <div
      className={`max-w-[80%] px-4 py-3 rounded-2xl ${
        message.type === "user"
          ? "bg-blue-500 text-white"
          : "bg-gray-100 text-gray-700"
      }`}
    >
      <p className="whitespace-pre-wrap">{message.content}</p>
    </div>
    {message.type === "user" && (
      <div className="w-7 h-7 rounded-full bg-gray-500/10 flex items-center justify-center flex-shrink-0">
        <User2 className="w-4 h-4 text-gray-500" />
      </div>
    )}
  </div>
);

export default MessageBubble;
