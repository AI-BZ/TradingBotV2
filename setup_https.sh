#!/bin/bash
# Setup HTTPS with Let's Encrypt for TradingBot V2

set -e

echo "=========================================="
echo "Setting up HTTPS with Let's Encrypt"
echo "=========================================="

# Install certbot
echo "Installing certbot..."
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Stop nginx temporarily
echo "Stopping nginx temporarily..."
systemctl stop nginx

# Obtain SSL certificate
echo "Obtaining SSL certificate..."
certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email admin@tradingbot.com \
  -d 167.179.108.246

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

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/167.179.108.246/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/167.179.108.246/privkey.pem;

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

# Start nginx
echo "Starting nginx..."
systemctl start nginx

# Set up auto-renewal
echo "Setting up SSL certificate auto-renewal..."
systemctl enable certbot.timer
systemctl start certbot.timer

echo "=========================================="
echo "HTTPS Setup Complete!"
echo "=========================================="
echo ""
echo "Dashboard URL: https://167.179.108.246"
echo "API Docs: https://167.179.108.246/docs"
echo "Health Check: https://167.179.108.246/health"
echo ""
echo "SSL certificate will auto-renew every 60 days"
echo ""
echo "To check certificate status:"
echo "  certbot certificates"
echo ""
echo "To manually renew certificate:"
echo "  certbot renew"
