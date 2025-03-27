import React, { useState, useEffect, useRef } from "react";
import { Terminal } from "lucide-react";

// Get API URL from environment or use localhost as default
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Function to dynamically generate WebSocket URL based on API URL
const getWebSocketUrl = () => {
  let host;
  if (API_URL.includes("://")) {
    host = API_URL.split("://")[1];
  } else {
    host = API_URL;
  }

  const protocol = API_URL.startsWith("https://") ? "wss" : "ws";
  return `${protocol}://${host}/ws/logs`;
};

// Format time consistently in 24-hour format
const formatTime = (date) => {
  // Format as HH:MM:SS (24-hour format)
  return date.toTimeString().split(' ')[0];
};

// Normalize timestamp to match client's local time format
const normalizeTimestamp = (timestamp) => {
  if (!timestamp) return formatTime(new Date());
  
  // If it looks like just a time without date (HH:MM:SS)
  if (/^\d{1,2}:\d{2}:\d{2}$/.test(timestamp)) {
    // Get current date and create a date object with server time
    const today = new Date();
    const serverHours = parseInt(timestamp.split(':')[0], 10);
    const serverMinutes = parseInt(timestamp.split(':')[1], 10); 
    const serverSeconds = parseInt(timestamp.split(':')[2], 10);
    
    // We'll normalize all timestamps to client's local time for consistency
    // Instead of trying to handle timezone conversion, we'll just use the client's current time
    return formatTime(new Date());
  }
  
  // For any other format, fallback to client's current time
  return formatTime(new Date());
};

