# 🚀 TradingBot V2 - Vultr 수동 배포 가이드

**서버 정보**:
- IP: 167.179.108.246
- Vultr API Key: D6EGT3LPYGJGHGKVBGILSU3KBAN7DY4MSHYQ

---

## 1️⃣ 서버 접속

```bash
# SSH로 서버 접속 (비밀번호 입력 필요)
ssh root@167.179.108.246
```

---

## 2️⃣ V1 완전 삭제

```bash
# 실행 중인 프로세스 종료
pkill -f "rails" || true
pkill -f "puma" || true
pkill -f "ruby" || true
pkill -f "python" || true

# Docker 정리 (있다면)
docker ps -q | xargs -r docker stop
docker ps -aq | xargs -r docker rm

# V1 디렉토리 삭제
rm -rf /root/trading_bot
rm -rf /opt/trading_bot

# Systemd 서비스 정리
systemctl stop tradingbot 2>/dev/null || true
systemctl disable tradingbot 2>/dev/null || true
rm -f /etc/systemd/system/tradingbot.service

echo "✅ V1 완전 삭제 완료"
```

---

## 3️⃣ 시스템 업데이트 및 의존성 설치

```bash
# 시스템 업데이트
apt-get update
apt-get upgrade -y

# Python 3.11 설치
apt-get install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev

# 빌드 도구 설치
apt-get install -y build-essential wget git nginx

# TA-Lib 설치 (기술적 지표 라이브러리)
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
make install
ldconfig

echo "✅ 시스템 설정 완료"
```

---

## 4️⃣ TradingBot V2 클론

```bash
# 배포 디렉토리 생성
mkdir -p /opt
cd /opt

# GitHub에서 클론
git clone https://github.com/AI-BZ/TradingBotV2.git tradingbot-v2
cd tradingbot-v2

echo "✅ 코드 다운로드 완료"
```

---

## 5️⃣ Python 환경 설정

```bash
cd /opt/tradingbot-v2/backend

# 가상 환경 생성
python3.11 -m venv venv

# 가상 환경 활성화
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip

# 의존성 설치 (5-10분 소요)
pip install -r requirements.txt

echo "✅ Python 환경 완료"
```

---

## 6️⃣ 환경 변수 설정

```bash
cd /opt/tradingbot-v2

# .env 파일 생성
cat > .env << 'EOF'
# Binance API Configuration
BINANCE_API_KEY=hj8K4K64Vt38O339jwbo6cWoL7PZwhVxj5WL2mfbkU50ortBv7MxCnL0pvQSZ6BV
BINANCE_API_SECRET=<YOUR_SECRET_KEY_HERE>
BINANCE_TESTNET=true

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=tradingbot_v2
POSTGRES_USER=tradingbot
POSTGRES_PASSWORD=tradingbot_password

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

# IMPORTANT: Binance API Secret 추가 필요!
nano .env  # API Secret을 직접 입력하세요

echo "✅ 환경 변수 설정 완료"
```

---

## 7️⃣ Systemd 서비스 생성

```bash
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

# Systemd 리로드
systemctl daemon-reload
systemctl enable tradingbot

echo "✅ Systemd 서비스 생성 완료"
```

---

## 8️⃣ Nginx 리버스 프록시 설정

```bash
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

# 사이트 활성화
ln -sf /etc/nginx/sites-available/tradingbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Nginx 설정 테스트 및 재시작
nginx -t
systemctl restart nginx

echo "✅ Nginx 설정 완료"
```

---

## 9️⃣ 서비스 시작

```bash
# 로그 디렉토리 생성
mkdir -p /opt/tradingbot-v2/logs

# 서비스 시작
systemctl start tradingbot

# 상태 확인
sleep 5
systemctl status tradingbot

# 로그 확인
journalctl -u tradingbot -f --lines=50
```

---

## 🔟 배포 검증

### 로컬에서 테스트:
```bash
# Health check
curl http://167.179.108.246/health

# API 문서 확인
open http://167.179.108.246/docs

# Market 가격 조회
curl "http://167.179.108.246/api/v1/market/prices?symbols=BTCUSDT"
```

