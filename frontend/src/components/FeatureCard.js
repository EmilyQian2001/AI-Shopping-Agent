import React from 'react';

const FeatureCard = ({ icon, title, description, color }) => {
  const colors = {
    blue: "bg-blue-50/50 text-blue-500",
    green: "bg-green-50/50 text-green-500",
    purple: "bg-purple-50/50 text-purple-500"
  };

  return (
    <div className="relative rounded-2xl bg-white p-5 group transition-all duration-300">
      {/* Subtle border gradient */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-b from-gray-100/50 via-transparent to-transparent" />
      
      <div className="relative">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${colors[color]}`}>
          {icon}
        </div>
        <h3 className="text-base font-semibold text-gray-800 mb-1.5">
          {title}
        </h3>
        <p className="text-gray-500 text-sm leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
};

export default FeatureCard;