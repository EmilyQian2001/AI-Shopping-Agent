import React, { useState } from 'react';
import { Code, Copy, Check } from 'lucide-react';

const JSONDisplay = ({ content, title }) => {
  const [copied, setCopied] = useState(false);
  
  // Extract JSON string from content
  const extractJson = (text) => {
    try {
      const jsonStart = text.indexOf('{');
      const jsonEnd = text.lastIndexOf('}') + 1;
      if (jsonStart >= 0 && jsonEnd > jsonStart) {
        const jsonStr = text.substring(jsonStart, jsonEnd);
        // Format JSON for better display
        const parsed = JSON.parse(jsonStr);
        return JSON.stringify(parsed, null, 2);
      }
    } catch (e) {
      console.error("JSON parsing error:", e);
    }
    return text; // Return original text if parsing fails
  };
  
  const formattedJson = extractJson(content);
  
  const copyToClipboard = () => {
    navigator.clipboard.writeText(formattedJson).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="my-4 border border-gray-200 bg-gray-50 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between bg-gray-100 px-4 py-2 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Code className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-medium text-gray-700">
            {title || "Recommendation JSON"}
          </span>
        </div>
        <button 
          onClick={copyToClipboard}
          className="text-gray-500 hover:text-gray-700 focus:outline-none"
          title="Copy JSON"
        >
          {copied ? (
            <Check className="w-4 h-4 text-green-500" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </button>
      </div>
      <pre className="p-4 text-sm text-gray-800 overflow-x-auto whitespace-pre-wrap">
        {formattedJson}
      </pre>
    </div>
  );
};

export default JSONDisplay;