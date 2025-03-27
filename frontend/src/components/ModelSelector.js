import React from 'react';
import { Cpu } from 'lucide-react';

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

export default ModelSelector;