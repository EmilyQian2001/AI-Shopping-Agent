import React from "react";
import { ExternalLink } from "lucide-react";
import { Card, CardContent } from "./Card";

const BuyLinks = ({ links }) => (
  <div>
    <h4 className="text-lg font-semibold mb-3 text-gray-800">Where to Buy:</h4>
    <div className="grid sm:grid-cols-2 gap-3">
      {links.map((link, index) => (
        <a
          key={index}
          href={link.link}
          target="_blank"
          rel="noopener noreferrer"
          className="group block"
        >
          <Card className="hover:shadow-md transition-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="w-16 h-16 flex-shrink-0">
                <img
                  src={link.imageUrl || "/api/placeholder/64/64"}
                  alt={link.title}
                  className="w-full h-full object-cover rounded"
                />
              </div>
              <div className="flex-grow">
                <div className="font-semibold text-gray-900 group-hover:text-blue-600 flex items-center gap-1">
                  {link.title}
                  <ExternalLink className="w-4 h-4 opacity-0 group-hover:opacity-100" />
                </div>
                <div className="text-lg font-bold text-gray-900">
                  {link.price}
                </div>
              </div>
            </CardContent>
          </Card>
        </a>
      ))}
    </div>
  </div>
);

export default BuyLinks;
