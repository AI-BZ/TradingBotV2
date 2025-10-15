# React Dashboard Deployment Guide

## Current Status
✅ Frontend built successfully (180.65 kB main.js, 2.02 kB CSS)
✅ Code committed to GitHub
✅ Deployment script created

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

SSH to your server and run the deployment script:

```bash
# SSH to server
ssh root@167.179.108.246

# Navigate to project directory
cd /opt/tradingbot-v2

# Pull latest code (includes deployment script)
git pull origin master

# Run deployment script
bash deploy_frontend.sh
```

The script will automatically:
1. Install Node.js (if not installed)
2. Build the React frontend
3. Copy files to `/var/www/tradingbot`
4. Configure Nginx
5. Reload Nginx

### Option 2: Manual Deployment

If you prefer manual steps:

```bash
# SSH to server
ssh root@167.179.108.246

# Install Node.js (if not installed)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
apt-get install -y nodejs

# Navigate to project and pull code
cd /opt/tradingbot-v2
git pull origin master

# Build frontend
cd frontend
npm install
npm run build

# Create web directory and copy files
mkdir -p /var/www/tradingbot
rm -rf /var/www/tradingbot/*
cp -r build/* /var/www/tradingbot/

# Configure Nginx (see Nginx configuration below)
nano /etc/nginx/sites-available/tradingbot

# Enable site and reload
ln -sf /etc/nginx/sites-available/tradingbot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### Nginx Configuration

Create `/etc/nginx/sites-available/tradingbot`:

```nginx
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
```

## Verification

After deployment, verify the dashboard is working:

```bash
# Check Nginx status
systemctl status nginx

# Check backend is running
systemctl status tradingbot

# Test dashboard (should return HTML)
curl http://167.179.108.246/

# Test API (should return JSON)
curl http://167.179.108.246/health
curl http://167.179.108.246/api/v1/market/prices?symbols=BTCUSDT
```

## Access URLs

After successful deployment:

- **Dashboard**: http://167.179.108.246
- **API Documentation**: http://167.179.108.246/docs
- **Health Check**: http://167.179.108.246/health

## Dashboard Features

The React dashboard includes:

### Real-time Monitoring
- Live price updates every 5 seconds
- BTC, ETH, BNB, SOL price cards
- 24-hour change percentages
- Color-coded trends (green/red)

### System Status
- API health status
- WebSocket connection status
- System uptime

### Interactive Charts
- Symbol selector (BTC/ETH/BNB/SOL)
- Interval selector (1m/5m/15m/1h/4h/1d)
- Real-time price visualization
- Powered by Recharts

### Performance Metrics
- Win Rate with progress bar
- Profit Factor
- Sharpe Ratio
- Max Drawdown
- Total/Winning/Losing trades
- Average Win/Loss amounts

### Trade History
- Recent trades table
- Entry/Exit prices
- P&L with percentage
- Trade duration
- Exit reason (Take Profit/Stop Loss/Signal)
- Timestamp

### Design
- Dark theme (#0a0a0a background)
- Responsive layout (desktop/tablet/mobile)
- Hover effects and transitions
- Professional gradient UI

## Troubleshooting

### Dashboard not loading
```bash
# Check Nginx configuration
nginx -t

# Check Nginx logs
tail -f /var/log/nginx/error.log

# Verify files exist
ls -la /var/www/tradingbot/
```

### API calls failing
```bash
# Check backend is running
systemctl status tradingbot

# Check backend logs
tail -f /opt/tradingbot-v2/logs/app.log

# Test API directly
curl http://localhost:8000/health
```

### Port conflicts
```bash
# Check what's using port 80
lsof -i :80

# Check what's using port 8000
lsof -i :8000
```

### Rebuild frontend
```bash
cd /opt/tradingbot-v2/frontend
npm run build
rm -rf /var/www/tradingbot/*
cp -r build/* /var/www/tradingbot/
```

## Tech Stack

- **Frontend**: React 18 + TypeScript
- **Data Fetching**: @tanstack/react-query (5-second polling)
- **Charts**: Recharts
- **HTTP Client**: Axios
- **Icons**: Lucide-react
- **Styling**: CSS (dark theme)
- **Web Server**: Nginx (reverse proxy)
- **Backend**: FastAPI (port 8000)

## Development Workflow

To modify the dashboard:

1. Make changes locally in `/frontend/src`
2. Test locally: `npm start`
3. Build: `npm run build`
4. Commit to GitHub
5. SSH to server and run `bash deploy_frontend.sh`

## Performance

Build output:
- Main JS: 180.65 kB (gzipped)
- Main CSS: 2.02 kB (gzipped)
- Total: ~183 kB

Auto-refresh interval: 5 seconds
Charts render: Real-time with smooth animations
Responsive: Mobile-first design

## Security Notes

- Dashboard is currently HTTP only (no HTTPS)
- No authentication implemented
- API is publicly accessible
- Consider adding:
  - HTTPS with Let's Encrypt
  - Authentication/Authorization
  - Rate limiting
  - CORS configuration
  - API key protection

## Next Steps

Potential improvements:
1. Add HTTPS (Let's Encrypt)
2. Implement authentication
3. Add WebSocket for real-time updates
4. Create admin panel
5. Add more chart types
6. Implement trade execution from UI
7. Add alert notifications
8. Create mobile app version
