import React from 'react';
import { LayoutGrid, Table2 } from 'lucide-react';

const ViewToggleButton = ({ isTableView, onToggle }) => {
  return (
    <button
      onClick={onToggle}
      className="flex items-center gap-2 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg border border-blue-100 transition-colors duration-200"
      title={isTableView ? "Switch to card view" : "Switch to table view"}
    >
      {isTableView ? (
        <>
          <LayoutGrid className="w-4 h-4" />
          <span className="text-sm font-medium">Card View</span>
        </>
      ) : (
        <>
          <Table2 className="w-4 h-4" />
          <span className="text-sm font-medium">Table View</span>
        </>
      )}
    </button>
  );
};

export default ViewToggleButton;