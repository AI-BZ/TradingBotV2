import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface Price {
  symbol: string;
  price: number;
  change_24h?: number;
  change_pct_24h?: number;
}

interface PriceCardsProps {
  pricesData?: { prices: Price[] };
}

const PriceCards: React.FC<PriceCardsProps> = ({ pricesData }) => {
  if (!pricesData?.prices) {
    return (
      <div className="price-cards">
        <div className="loading">Loading prices...</div>
      </div>
    );
  }

  return (
    <div className="price-cards">
      {pricesData.prices.map((price) => {
        const isPositive = (price.change_pct_24h || 0) >= 0;
        const symbolName = price.symbol.replace('USDT', '');

        return (
          <div key={price.symbol} className="price-card">
            <div className="price-card-header">
              <span className="symbol-name">{symbolName}</span>
              <span className="symbol-pair">/{price.symbol.slice(-4)}</span>
            </div>
            <div className="price-card-price">
              ${price.price.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </div>
            <div className={`price-card-change ${isPositive ? 'positive' : 'negative'}`}>
              {isPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              <span>
                {isPositive ? '+' : ''}
                {price.change_pct_24h?.toFixed(2) || '0.00'}%
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default PriceCards;
