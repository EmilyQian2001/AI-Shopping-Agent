import React, { useState, useRef, useEffect } from "react";
import {
  Loader2,
  Send,
  ShoppingCart,
  Bot,
  Sparkles,
  Search,
  TrendingUp,
  Package,
  RefreshCw,
  Cpu,
} from "lucide-react";
import MessageBubble from "./components/MessageBubble";
import ProductCard from "./components/ProductCard";
import LogPanel from "./components/LogPanel";
import FeatureCard from "./components/FeatureCard";
import SuggestionButton from "./components/SuggestionButton";
import EnhancedProductComparisonTable from "./components/EnhancedProductComparisonTable";
import ViewToggleButton from "./components/ViewToggleButton";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Model selector component
const ModelSelector = ({ selectedModel, onChange }) => {
  return (
    <div className="flex items-center gap-2">
      <div className="p-1.5 bg-purple-100 rounded-md">
        <Cpu className="w-4 h-4 text-purple-600" />
      </div>
      <select
        value={selectedModel}
        onChange={(e) => onChange(e.target.value)}
        className="bg-white border border-gray-200 text-gray-700 py-1 px-2 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
      >
        <option value="perplexity">Perplexity</option>
        <option value="openai">OpenAI</option>
        <option value="hybrid">Hybrid (Both)</option>
      </select>
    </div>
  );
};

