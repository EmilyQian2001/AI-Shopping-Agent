import React from "react";
import { ShoppingCart } from "lucide-react";
import { Card, CardContent } from "./Card";
import BuyLinks from "./BuyLinks";
import ExpertReviews from "./ExpertReviews";

const ProductDescription = ({ description }) => (
  <div>
    <p className="text-gray-600 leading-relaxed">{description}</p>
  </div>
);

const ProductCard = ({ product, details }) => {
  return (
    <Card className="my-8 overflow-hidden  shadow-lg border border-gray-200 rounded-lg hover:shadow-xl transition-shadow duration-300">
      <CardContent className="p-6">
        <h3 className="text-2xl font-bold mb-6 text-gray-800 flex items-center gap-3 pb-4 border-b border-gray-200">
          <ShoppingCart className="w-6 h-6 text-blue-500" />

          {product.name}
        </h3>

        <div className="mb-6">
          <h4 className="text-lg font-semibold mb-3 text-gray-800 flex items-center">
            Description:
          </h4>
          <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-lg p-4 border border-blue-100">
            <ProductDescription description={product.description} />
          </div>
        </div>

        {details && (
          <div>
            {details.buy_links && <BuyLinks links={details.buy_links} />}
            {details.reviews && <ExpertReviews reviews={details.reviews} />}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ProductCard;
