#!/bin/bash
# TradingBot V2 Setup Script
# Automated environment setup and initialization

set -e

echo "🚀 TradingBot V2 Setup Starting..."
echo "=================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -e "\n${YELLOW}Checking Python version...${NC}"
python3 --version

# Create virtual environment
echo -e "\n${YELLOW}Creating Python virtual environment...${NC}"
cd backend
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo -e "\n${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install Python dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt

echo -e "\n${GREEN}✅ Python environment setup complete!${NC}"

# Create .env file from example
echo -e "\n${YELLOW}Setting up environment variables...${NC}"
cd ..
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env file (please configure your API keys)${NC}"
else
    echo -e "${YELLOW}⚠️  .env file already exists, skipping...${NC}"
fi

# Check Docker
echo -e "\n${YELLOW}Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker is installed${NC}"
    docker --version
else
    echo -e "${YELLOW}⚠️  Docker not found. Please install Docker Desktop.${NC}"
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose is installed${NC}"
    docker-compose --version
else
    echo -e "${YELLOW}⚠️  Docker Compose not found.${NC}"
fi

# Create data directories
echo -e "\n${YELLOW}Creating data directories...${NC}"
mkdir -p data/historical
mkdir -p data/backtest
mkdir -p logs

echo -e "\n${GREEN}✅ Data directories created${NC}"

# Final instructions
echo -e "\n=================================="
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Configure your API keys in .env file"
echo "2. Start services: docker-compose up -d"
echo "3. Run backend: cd backend && source venv/bin/activate && python main.py"
echo "4. Visit: http://localhost:8000"
echo ""
echo -e "${YELLOW}For development:${NC}"
echo "cd backend && source venv/bin/activate"
echo "python binance_client.py  # Test Binance connection"
echo "python technical_indicators.py  # Test indicators"
echo "python backtest_engine.py  # Test backtesting"
echo ""