const ClarifyingQuestions = ({ questions, onAnswer, selectedPreferences }) => (
  <div className="my-4">
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-xl font-bold mb-6 text-gray-800">
        Let me help you find the perfect product! Please answer these questions:
      </h3>
      <div className="space-y-8">
        {Object.entries(questions).map(([category, data]) => (
          <div key={category} className="space-y-3">
            <div className="flex items-center gap-2">
              <h4 className="text-lg font-semibold text-gray-800">
                {category}
              </h4>
              <span className="text-gray-500">:</span>
            </div>
            <p className="text-gray-600">{data.question}</p>
            <div className="flex flex-wrap gap-3">
              {data.options.map((option, index) => (
                <button
                  key={index}
                  type="button" // Explicitly set type to prevent form submission
                  onClick={(e) => {
                    e.preventDefault(); // Prevent default action
                    e.stopPropagation(); // Stop event propagation
                    onAnswer(category, option);
                  }}
                  className={`px-6 py-2 rounded-full border-2 transition-colors font-medium
                    ${
                      selectedPreferences[category] === option
                        ? "bg-blue-500 border-blue-500 text-white"
                        : "border-blue-500 text-blue-500 hover:bg-blue-500 hover:text-white"
                    }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

const OverviewMessage = ({ content }) => {
  const [displayedText, setDisplayedText] = useState("");
  const [isStreaming, setIsStreaming] = useState(true);

  useEffect(() => {
    try {
      if (!content) {
        setIsStreaming(false);
        return;
      }

      const jsonStart = content.indexOf("{");
      const jsonEnd = content.lastIndexOf("}") + 1;

      // Check for valid JSON positions
      if (jsonStart === -1 || jsonEnd <= jsonStart) {
        setIsStreaming(false);
        setDisplayedText("Unable to parse overview data. Please try again.");
        return;
      }

      const jsonStr = content.substring(jsonStart, jsonEnd);
      const parsedJson = JSON.parse(jsonStr);

      // Check if overview exists
      if (!parsedJson || !parsedJson.overview) {
        setIsStreaming(false);
        setDisplayedText("No overview available for this recommendation.");
        return;
      }

      const overview = parsedJson.overview;

      let currentIndex = 0;
      const streamInterval = setInterval(() => {
        if (currentIndex <= overview.length) {
          setDisplayedText(overview.slice(0, currentIndex));
          currentIndex++;
        } else {
          clearInterval(streamInterval);
          setIsStreaming(false);
        }
      }, 20); // Adjust speed as needed

      return () => clearInterval(streamInterval);
    } catch (err) {
      console.error("Failed to parse overview:", err);
      setIsStreaming(false);
      setDisplayedText("An error occurred while processing the overview.");
    }
  }, [content]);

  return (
    <div className="flex items-center gap-4 mb-6">
      <div className="w-7 h-7 rounded-full bg-blue-500/10 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-blue-500" />
      </div>
      <div className="bg-gray-100 py-3 px-4 rounded-2xl text-gray-700">
        {displayedText}
        {isStreaming && <span className="animate-pulse">▋</span>}
      </div>
    </div>
  );
};

const App = () => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [productDetails, setProductDetails] = useState([]);
  const [loading, setLoading] = useState(false);
  const [productLoading, setProductLoading] = useState(false);
  const [error, setError] = useState("");
  const [clarifyingQuestions, setClarifyingQuestions] = useState(null);

  // Split preferences into two states:
  // persistedPreferences - for data persistence and API requests
  // displayedPreferences - for UI display in the input field
  const [persistedPreferences, setPersistedPreferences] = useState({});
  const [displayedPreferences, setDisplayedPreferences] = useState({});

  const [currentQuery, setCurrentQuery] = useState("");
  const [sessionId, setSessionId] = useState(""); // Track conversation session
  const [hasInitialRecommendation, setHasInitialRecommendation] =
    useState(false); // Track if we've shown recommendations
  const [modelChoice, setModelChoice] = useState("perplexity"); // New state for model selection
  const [isClarified, setIsClarified] = useState(false); // New state to track if query is clarified

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Function to refresh the page and clear conversation history
  const handleRefresh = () => {
    if (
      window.confirm(
        "This will clear your conversation history and start over. Continue?"
      )
    ) {
      setPersistedPreferences({});
      setDisplayedPreferences({});
      setIsClarified(false); // Reset clarification state
      window.location.reload();
    }
  };

  // Function to switch model during an active conversation
  const handleModelSwitch = async (newModel) => {
    if (!sessionId) {
      setModelChoice(newModel);
      return;
    }

    try {
      // Call the API to switch the model for the current session
      const res = await fetch(`${API_URL}/api/switch-model/${sessionId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model_choice: newModel,
        }),
      });

      if (!res.ok) throw new Error("Failed to switch model");

      // Update the local model choice state
      setModelChoice(newModel);

      // Add a system message about the model switch
      addToMessageQueue({
        type: "assistant",
        content: `AI model switched to ${getModelName(newModel)}.`,
      });
    } catch (err) {
      setError("Error: " + err.message);
    }
  };

  const getModelName = (modelKey) => {
    const models = {
      perplexity: "Perplexity",
      openai: "OpenAI GPT-4",
      hybrid: "Hybrid (Perplexity + OpenAI)",
    };
    return models[modelKey] || modelKey;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Modified to update both preference states
  const handleRemovePreference = (category) => {
    setPersistedPreferences((prev) => {
      const newPreferences = { ...prev };
      delete newPreferences[category];
      return newPreferences;
    });

    setDisplayedPreferences((prev) => {
      const newPreferences = { ...prev };
      delete newPreferences[category];
      return newPreferences;
    });
  };

  // Modified to update both preference states
  const handleQuestionAnswer = (category, answer) => {
    console.log(`Selected preference: ${category} = ${answer}`);

    setPersistedPreferences((prev) => ({
      ...prev,
      [category]: answer,
    }));

    setDisplayedPreferences((prev) => ({
      ...prev,
      [category]: answer,
    }));
  };

  const addToMessageQueue = (newItems) => {
    setMessages((prev) => [
      ...prev,
      ...(Array.isArray(newItems) ? newItems : [newItems]),
    ]);
  };

  const removeLoadingMessages = () => {
    setMessages((prev) => prev.filter((msg) => msg.type !== "loading"));
  };

  // Simplified API request handler
  const sendRequest = async (
    message,
    preferences,
    sessionId,
    isFollowup,
    modelChoice
  ) => {
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          preferences,
          session_id: sessionId,
          is_followup: isFollowup,
          model_choice: modelChoice,
        }),
      });

      if (!res.ok) throw new Error("Failed to get response");
      return await res.json();
    } catch (err) {
      throw new Error("API request failed: " + err.message);
    }
  };

  // Process recommendations and fetch product details
  const processRecommendations = async (data, sessionId) => {
    // Helper to extract recommendations from response
    const extractRecommendations = (responseText) => {
      try {
        const jsonStart = responseText.indexOf("{");
        const jsonEnd = responseText.lastIndexOf("}") + 1;

        if (jsonStart === -1 || jsonEnd <= jsonStart) {
          throw new Error("Invalid JSON structure in response");
        }

        const jsonStr = responseText.substring(jsonStart, jsonEnd);
        return JSON.parse(jsonStr);
      } catch (err) {
        console.error("Error parsing JSON response:", err);
        throw new Error("Failed to parse recommendations");
      }
    };

    // Poll for product details
    const pollForProductDetails = async (sessionId) => {
      return new Promise((resolve, reject) => {
        const poll = async () => {
          try {
            const detailsRes = await fetch(
              `${API_URL}/api/product-details/${sessionId}`
            );

            if (!detailsRes.ok) {
              throw new Error("Failed to fetch product details");
            }

            const detailsData = await detailsRes.json();

            if (detailsData.status === "processing") {
              // Continue polling after a delay
              setTimeout(poll, 2000);
            } else if (detailsData.status === "completed") {
              resolve(detailsData);
            } else {
              reject(
                new Error("Unexpected status in product details response")
              );
            }
          } catch (err) {
            reject(err);
          }
        };

        // Start polling
        poll();
      });
    };

    // Parse the original response for recommendations
    const parsedResponse = extractRecommendations(data.response);

    // Wait for product details to be ready
    const detailsData = await pollForProductDetails(sessionId);

    return {
      recommendations: parsedResponse.recommendations || [],
      details: detailsData.product_details || [],
      overview: parsedResponse.overview || null,
    };
  };

  // Check if the response requires clarification
  const needsClarification = (responseText) => {
    try {
      const jsonStart = responseText.indexOf("{");
      const jsonEnd = responseText.lastIndexOf("}") + 1;

      if (jsonStart === -1 || jsonEnd <= jsonStart) {
        return false;
      }

      const jsonStr = responseText.substring(jsonStart, jsonEnd);
      const parsedResponse = JSON.parse(jsonStr);

      return parsedResponse.type === "clarification"
        ? parsedResponse.questions
        : null;
    } catch (e) {
      console.error("Error parsing clarification check:", e);
      return false;
    }
  };

  // Combined function for all query types (initial, enhanced, and followup)
  const sendQuery = async (
    message,
    preferences,
    sessionId,
    isFollowup,
    modelChoice
  ) => {
    setLoading(true);
    setError("");

    console.log("Sending query:", {
      message,
      preferences,
      sessionId,
      isFollowup,
      modelChoice,
    });
    // Add loading message
    addToMessageQueue({
      type: "loading",
      content: isFollowup ? "AI is thinking..." : "Analyzing your needs...",
    });

    try {
      // Make API request
      const data = await sendRequest(
        message,
        preferences,
        sessionId,
        isFollowup,
        modelChoice
      );
      removeLoadingMessages();

      // Store the session ID if it's returned
      if (data.session_id) {
        console.log(`Setting session ID to ${data.session_id}`);
        setSessionId(data.session_id);
      }

      // Check if we need clarification
      const clarifyingQuestions = needsClarification(data.response);

      if (clarifyingQuestions) {
        // We need clarification - show questions and update state
        setIsClarified(false);
        setClarifyingQuestions(clarifyingQuestions);

        addToMessageQueue([
          {
            type: "assistant",
            content:
              "To help you find the perfect product, I need to know more about your preferences:",
          },
          {
            type: "clarification",
            content: clarifyingQuestions,
          },
        ]);

        setLoading(false);
        return;
      }

      // If we're here, no clarification needed
      setIsClarified(true);
      setClarifyingQuestions(null);

      // Immediately show JSON response (for overview)
      addToMessageQueue({
        type: "json_output",
        content: data.response,
      });

      // Add the loading message for product details
      addToMessageQueue({
        type: "loading",
        content: "Fetching recommendation details...",
      });

      // Process recommendations and fetch product details
      try {
        const results = await processRecommendations(
          data,
          data.session_id || sessionId
        );

        // Remove loading messages
        removeLoadingMessages();

        // Add assistant message and product cards
        addToMessageQueue([
          {
            type: "assistant",
            content: "Here are some products I have found for you:",
          },
          {
            type: "products",
            content: {
              recommendations: results.recommendations,
              details: results.details,
            },
          },
        ]);

        // Update state
        setRecommendations(results.recommendations);
        setProductDetails(results.details);
        setHasInitialRecommendation(true);
      } catch (err) {
        console.error("Error processing product details:", err);
        removeLoadingMessages();
        addToMessageQueue({
          type: "assistant",
          content:
            "I had trouble retrieving detailed product information. Please try again or refine your search.",
        });
      }
    } catch (err) {
      console.error("Error sending query:", err);
      removeLoadingMessages();
      setError("Error: " + err.message);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // Simplified handleSubmit function that follows the state diagram flow
  const handleSubmit = async (e) => {
    e.preventDefault();
    console.log("Form submitted");

    // Don't proceed if input is empty (unless we have selected preferences to submit)
    if (!input.trim() && Object.keys(displayedPreferences).length === 0) return;

    const userMessage = input.trim();
    setInput("");
    setError("");

    // Always show the user message
    if (Object.keys(displayedPreferences).length > 0) {
      // Combine message with existing preferences
      const preferencesStr = Object.entries(persistedPreferences)
        .map(([key, value]) => `${key}: ${value}`)
        .join(", ");

      const enhancedMessage = [preferencesStr, userMessage]
        .filter(Boolean)
        .join(", ");
      addToMessageQueue({ type: "user", content: enhancedMessage });
    } else {
      addToMessageQueue({ type: "user", content: userMessage });
    }

    // Follow the state diagram logic
    if (sessionId === "") {
      // INITIAL STATE -> ANALYZING_QUERY
      console.log("Starting new conversation");
      await sendQuery(userMessage, null, "", false, modelChoice);
    } else if (isClarified) {
      // Already in GENERATING_QUERY or RECOMMENDING -> Handle as follow-up
      console.log("Handling as follow-up query");
      await sendQuery(
        userMessage,
        persistedPreferences,
        sessionId,
        true,
        modelChoice
      );
    } else if (clarifyingQuestions) {
      // In CLARIFYING state -> Process preferences
      console.log("Processing preferences in clarification state");

      // Combine message with existing preferences
      const preferencesStr = Object.entries(persistedPreferences)
        .map(([key, value]) => `${key}: ${value}`)
        .join(", ");

      const enhancedMessage = [preferencesStr, userMessage]
        .filter(Boolean)
        .join(", ");

      // Clear displayed preferences after submission but keep persisted preferences
      setDisplayedPreferences({});

      // Send enhanced query to move from CLARIFYING -> GENERATING_QUERY
      await sendQuery(
        enhancedMessage,
        persistedPreferences,
        sessionId,
        false,
        modelChoice
      );
    }
  };

  // Clean implementations of the original functions using the above helpers
  const sendEnhancedQuery = (query, preferences, isFollowup = false) => {
    return sendQuery(query, preferences, sessionId, isFollowup, modelChoice);
  };

  const sendFollowupQuery = (message) => {
    return sendQuery(
      message,
      persistedPreferences,
      sessionId,
      true,
      modelChoice
    );
  };

  const focusInput = () => {
    inputRef.current?.focus();
  };

  // Modified renderMessage function to use persistedPreferences for clarification questions
  const renderMessage = (message, index) => {
    return (
      <div
        key={index}
        style={{ order: index }} // Use CSS order to enforce rendering sequence
      >
        {(() => {
          switch (message.type) {
            case "user":
            case "assistant":
              return <MessageBubble message={message} />;

            case "loading":
              return (
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex items-center gap-2 text-gray-500 bg-gray-100 py-2 px-4 rounded-2xl">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>{message.content}</span>
                  </div>
                </div>
              );

            case "json_output":
              // Replace JSONDisplay with OverviewMessage
              return <OverviewMessage content={message.content} />;

            case "clarification":
              return (
                <ClarifyingQuestions
                  questions={message.content}
                  onAnswer={handleQuestionAnswer}
                  selectedPreferences={persistedPreferences} // Use persistedPreferences here
                />
              );

              case "products":
                return (
                  <div className="mt-6">
                    {/* product view */}
                    <div className="mt-10 mb-4 border-t border-gray-200 pt-8">
                      <h3 className="text-xl font-semibold text-gray-800 mb-4">Product Comparison</h3>
                      <EnhancedProductComparisonTable 
                        recommendations={message.content.recommendations} 
                        details={message.content.details} 
                      />
                    </div>
                    {/* card view */}
                    <div className="mb-8">
                      <h3 className="text-xl font-semibold text-gray-800 mb-4">Product Details</h3>
                      {message.content.recommendations.map((product, idx) => (
                        <ProductCard
                          key={idx}
                          product={product}
                          details={
                            message.content.details &&
                            idx < message.content.details.length
                              ? message.content.details[idx]
                              : null
                          }
                        />
                      ))}
                    </div>
                  </div>
              );

            default:
              return null;
          }
        })()}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="w-full max-w-[1800px] mx-auto p-6">
        {/* Header with properly aligned elements */}
        <header className="text-center mb-12">
          <h1 className="text-2xl font-bold text-gray-800 mb-3 flex items-center justify-center gap-3">
            <div className="p-3 bg-blue-500 rounded-xl shadow-lg">
              <ShoppingCart className="w-8 h-8 text-white" />
            </div>
            AI Shopping Agent
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-600">
              <Sparkles className="w-4 h-4 mr-1" />
              AI Powered
            </span>
          </h1>
        </header>

        <div className="flex gap-6">
          {/* Main Chat Area */}
          <div className="flex-1">
            <div className="bg-white rounded-xl shadow-xl border border-gray-100 mb-4 h-[calc(100vh-160px)]">
              <div className="h-[calc(100%-80px)] overflow-y-auto p-6">
                {messages.length === 0 ? (
                  <div className="text-center mt-12">
                    {/* Model Selector - Only shown at start */}
                    <div className="flex justify-center mb-6">
                      <div className="inline-flex items-center p-2 bg-gray-50 rounded-lg border border-gray-200">
                        <span className="mr-2 text-sm text-gray-600">
                          AI Model:
                        </span>
                        <ModelSelector
                          selectedModel={modelChoice}
                          onChange={setModelChoice}
                        />
                      </div>
                    </div>

                    {/* Feature Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                      <FeatureCard
                        icon={<Search className="w-6 h-6" />}
                        title="Smart Search"
                        description="Advanced AI-powered product search and recommendations"
                        color="blue"
                      />
                      <FeatureCard
                        icon={<TrendingUp className="w-6 h-6" />}
                        title="Price Tracking"
                        description="Compare prices across multiple retailers"
                        color="green"
                      />
                      <FeatureCard
                        icon={<Package className="w-6 h-6" />}
                        title="Expert Reviews"
                        description="Access detailed product reviews and analyses"
                        color="purple"
                      />
                    </div>

                    {/* Examples Section */}
                    <div className="max-w-2xl mx-auto">
                      <h2 className="text-lg font-medium text-gray-700 mb-5">
                        Try these examples:
                      </h2>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {[
                          "Find laptops under $1500",
                          "Recommend espresso machine",
                          "Find sunglasses under $100",
                          "Find running shoes in white",
                        ].map((suggestion, index) => (
                          <SuggestionButton
                            key={index}
                            suggestion={suggestion}
                            onClick={() => {
                              setInput(suggestion);
                              inputRef.current?.focus();
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Model Selector - Always visible during conversation */}
                    <div className="flex justify-end mb-4">
                      <div className="inline-flex items-center p-2 bg-gray-50 rounded-lg border border-gray-200">
                        <span className="mr-2 text-sm text-gray-600">
                          AI Model:
                        </span>
                        <ModelSelector
                          selectedModel={modelChoice}
                          onChange={handleModelSwitch}
                        />
                      </div>
                    </div>

                    {/* Debug info for development */}
                    {process.env.NODE_ENV === "development" && (
                      <div className="bg-gray-50 p-2 text-xs text-gray-500 rounded">
                        Session ID: {sessionId || "none"} | Preferences:{" "}
                        {JSON.stringify(persistedPreferences)} | Model:{" "}
                        {modelChoice} | Clarified: {isClarified ? "Yes" : "No"}
                      </div>
                    )}

                    {messages.map((message, index) =>
                      renderMessage(message, index)
                    )}
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Area with Send and New Chat buttons */}
              <form
                onSubmit={handleSubmit}
                className="p-4 border-t border-gray-100"
              >
                <div className="flex gap-3">
                  <div className="flex-1 relative">
                    <div
                      className="w-full min-h-12 pl-12 pr-4 py-3 border border-gray-200 rounded-xl cursor-text flex flex-wrap items-center gap-2 focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-100 transition-all duration-200"
                      onClick={focusInput}
                    >
                      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                        <Search className="w-5 h-5" />
                      </div>
                      {/* Only show tags from displayedPreferences, not persistedPreferences */}
                      {Object.entries(displayedPreferences).map(
                        ([category, answer]) => (
                          <span
                            key={category}
                            className="flex items-center gap-1 px-3 py-1 bg-blue-500 text-white text-sm rounded-full border border-blue-500"
                          >
                            {category}: {answer}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRemovePreference(category);
                              }}
                              className="ml-1 hover:text-blue-200"
                            >
                              ×
                            </button>
                          </span>
                        )
                      )}
                      <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        className="flex-1 min-w-40 outline-none bg-transparent"
                        placeholder={
                          isClarified
                            ? "Tell me more about what you're looking for..."
                            : clarifyingQuestions
                            ? "Enter your preference or select options above..."
                            : "Tell me what you want to buy..."
                        }
                      />
                    </div>
                  </div>

                  {/* Send Button - Now First */}
                  <button
                    type="submit"
                    disabled={
                      loading ||
                      (!input.trim() &&
                        Object.keys(displayedPreferences).length === 0 &&
                        !isClarified)
                    }
                    className="px-6 py-3 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 shadow-lg shadow-blue-500/30 hover:shadow-blue-500/40"
                  >
                    {loading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        <Send className="w-5 h-5" />
                        <span className="font-medium hidden sm:inline">
                          Send
                        </span>
                      </>
                    )}
                  </button>

                  {/* New Chat Button - Now Second */}
                  <button
                    type="button"
                    onClick={handleRefresh}
                    className="px-4 py-3 bg-blue-100 text-blue-600 rounded-xl hover:bg-blue-200 transition-colors duration-200 flex items-center gap-2"
                    title="Start a new conversation"
                  >
                    <RefreshCw className="w-5 h-5" />
                    <span className="font-medium hidden sm:inline">
                      New Chat
                    </span>
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Log Panel */}
          <LogPanel />
        </div>

        {error && (
          <div className="p-4 bg-red-50 text-red-700 rounded-xl border border-red-100 mt-4">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default App;
