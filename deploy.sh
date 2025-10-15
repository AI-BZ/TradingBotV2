#!/bin/bash
# TradingBot V2 Deployment Script for Vultr
# This script cleans V1 and deploys V2 on Vultr server

set -e

echo "🚀 TradingBot V2 Deployment Starting..."
echo "==========================================="

# Server configuration
SERVER="167.179.108.246"
SERVER_USER="root"
DEPLOY_DIR="/opt/tradingbot-v2"
V1_DIR="/root/trading_bot"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "\n${YELLOW}Step 1: Connecting to Vultr server...${NC}"
ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER} "echo 'Connected to Vultr successfully!' && hostname && uptime"

echo -e "\n${YELLOW}Step 2: Stopping and removing V1...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    # Stop any running Rails processes
    echo "Stopping V1 processes..."
    pkill -f "rails" || echo "No Rails processes found"
    pkill -f "puma" || echo "No Puma processes found"
    pkill -f "ruby" || echo "No Ruby processes found"

    # Stop any Docker containers
    if command -v docker &> /dev/null; then
        echo "Stopping Docker containers..."
        docker ps -q | xargs -r docker stop
        docker ps -aq | xargs -r docker rm
    fi

    # Remove V1 directory
    if [ -d "/root/trading_bot" ]; then
        echo "Removing V1 directory..."
        rm -rf /root/trading_bot
        echo "✅ V1 removed"
    else
        echo "V1 directory not found, skipping..."
    fi

    # Clean up old processes
    echo "Cleaning up old processes..."
    systemctl stop tradingbot 2>/dev/null || echo "No systemd service to stop"
    systemctl disable tradingbot 2>/dev/null || echo "No systemd service to disable"

    echo "✅ V1 cleanup complete"
ENDSSH

echo -e "\n${YELLOW}Step 3: Installing system dependencies...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    # Update system
    echo "Updating system packages..."
    apt-get update -qq

    # Install Python 3.11+
    if ! command -v python3.11 &> /dev/null; then
        echo "Installing Python 3.11..."
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq
        apt-get install -y python3.11 python3.11-venv python3.11-dev
    fi

    # Install build dependencies
    echo "Installing build dependencies..."
    apt-get install -y build-essential wget git nginx

    # Install TA-Lib
    if [ ! -f "/usr/local/lib/libta_lib.so" ]; then
        echo "Installing TA-Lib..."
        cd /tmp
        wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
        tar -xzf ta-lib-0.4.0-src.tar.gz
        cd ta-lib/
        ./configure --prefix=/usr
        make
        make install
        ldconfig
        cd ~
        rm -rf /tmp/ta-lib*
        echo "✅ TA-Lib installed"
    else
        echo "TA-Lib already installed"
    fi

    echo "✅ System dependencies installed"
ENDSSH

echo -e "\n${YELLOW}Step 4: Cloning TradingBot V2 from GitHub...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    # Create deployment directory
    mkdir -p /opt
    cd /opt

    # Clone repository
    if [ -d "tradingbot-v2" ]; then
        echo "Repository exists, pulling latest..."
        cd tradingbot-v2
        git pull
    else
        echo "Cloning repository..."
        git clone https://github.com/AI-BZ/TradingBotV2.git tradingbot-v2
    fi

    cd tradingbot-v2
    echo "✅ Code deployed"
ENDSSH

echo -e "\n${YELLOW}Step 5: Setting up Python environment...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    cd /opt/tradingbot-v2/backend

    # Create virtual environment
    echo "Creating Python virtual environment..."
    python3.11 -m venv venv

    # Install dependencies
    echo "Installing Python dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    echo "✅ Python environment ready"
ENDSSH

echo -e "\n${YELLOW}Step 6: Configuring environment variables...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    cd /opt/tradingbot-v2

    # Create .env file
    cat > .env << 'EOF'
# Binance API Configuration
BINANCE_API_KEY=hj8K4K64Vt38O339jwbo6cWoL7PZwhVxj5WL2mfbkU50ortBv7MxCnL0pvQSZ6BV
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=tradingbot_v2
POSTGRES_USER=tradingbot
POSTGRES_PASSWORD=tradingbot_password

# QuestDB Configuration
QUESTDB_HOST=localhost
QUESTDB_HTTP_PORT=9000
QUESTDB_PG_PORT=8812
QUESTDB_INFLUX_PORT=9009

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Trading Configuration
INITIAL_BALANCE=10000
MAX_POSITION_SIZE=0.2
STOP_LOSS_PERCENTAGE=3.0
TAKE_PROFIT_PERCENTAGE=5.0
DAILY_LOSS_LIMIT=10.0
MAX_DRAWDOWN=25.0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=*

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log
EOF

    echo "✅ Environment configured"
ENDSSH

echo -e "\n${YELLOW}Step 7: Creating systemd service...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    cat > /etc/systemd/system/tradingbot.service << 'EOF'
[Unit]
Description=TradingBot V2 - AI-Powered Cryptocurrency Trading System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tradingbot-v2/backend
Environment="PATH=/opt/tradingbot-v2/backend/venv/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/tradingbot-v2/.env
ExecStart=/opt/tradingbot-v2/backend/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security hardening
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    systemctl enable tradingbot

    echo "✅ Systemd service created"
ENDSSH

echo -e "\n${YELLOW}Step 8: Configuring Nginx reverse proxy...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    cat > /etc/nginx/sites-available/tradingbot << 'EOF'
upstream tradingbot_backend {
    server 127.0.0.1:8000;
    keepalive 256;
}

server {
    listen 80;
    server_name 167.179.108.246;

    client_max_body_size 10M;

    location / {
        proxy_pass http://tradingbot_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://tradingbot_backend/health;
        access_log off;
    }

    location /ws/ {
        proxy_pass http://tradingbot_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/tradingbot /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    # Test and reload Nginx
    nginx -t
    systemctl reload nginx

    echo "✅ Nginx configured"
ENDSSH

echo -e "\n${YELLOW}Step 9: Starting TradingBot V2...${NC}"
ssh ${SERVER_USER}@${SERVER} << 'ENDSSH'
    # Create logs directory
    mkdir -p /opt/tradingbot-v2/logs

    # Start service
    systemctl start tradingbot

    # Wait for startup
    echo "Waiting for service to start..."
    sleep 5

    # Check status
    systemctl status tradingbot --no-pager

    echo "✅ TradingBot V2 started"
ENDSSH

echo -e "\n${YELLOW}Step 10: Verifying deployment...${NC}"
sleep 3
curl -s http://167.179.108.246/health | python3 -m json.tool || echo "Waiting for API to be ready..."

echo -e "\n${GREEN}==========================================="
echo -e "🎉 Deployment Complete!"
echo -e "===========================================${NC}"
echo ""
echo "📊 Service Information:"
echo "  API URL: http://167.179.108.246"
echo "  Health: http://167.179.108.246/health"
echo "  Docs: http://167.179.108.246/docs"
echo ""
echo "🔧 Management Commands:"
echo "  Status:  ssh root@167.179.108.246 'systemctl status tradingbot'"
echo "  Logs:    ssh root@167.179.108.246 'journalctl -u tradingbot -f'"
echo "  Restart: ssh root@167.179.108.246 'systemctl restart tradingbot'"
echo "  Stop:    ssh root@167.179.108.246 'systemctl stop tradingbot'"
echo ""
echo "📁 Deployment Location: /opt/tradingbot-v2"
echo ""
echo "✅ TradingBot V2 is now live!"
