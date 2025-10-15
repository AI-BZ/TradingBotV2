#!/bin/bash

# Frontend Deployment Script for TradingBot V2
# Run this script on the Vultr server (167.179.108.246)

set -e

echo "=========================================="
echo "TradingBot V2 Frontend Deployment"
echo "=========================================="

# Navigate to project directory
cd /opt/tradingbot-v2

# Pull latest code
echo "Pulling latest code from GitHub..."
git pull origin master

# Install Node.js if not installed
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    apt-get install -y nodejs
fi

# Build frontend
echo "Building frontend..."
cd frontend
npm install
npm run build

# Create web directory
echo "Setting up web directory..."
mkdir -p /var/www/tradingbot
rm -rf /var/www/tradingbot/*
cp -r build/* /var/www/tradingbot/

# Create Nginx configuration
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/tradingbot << 'NGINX_CONFIG'
server {
    listen 80;
    server_name 167.179.108.246;

    # Frontend - React Dashboard
    location / {
        root /var/www/tradingbot;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Health endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # API docs
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://localhost:8000/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
NGINX_CONFIG

# Enable site and reload Nginx
ln -sf /etc/nginx/sites-available/tradingbot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Dashboard URL: http://167.179.108.246"
echo "API Docs: http://167.179.108.246/docs"
echo "Health Check: http://167.179.108.246/health"
echo ""
echo "Please verify the backend is running:"
echo "systemctl status tradingbot"
