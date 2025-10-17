#!/bin/bash
#
# Auto Deploy After Optimization - Master Script
# Runs automatically when continuous optimization completes (06:00 KST)
#
# This script:
# 1. Waits for optimization to complete
# 2. Deploys best strategy to backend
# 3. Updates frontend for production
# 4. Restarts services with optimized configuration
#

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "════════════════════════════════════════════════════════════════"
echo "🤖 AUTO DEPLOYMENT SCRIPT - POST OPTIMIZATION"
echo "════════════════════════════════════════════════════════════════"
echo "Current Time: $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "Target Time: 2025-10-17 06:00:00 KST"
echo ""

# Function to check if optimization is complete
check_optimization_complete() {
    if [ -f "claudedocs/continuous_optimization_history.json" ]; then
        # Check if best_version exists in the file
        if grep -q "best_version" claudedocs/continuous_optimization_history.json; then
            return 0
        fi
    fi
    return 1
}

# Function to check if it's past 06:00 KST
check_deadline_passed() {
    CURRENT_HOUR=$(date '+%H')
    if [ $CURRENT_HOUR -ge 6 ]; then
        return 0
    fi
    return 1
}

echo "⏰ Waiting for continuous optimization to complete..."
echo "   Checking every 60 seconds..."
echo ""

# Wait for optimization completion OR deadline
WAIT_COUNT=0
MAX_WAIT=360  # 6 hours max

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if check_optimization_complete; then
        echo "✅ Optimization complete! Starting deployment..."
        break
    fi

    if check_deadline_passed; then
        echo "⏰ Deadline (06:00 KST) reached!"
        if check_optimization_complete; then
            echo "✅ Optimization results found, proceeding with deployment..."
            break
        else
            echo "⚠️  No optimization results yet, waiting 5 more minutes..."
            sleep 300
            if check_optimization_complete; then
                break
            else
                echo "❌ Optimization did not complete. Aborting deployment."
                exit 1
            fi
        fi
    fi

    # Log progress every 10 minutes
    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "   Still waiting... ($(date '+%H:%M:%S'))"
    fi

    sleep 60
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "❌ Timeout waiting for optimization to complete"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📦 STEP 1: DEPLOY OPTIMIZED STRATEGY"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Activate virtual environment
source venv/bin/activate

# Deploy optimized strategy
python deploy_optimized_strategy.py
if [ $? -ne 0 ]; then
    echo "❌ Strategy deployment failed!"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🎨 STEP 2: UPDATE FRONTEND FOR PRODUCTION"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Update frontend
python update_frontend_for_production.py
if [ $? -ne 0 ]; then
    echo "❌ Frontend update failed!"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🔄 STEP 3: RESTART BACKEND WITH OPTIMIZED STRATEGY"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Kill existing main.py processes
echo "🛑 Stopping existing backend processes..."
pkill -f "python main.py" || true
sleep 2

# Start new backend with optimized strategy
echo "🚀 Starting backend with optimized strategy..."
nohup python main.py > production_backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"
sleep 5

# Verify backend is running
if ps -p $BACKEND_PID > /dev/null; then
    echo "✅ Backend started successfully"
else
    echo "❌ Backend failed to start"
    cat production_backend.log
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 System Status:"
echo "   - Backend: Running (PID: $BACKEND_PID)"
echo "   - Strategy: Optimized version deployed"
echo "   - Frontend: Connected to real-time data"
echo "   - Mode: Paper trading (testnet)"
echo ""
echo "🌐 Access Points:"
echo "   - Dashboard: http://167.179.108.246:5173"
echo "   - API: http://167.179.108.246:8000"
echo "   - Performance: http://167.179.108.246:8000/api/v1/trading/performance"
echo ""
echo "📋 Next Steps:"
echo "   1. Monitor real-time dashboard for 1-2 hours"
echo "   2. Check logs: tail -f production_backend.log"
echo "   3. Verify all metrics update correctly"
echo "   4. If stable, consider production deployment"
echo ""
echo "📄 Deployment Reports:"
echo "   - Strategy: claudedocs/deployment_v*.md"
echo "   - Frontend: claudedocs/frontend_deployment_summary.md"
echo "   - Optimization: claudedocs/continuous_optimization_history.json"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🎉 READY FOR PRODUCTION MONITORING!"
echo "════════════════════════════════════════════════════════════════"
