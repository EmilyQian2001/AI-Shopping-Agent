import React from "react";
import { ExternalLink, Star, Link as LinkIcon } from "lucide-react";
import { Card, CardContent } from "./Card";

const ExpertReviews = ({ reviews }) => (
  <div className="border-t border-gray-200 pt-4">
    <h4 className="text-lg font-semibold mb-3 text-gray-800 flex items-center">
      <Star className="w-5 h-5 text-yellow-500 mr-2" />
      Review Summary:
    </h4>
    <Card className="mb-3 bg-gradient-to-r from-white to-blue-50 border border-blue-100">
      <CardContent className="p-4">
        <div className="flex items-start gap-2">
          <p className="text-gray-700">
            "{reviews[0]?.summary || "No review summary available."}"
          </p>
        </div>
      </CardContent>
    </Card>

    {/* Review Links */}
    {reviews.length > 0 && (
      <div className="flex items-center gap-2 p-2 rounded-lg">
        <span className="text-sm text-gray-600">Read full reviews:</span>
        {reviews.map((review, index) => (
          <a
            key={index}
            href={review.link}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 bg-white hover:bg-gradient-to-r hover:from-white hover:to-blue-100 rounded-full transition-colors shadow-sm"
            title={review.title}
          >
            <LinkIcon className="w-4 h-4 text-blue-500" />
          </a>
        ))}
      </div>
    )}
  </div>
);

export default ExpertReviews;