### 서버에서 테스트:
```bash
# 서비스 상태
systemctl status tradingbot

# 실시간 로그
journalctl -u tradingbot -f

# 프로세스 확인
ps aux | grep python

# 포트 확인
netstat -tlnp | grep 8000
```

---

## 🛠️ 관리 명령어

### 서비스 제어
```bash
# 시작
systemctl start tradingbot

# 중지
systemctl stop tradingbot

# 재시작
systemctl restart tradingbot

# 상태 확인
systemctl status tradingbot

# 부팅 시 자동 시작 활성화
systemctl enable tradingbot

# 부팅 시 자동 시작 비활성화
systemctl disable tradingbot
```

### 로그 확인
```bash
# 실시간 로그
journalctl -u tradingbot -f

# 최근 100줄
journalctl -u tradingbot -n 100

# 오늘 로그만
journalctl -u tradingbot --since today

# 에러 로그만
journalctl -u tradingbot -p err
```

### 코드 업데이트
```bash
cd /opt/tradingbot-v2
git pull
systemctl restart tradingbot
```

### 성능 모니터링
```bash
# CPU/메모리 사용량
top -p $(pidof python)

# 네트워크 연결
netstat -anp | grep 8000

# 디스크 사용량
df -h
```

---

## 🐛 문제 해결

### 서비스가 시작되지 않을 때
```bash
# 로그 확인
journalctl -u tradingbot -n 100

# 직접 실행해보기
cd /opt/tradingbot-v2/backend
source venv/bin/activate
python main.py
```

### 포트가 이미 사용 중일 때
```bash
# 포트 사용 프로세스 확인
lsof -i :8000

# 프로세스 종료
kill -9 <PID>
```

### Nginx 오류
```bash
# Nginx 설정 테스트
nginx -t

# Nginx 로그 확인
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log
```

### 의존성 오류
```bash
cd /opt/tradingbot-v2/backend
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

---

## 📊 성능 최적화

### 1. Systemd 서비스 최적화
```ini
# /etc/systemd/system/tradingbot.service 수정
[Service]
# 우선순위 높이기
Nice=-10

# 파일 디스크립터 증가
LimitNOFILE=65535

# 메모리 제한 (선택사항)
MemoryLimit=2G
```

### 2. 시스템 파라미터 튜닝
```bash
# /etc/sysctl.conf 편집
cat >> /etc/sysctl.conf << 'EOF'
# Network performance
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 4096
net.core.netdev_max_backlog = 4096
net.ipv4.tcp_tw_reuse = 1
EOF

# 적용
sysctl -p
```

### 3. 로그 로테이션
```bash
cat > /etc/logrotate.d/tradingbot << 'EOF'
/opt/tradingbot-v2/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        systemctl reload tradingbot > /dev/null 2>&1 || true
    endscript
}
EOF
```

---

## ✅ 배포 완료 체크리스트

- [ ] V1 완전 삭제 확인
- [ ] Python 3.11 설치 완료
- [ ] TA-Lib 설치 완료
- [ ] 코드 GitHub에서 클론 완료
- [ ] Python 가상 환경 및 의존성 설치 완료
- [ ] .env 파일 생성 및 API 키 설정 완료
- [ ] Systemd 서비스 생성 및 활성화 완료
- [ ] Nginx 설정 및 재시작 완료
- [ ] 서비스 시작 및 정상 동작 확인
- [ ] Health check API 응답 확인 (http://167.179.108.246/health)
- [ ] API 문서 접근 확인 (http://167.179.108.246/docs)
- [ ] 실시간 로그 확인

---

## 🎯 다음 단계

배포가 완료되면:

1. **Binance API Secret 추가** (.env 파일)
2. **실전 데이터 수집 시작** (자동)
3. **ML 모델 학습** (10개월 과거 데이터)
4. **Paper Trading 시작** (Testnet)
5. **성과 모니터링**

---

**작성**: 2025-10-15
**GitHub**: https://github.com/AI-BZ/TradingBotV2
