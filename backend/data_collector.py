"""
Historical Data Collection System
10개월간의 OHLCV 데이터를 Binance에서 다운로드하고 저장하는 시스템
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from pathlib import Path
import logging
from binance_client import BinanceClient
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCollector:
    """Historical market data collector from Binance"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 testnet: bool = False, data_dir: str = "data"):
        self.client = BinanceClient(api_key, api_secret, testnet)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # 기본 심볼 리스트 (주요 암호화폐 10개)
        self.symbols = [
            'BTCUSDT',   # Bitcoin
            'ETHUSDT',   # Ethereum
            'BNBUSDT',   # Binance Coin
            'SOLUSDT',   # Solana
            'ADAUSDT',   # Cardano
            'DOTUSDT',   # Polkadot
            'MATICUSDT', # Polygon
            'AVAXUSDT',  # Avalanche
            'UNIUSDT',   # Uniswap
            'LINKUSDT'   # Chainlink
        ]

        # Progress tracking
        self.progress_file = self.data_dir / "download_progress.json"
        self.progress = self.load_progress()

    def load_progress(self) -> Dict:
        """Load download progress from file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {}

    def save_progress(self):
        """Save download progress to file"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    async def download_symbol_data(self, symbol: str,
                                   start_date: datetime,
                                   end_date: datetime,
                                   interval: str = '1h') -> pd.DataFrame:
        """
        Download historical OHLCV data for a single symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            start_date: Start date for data collection
            end_date: End date for data collection
            interval: Kline interval (default: 1h)

        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Downloading {symbol} data from {start_date} to {end_date}")

        all_data = []
        current_start = start_date

        # Binance API limit: 1000 candles per request
        # For 1h interval: 1000 hours ≈ 41 days per request
        interval_mapping = {
            '1m': timedelta(minutes=1000),
            '5m': timedelta(minutes=5000),
            '15m': timedelta(minutes=15000),
            '1h': timedelta(hours=1000),
            '4h': timedelta(hours=4000),
            '1d': timedelta(days=1000)
        }

        chunk_size = interval_mapping.get(interval, timedelta(hours=1000))

        while current_start < end_date:
            current_end = min(current_start + chunk_size, end_date)

            try:
                # Convert datetime to milliseconds timestamp
                start_ms = int(current_start.timestamp() * 1000)
                end_ms = int(current_end.timestamp() * 1000)

                # Get klines from Binance
                klines = await self.client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=start_ms,
                    end_time=end_ms,
                    limit=1000
                )

                if not klines:
                    logger.warning(f"No data returned for {symbol} from {current_start} to {current_end}")
                    break

                # Convert to DataFrame
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades',
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])

                # Convert types
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)

                all_data.append(df)

                # Update progress
                self.progress[symbol] = {
                    'last_timestamp': str(current_end),
                    'rows_collected': len(all_data) * len(df)
                }
                self.save_progress()

                logger.info(f"{symbol}: Downloaded {len(df)} rows up to {current_end}")

                # Move to next chunk
                current_start = current_end

                # Rate limiting: wait 100ms between requests
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error downloading {symbol} data: {e}")
                # Save partial results
                if all_data:
                    break
                raise

        if not all_data:
            return pd.DataFrame()

        # Combine all chunks
        result = pd.concat(all_data, ignore_index=True)
        result = result.drop_duplicates(subset=['timestamp'])
        result = result.sort_values('timestamp')

        logger.info(f"{symbol}: Total {len(result)} rows collected")
        return result

    async def download_all_symbols(self, months: int = 10,
                                   interval: str = '1h',
                                   resume: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Download historical data for all symbols

        Args:
            months: Number of months of historical data to download
            interval: Kline interval (default: 1h)
            resume: Resume from last progress if True

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        logger.info(f"Starting data collection for {len(self.symbols)} symbols")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Interval: {interval}")

        results = {}

        for i, symbol in enumerate(self.symbols, 1):
            try:
                # Check if we should resume
                symbol_start = start_date
                if resume and symbol in self.progress:
                    last_timestamp = datetime.fromisoformat(self.progress[symbol]['last_timestamp'])
                    if last_timestamp > start_date:
                        symbol_start = last_timestamp
                        logger.info(f"Resuming {symbol} from {symbol_start}")

                # Download data
                df = await self.download_symbol_data(
                    symbol=symbol,
                    start_date=symbol_start,
                    end_date=end_date,
                    interval=interval
                )

                if not df.empty:
                    # Save to CSV
                    csv_path = self.data_dir / f"{symbol}_{interval}_{months}months.csv"
                    df.to_csv(csv_path, index=False)
                    logger.info(f"{symbol}: Saved to {csv_path}")

                    # Save to parquet for faster loading
                    parquet_path = self.data_dir / f"{symbol}_{interval}_{months}months.parquet"
                    df.to_parquet(parquet_path, index=False)
                    logger.info(f"{symbol}: Saved to {parquet_path}")

                    results[symbol] = df

                    # Summary statistics
                    logger.info(f"{symbol} Summary:")
                    logger.info(f"  Rows: {len(df)}")
                    logger.info(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
                    logger.info(f"  Price range: {df['close'].min():.2f} - {df['close'].max():.2f}")
                else:
                    logger.warning(f"{symbol}: No data collected")

                # Progress report
                logger.info(f"Progress: {i}/{len(self.symbols)} symbols completed")

            except Exception as e:
                logger.error(f"Failed to download {symbol}: {e}")
                continue

        logger.info(f"Data collection complete: {len(results)}/{len(self.symbols)} symbols successful")
        return results

    def load_symbol_data(self, symbol: str, interval: str = '1h',
                        months: int = 10, format: str = 'parquet') -> pd.DataFrame:
        """
        Load previously downloaded data from disk

        Args:
            symbol: Trading pair symbol
            interval: Kline interval
            months: Number of months
            format: 'csv' or 'parquet' (default: parquet for speed)

        Returns:
            DataFrame with OHLCV data
        """
        if format == 'parquet':
            file_path = self.data_dir / f"{symbol}_{interval}_{months}months.parquet"
            return pd.read_parquet(file_path)
        else:
            file_path = self.data_dir / f"{symbol}_{interval}_{months}months.csv"
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df

    def get_available_data(self) -> List[Dict]:
        """
        Get list of available downloaded data files

        Returns:
            List of dictionaries with file info
        """
        available = []
        for file_path in self.data_dir.glob("*.parquet"):
            parts = file_path.stem.split('_')
            if len(parts) >= 3:
                available.append({
                    'symbol': parts[0],
                    'interval': parts[1],
                    'period': parts[2],
                    'file_path': str(file_path),
                    'format': 'parquet',
                    'size_mb': file_path.stat().st_size / (1024 * 1024)
                })
        return available


async def main():
    """Main function to run data collection"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    testnet = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'

    collector = DataCollector(api_key, api_secret, testnet)

    # Download 10 months of hourly data
    logger.info("=" * 60)
    logger.info("TradingBot V2 - Historical Data Collection")
    logger.info("=" * 60)

    results = await collector.download_all_symbols(
        months=10,
        interval='1h',
        resume=True
    )

    # Display summary
    logger.info("\n" + "=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info("=" * 60)

    total_rows = 0
    total_size = 0

    for symbol, df in results.items():
        size_mb = len(df) * 40 / (1024 * 1024)  # Rough estimate
        total_rows += len(df)
        total_size += size_mb

        logger.info(f"{symbol:12s}: {len(df):8,d} rows, ~{size_mb:.2f} MB")

    logger.info("-" * 60)
    logger.info(f"{'TOTAL':12s}: {total_rows:8,d} rows, ~{total_size:.2f} MB")
    logger.info("=" * 60)

    # Show available data
    available = collector.get_available_data()
    logger.info(f"\nAvailable data files: {len(available)}")
    for data_info in available:
        logger.info(f"  {data_info['symbol']:12s} | {data_info['interval']:4s} | {data_info['size_mb']:.2f} MB")


if __name__ == "__main__":
    asyncio.run(main())
