#!/bin/bash
# Setup HTTPS with Self-Signed Certificate for TradingBot V2
# Use this for IP address (Let's Encrypt requires domain name)

set -e

echo "=========================================="
echo "Setting up HTTPS with Self-Signed Certificate"
echo "=========================================="

# Create directory for SSL certificates
mkdir -p /etc/ssl/tradingbot

# Generate self-signed certificate (valid for 365 days)
echo "Generating self-signed SSL certificate..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/tradingbot/privkey.pem \
  -out /etc/ssl/tradingbot/fullchain.pem \
  -subj "/C=US/ST=State/L=City/O=TradingBot/CN=167.179.108.246"

# Backup current nginx config
echo "Backing up current nginx configuration..."
cp /etc/nginx/sites-available/tradingbot /etc/nginx/sites-available/tradingbot.backup

# Create new HTTPS-enabled nginx config
echo "Creating HTTPS-enabled nginx configuration..."
cat > /etc/nginx/sites-available/tradingbot << 'EOF'
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name 167.179.108.246;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name 167.179.108.246;

    # Self-signed SSL certificate
    ssl_certificate /etc/ssl/tradingbot/fullchain.pem;
    ssl_certificate_key /etc/ssl/tradingbot/privkey.pem;

    # SSL security settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

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
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API docs
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /openapi.json {
        proxy_pass http://localhost:8000/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Test nginx configuration
echo "Testing nginx configuration..."
nginx -t

# Restart nginx
echo "Restarting nginx..."
systemctl restart nginx

echo "=========================================="
echo "HTTPS Setup Complete!"
echo "=========================================="
echo ""
echo "Dashboard URL: https://167.179.108.246"
echo "API Docs: https://167.179.108.246/docs"
echo "Health Check: https://167.179.108.246/health"
echo ""
echo "⚠️  NOTE: Self-signed certificate in use"
echo "Your browser will show a security warning."
echo "Click 'Advanced' and 'Proceed anyway' to access."
echo ""
echo "To use a trusted certificate, you need:"
echo "1. A domain name (not an IP address)"
echo "2. Then run setup_https.sh with Let's Encrypt"
