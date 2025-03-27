import React from 'react';
import { Search } from 'lucide-react';

const SuggestionButton = ({ suggestion, onClick }) => (
  <button
    onClick={onClick}
    className="group w-full bg-blue-50/30 hover:bg-blue-50/50 rounded-xl transition-all duration-300"
  >
    <div className="px-4 py-3 flex items-center gap-3">
      <div className="text-blue-400 transition-colors duration-300">
        <Search className="w-4 h-4" strokeWidth={2.5} />
      </div>
      <span className="text-sm text-gray-600 group-hover:text-gray-900 transition-colors duration-300 text-left">
        {suggestion}
      </span>
    </div>
  </button>
);

export default SuggestionButton;