const LogPanel = () => {
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const logEndRef = useRef(null);
  const wsRef = useRef(null);

  const scrollToBottom = () => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Helper function to determine log type based on content
  const getLogType = (message) => {
    if (!message) return "default";

    if (message.toLowerCase().includes("error")) return "error";
    if (
      message.toLowerCase().includes("success") ||
      message.toLowerCase().includes("found") ||
      message.toLowerCase().includes("received")
    )
      return "success";
    if (
      message.toLowerCase().includes("api") ||
      message.toLowerCase().includes("request") ||
      message.toLowerCase().includes("searching")
    )
      return "info";
    return "default";
  };

  // Function to highlight query in the log message
  const highlightQuery = (message) => {
    if (!message) return "";

    // Special handling for session ID messages
    if (message.includes("session:")) {
      const sessionIndex = message.indexOf("session:");
      if (sessionIndex !== -1) {
        const beforeSession = message.substring(0, sessionIndex + 8);
        let afterSession = message.substring(sessionIndex + 8).trim();
        if (afterSession.length > 36) {
          afterSession = afterSession.substring(0, 36);
        }
        return (
          <>
            {beforeSession}
            <span className="text-blue-500 font-medium">{afterSession}</span>
          </>
        );
      }
    }

    // Highlight original requests in follow-up queries
    if (message.includes("Original request:")) {
      try {
        const originalIndex = message.indexOf("Original request:");
        if (originalIndex !== -1) {
          const beforeOriginal = message.substring(0, originalIndex);
          const preferencesIndex = message.indexOf("Preferences:");
          const additionalIndex = message.indexOf("Additional requests:");

          // Handle case when preferences section is not found
          const originalRequestEnd =
            preferencesIndex !== -1
              ? preferencesIndex
              : additionalIndex !== -1
              ? additionalIndex
              : message.length;

          const originalRequest = message
            .substring(originalIndex, originalRequestEnd)
            .trim();

          let preferences = "";
          if (preferencesIndex !== -1) {
            const preferencesEnd =
              additionalIndex !== -1 ? additionalIndex : message.length;
            preferences = message
              .substring(preferencesIndex, preferencesEnd)
              .trim();
          }

          let additionalRequest = "";
          if (additionalIndex !== -1) {
            additionalRequest = message.substring(additionalIndex).trim();
          }

          return (
            <>
              {beforeOriginal}
              <span className="font-bold text-purple-600 bg-purple-50 px-1 rounded">
                {originalRequest}
              </span>
              {preferences && (
                <>
                  {" "}
                  <span className="text-blue-600">{preferences}</span>
                </>
              )}
              {additionalRequest && (
                <>
                  {" "}
                  <span className="font-bold text-green-600 bg-green-50 px-1 rounded">
                    {additionalRequest}
                  </span>
                </>
              )}
            </>
          );
        }
      } catch (error) {
        console.error("Error highlighting enhanced query:", error);
        return message;
      }
    }

    // Regular query highlighting
    if (!message.includes("query") && !message.includes("Query"))
      return message;

    try {
      const lowerMessage = message.toLowerCase();
      const queryIndex = lowerMessage.indexOf("query");
      if (queryIndex === -1) return message;

      const afterQuery = message.substring(queryIndex);
      const colonIndex = afterQuery.indexOf(":");

      if (colonIndex !== -1) {
        const beforeQuery = message.substring(0, queryIndex);
        const queryKeyword = message.substring(
          queryIndex,
          queryIndex + colonIndex + 1
        );
        const afterQueryText = afterQuery.substring(colonIndex + 1);

        const endIndex = afterQueryText.length;
        const queryValue = afterQueryText.substring(0, endIndex).trim();
        const remainingText = afterQueryText.substring(endIndex);

        return (
          <>
            {beforeQuery}
            {queryKeyword}
            <span className="font-bold text-purple-500 bg-purple-50 px-1 rounded">
              {queryValue}
            </span>
            {remainingText}
          </>
        );
      }
    } catch (error) {
      console.error("Error highlighting query:", error);
    }

    return message;
  };

  useEffect(() => {
    // Create WebSocket connection using the dynamic URL
    const wsUrl = getWebSocketUrl();
    console.log(`Connecting to WebSocket: ${wsUrl}`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      const currentTime = formatTime(new Date());
      setLogs((prev) => [
        ...prev,
        {
          timestamp: currentTime,
          message: "Connected to server",
          type: "success",
        },
      ]);
    };

    ws.onclose = () => {
      setIsConnected(false);
      const currentTime = formatTime(new Date());
      setLogs((prev) => [
        ...prev,
        {
          timestamp: currentTime,
          message: "Disconnected from server",
          type: "error",
        },
      ]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const currentTime = formatTime(new Date());
        
        // Always use current client time for consistency
        const logWithType = {
          ...data,
          timestamp: currentTime,
          type: getLogType(data.message),
        };

        setLogs((prev) => [...prev, logWithType]);
      } catch (error) {
        console.error("Error processing log message:", error);
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  return (
    <div className="w-96 h-[calc(100vh-160px)] bg-white rounded-xl shadow-xl border border-gray-100">
      <div className="h-10 border-b border-gray-100 flex items-center px-4 gap-2">
        <div className="p-2 bg-blue-50 rounded-lg">
          <Terminal className="w-4 h-4 text-blue-600" />
        </div>
        <h2 className="text-sm font-semibold text-gray-700">System Logs</h2>
        <div
          className={`ml-2 w-2 h-2 rounded-full ${
            isConnected ? "bg-green-500" : "bg-gray-400"
          }`}
        />
      </div>
      <div className="h-[calc(100%-40px)] overflow-y-auto p-4 bg-gray-50">
        <div className="space-y-2">
          {logs.map((log, index) => {
            // We no longer use the log type for color
            return (
              <div
                key={index}
                className={`
                  p-2 rounded text-xs font-mono 
                  ${index % 2 === 0 ? "bg-white" : "bg-gray-50"}
                  border-l-2 border-blue-300
                  shadow-sm
                `}
              >
                <span className="text-gray-400 font-medium">
                  [{log.timestamp}]
                </span>
                <span className="ml-2 text-gray-800">
                  {highlightQuery(log.message)}
                </span>
              </div>
            );
          })}
        </div>
        <div ref={logEndRef} />
      </div>
    </div>
  );
};

export default LogPanel;