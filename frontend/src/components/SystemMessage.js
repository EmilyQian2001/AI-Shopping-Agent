import React from 'react';
import { AlertCircle } from 'lucide-react';

const SystemMessage = ({ content }) => {
  return (
    <div className="flex justify-center mb-6">
      <div className="flex items-center gap-2 py-2 px-4 bg-blue-50 text-blue-700 rounded-full border border-blue-100 shadow-sm max-w-max">
        <AlertCircle className="w-4 h-4" />
        <span className="text-sm font-medium">{content}</span>
      </div>
    </div>
  );
};

export default SystemMessage;