import React from 'react';
import { Info, Filter } from 'lucide-react';

const ComparisonSummary = ({ recommendations, sortConfig, onSortChange }) => {
  // Calculate min and max price
  const prices = recommendations
    .map(product => typeof product.price === 'number' ? product.price : null)
    .filter(price => price !== null);
  
  const minPrice = prices.length > 0 ? Math.min(...prices) : null;
  const maxPrice = prices.length > 0 ? Math.max(...prices) : null;
  
  // Get unique categories of "best for"
  const categories = [...new Set(
    recommendations
      .map(product => product.bestFor)
      .filter(Boolean)
  )];

  return (
    <div className="bg-gray-50 p-4 mb-4 rounded-lg border border-gray-200">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Info className="w-5 h-5 text-blue-500" />
          <h3 className="font-medium text-gray-800">Comparison Summary</h3>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Sort by:</span>
          <select 
            value={`${sortConfig.key}-${sortConfig.direction}`} 
            onChange={(e) => {
              const [key, direction] = e.target.value.split('-');
              onSortChange(key, direction);
            }}
            className="border border-gray-200 rounded-md px-2 py-1 text-sm"
          >
            <option value="name-ascending">Name (A-Z)</option>
            <option value="name-descending">Name (Z-A)</option>
            <option value="features-ascending">Features</option>
            <option value="bestFor-ascending">Best For</option>
          </select>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        <div className="bg-white p-3 rounded border border-gray-200">
          <div className="text-sm text-gray-500 mb-1">Products Compared</div>
          <div className="font-medium">{recommendations.length} products</div>
        </div>
        
        <div className="bg-white p-3 rounded border border-gray-200">
          <div className="text-sm text-gray-500 mb-1">Categories</div>
          <div className="flex flex-wrap gap-1 mt-1">
            {categories.slice(0, 3).map((category, index) => (
              <span key={index} className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700">
                <Filter className="w-3 h-3 mr-1" />
                {typeof category === 'string' && category.length > 20 
                  ? category.substring(0, 20) + '...' 
                  : category}
              </span>
            ))}
            {categories.length > 3 && (
              <span className="text-xs text-gray-500">+{categories.length - 3} more</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComparisonSummary;