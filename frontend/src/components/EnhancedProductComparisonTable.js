import React, { useState } from "react";
import { ExternalLink, ChevronUp, ChevronDown, ShoppingCart, Star } from "lucide-react";
import ComparisonSummary from "./ComparisonSummary";

const EnhancedProductComparisonTable = ({ recommendations, details }) => {
  const [sortConfig, setSortConfig] = useState({
    key: null,
    direction: 'ascending'
  });
  
  // Helper function to extract most relevant features in a concise format
  const extractKeyFeatures = (product) => {
    // Use features array if available, otherwise extract from description
    if (product.features && product.features.length > 0) {
      return product.features.join(", ");
    } else {
      // Extract key features from description
      const sentences = product.description.split(". ");
      // Just return the first two sentences for brevity
      return sentences.slice(0, 2).join(". ") + ".";
    }
  };

  // Helper function to extract what the product is best for
  const extractBestFor = (product) => {
    // Try to extract phrases with "ideal for", "perfect for", "best for", "great for"
    const description = product.description.toLowerCase();
    const phrases = ["ideal for", "perfect for", "best for", "great for", "designed for"];
    
    for (const phrase of phrases) {
      const index = description.indexOf(phrase);
      if (index !== -1) {
        // Extract the text after the phrase until end of sentence
        const startIndex = index + phrase.length;
        const endOfSentence = description.indexOf(".", startIndex);
        if (endOfSentence !== -1) {
          return description.substring(startIndex, endOfSentence + 1).trim();
        }
      }
    }
    
    // If no explicit "best for" phrase found, use pros
    if (product.pros && product.pros.length > 0) {
      return product.pros.slice(0, 2).join(". ");
    }
    
    // Fallback
    return "General purpose";
  };

  // Helper to get the price from a product
  const getPrice = (product, productDetails) => {
    if (product.price) {
      // If it's a string with a $ sign, extract the number
      if (typeof product.price === 'string' && product.price.includes('$')) {
        return parseFloat(product.price.replace(/[^0-9.]/g, ''));
      }
      return product.price;
    }
    
    // Try to extract from buy links
    if (productDetails && productDetails.buy_links && productDetails.buy_links.length > 0) {
      const prices = productDetails.buy_links
        .map(link => link.price)
        .filter(Boolean)
        .map(price => {
          // Extract just numbers from price text
          const match = price.match(/\$?([\d,.]+)/);
          return match ? parseFloat(match[1].replace(/,/g, '')) : null;
        })
        .filter(Boolean);
      
      if (prices.length > 0) {
        return Math.min(...prices);
      }
    }
    
    return 9999; // High number to sort unknown prices at the end
  };

  // Helper to get the price display
  const getPriceDisplay = (product, productDetails) => {
    if (product.price) {
      if (typeof product.price === 'number') {
        return `$${product.price.toFixed(2)}`;
      }
      return product.price;
    }
    
    // Try to extract from buy links
    if (productDetails && productDetails.buy_links && productDetails.buy_links.length > 0) {
      const priceTexts = productDetails.buy_links
        .map(link => link.price)
        .filter(Boolean)
        .map(price => {
          // Extract just numbers from price text
          const match = price.match(/\$?([\d,.]+)/);
          return match ? parseFloat(match[1].replace(/,/g, '')) : null;
        })
        .filter(Boolean);
      
      if (priceTexts.length > 0) {
        const minPrice = Math.min(...priceTexts);
        const maxPrice = Math.max(...priceTexts);
        
        if (minPrice === maxPrice) {
          return `$${minPrice.toFixed(2)}`;
        } else {
          return `$${minPrice.toFixed(2)} - $${maxPrice.toFixed(2)}`;
        }
      }
    }
    
    return "Price varies";
  };

  // Match recommendations with their details
  const productsWithDetails = recommendations.map((product, index) => {
    const productDetails = details && index < details.length ? details[index] : null;
    return {
      ...product,
      details: productDetails,
      keyFeatures: extractKeyFeatures(product),
      bestFor: extractBestFor(product),
      price: getPrice(product, productDetails),
      priceDisplay: getPriceDisplay(product, productDetails)
    };
  });

  // Sorting function
  const sortedProducts = [...productsWithDetails].sort((a, b) => {
    if (!sortConfig.key) return 0;
    
    let aValue, bValue;
    
    switch (sortConfig.key) {
      case 'name':
        aValue = a.name;
        bValue = b.name;
        break;
      case 'price':
        aValue = a.price;
        bValue = b.price;
        break;
      case 'features':
        aValue = a.keyFeatures;
        bValue = b.keyFeatures;
        break;
      case 'bestFor':
        aValue = a.bestFor;
        bValue = b.bestFor;
        break;
      default:
        return 0;
    }
    
    if (aValue < bValue) {
      return sortConfig.direction === 'ascending' ? -1 : 1;
    }
    if (aValue > bValue) {
      return sortConfig.direction === 'ascending' ? 1 : -1;
    }
    return 0;
  });

  // Request sort
  const requestSort = (key) => {
    let direction = 'ascending';
    if (sortConfig.key === key && sortConfig.direction === 'ascending') {
      direction = 'descending';
    }
    setSortConfig({ key, direction });
  };

  // Get sort direction indicator
  const getSortDirectionIndicator = (columnName) => {
    if (sortConfig.key !== columnName) {
      return null;
    }
    return sortConfig.direction === 'ascending' ? 
      <ChevronUp className="w-4 h-4" /> : 
      <ChevronDown className="w-4 h-4" />;
  };

  // Handle sort from summary component
  const handleSortChange = (key, direction) => {
    setSortConfig({ key, direction });
  };

  return (
    <div className="my-8">
      <ComparisonSummary 
        recommendations={sortedProducts} 
        sortConfig={sortConfig}
        onSortChange={handleSortChange}
      />
      
      <div className="overflow-hidden border border-gray-200 rounded-lg shadow-lg">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-gray-900 text-white text-sm">
              <th 
                className="px-6 py-4 text-left cursor-pointer hover:bg-gray-800"
                onClick={() => requestSort('name')}
              >
                <div className="flex items-center gap-1">
                  <span>Product Model</span>
                  {getSortDirectionIndicator('name')}
                </div>
              </th>
              <th 
                className="px-6 py-4 text-left cursor-pointer hover:bg-gray-800"
                onClick={() => requestSort('features')}
              >
                <div className="flex items-center gap-1">
                  <span>Key Features</span>
                  {getSortDirectionIndicator('features')}
                </div>
              </th>
              <th 
                className="px-6 py-4 text-left cursor-pointer hover:bg-gray-800"
                onClick={() => requestSort('bestFor')}
              >
                <div className="flex items-center gap-1">
                  <span>Best For</span>
                  {getSortDirectionIndicator('bestFor')}
                </div>
              </th>
              <th className="px-6 py-4 text-left">
                Shop
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {sortedProducts.map((product, index) => (
              <tr 
                key={index} 
                className={`${index % 2 === 0 ? "bg-white" : "bg-gray-50"} hover:bg-blue-50 transition-colors duration-150`}
              >
                <td className="px-6 py-4">
                  <div className="font-medium text-gray-800">{product.name}</div>
                  {product.details && product.details.reviews && product.details.reviews.length > 0 && (
                    <div className="flex items-center mt-1 text-yellow-500 text-xs">
                      <Star className="w-3 h-3 mr-1 fill-current" />
                      <span>Expert reviewed</span>
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 text-gray-700 max-w-xs">
                  {product.keyFeatures}
                </td>
                <td className="px-6 py-4 text-gray-700">
                  {product.bestFor}
                </td>
                <td className="px-6 py-4">
                  {product.details && product.details.buy_links && product.details.buy_links.length > 0 ? (
                    <div className="flex flex-col space-y-2">
                      {product.details.buy_links.map((link, i) => (
                        <a
                          key={i}
                          href={link.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center px-3 py-1 rounded bg-blue-50 text-blue-600 text-sm hover:bg-blue-100 transition-colors"
                        >
                          <ShoppingCart className="w-3 h-3 mr-1" />
                          {link.price}
                          <ExternalLink className="w-3 h-3 ml-1" />
                        </a>
                      ))}
                    </div>
                  ) : (
                    <span className="text-gray-400 text-sm">No buy links</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>
    </div>
  );
};

export default EnhancedProductComparisonTable;