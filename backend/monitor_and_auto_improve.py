"""
Monitor v5.0 completion and auto-start continuous optimization
This script waits for v5.0 multi-timeframe to complete, then launches continuous optimization
"""
import asyncio
import time
import subprocess
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_v5_completion():
    """Check if v5.0 multi-timeframe backtest is complete"""
    log_file = Path(__file__).parent / 'v5_multi_timeframe_output.log'

    if not log_file.exists():
        return False

    # Read last 50 lines of log
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            last_lines = ''.join(lines[-50:])

            # Check for completion indicators
            if 'v5.0 MULTI-TIMEFRAME VALIDATION PASSED' in last_lines:
                logger.info("✅ v5.0 completed with PASSED status")
                return True
            elif 'v5.0 PARTIAL SUCCESS' in last_lines:
                logger.info("⚠️  v5.0 completed with PARTIAL SUCCESS")
                return True
            elif 'v5.0 NEEDS IMPROVEMENT' in last_lines:
                logger.info("❌ v5.0 completed with NEEDS IMPROVEMENT")
                return True

    except Exception as e:
        logger.error(f"Error checking v5.0 log: {e}")

    return False


async def monitor_and_launch():
    """Monitor v5.0 and launch continuous optimization when ready"""
    logger.info(f"{'='*80}")
    logger.info(f"👀 MONITORING v5.0 MULTI-TIMEFRAME BACKTEST")
    logger.info(f"{'='*80}")
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}")
    logger.info(f"Deadline: 2025-10-17 06:00:00 KST")

    check_interval = 60  # Check every 60 seconds
    max_wait_hours = 3  # Max wait 3 hours

    start_time = time.time()

    while True:
        elapsed_hours = (time.time() - start_time) / 3600

        if elapsed_hours > max_wait_hours:
            logger.warning(f"⏰ Max wait time ({max_wait_hours}h) exceeded")
            logger.warning(f"Starting continuous optimization anyway...")
            break

        # Check if v5.0 is complete
        if await check_v5_completion():
            logger.info(f"✅ v5.0 multi-timeframe backtest complete!")
            logger.info(f"⏰ Elapsed: {elapsed_hours:.1f} hours")
            break

        # Log progress
        if int(elapsed_hours * 60) % 10 == 0:  # Every 10 minutes
            logger.info(f"⏳ Still waiting for v5.0... ({elapsed_hours:.1f}h elapsed)")

        await asyncio.sleep(check_interval)

    # Launch continuous optimization
    logger.info(f"\n{'='*80}")
    logger.info(f"🚀 LAUNCHING CONTINUOUS OPTIMIZATION")
    logger.info(f"{'='*80}")

    # Run continuous optimization in background
    process = subprocess.Popen(
        ['python', 'run_continuous_optimization.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        cwd=Path(__file__).parent
    )

    logger.info(f"✅ Continuous optimization started (PID: {process.pid})")
    logger.info(f"📋 Log file: continuous_optimization.log")

    # Stream output
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 CONTINUOUS OPTIMIZATION OUTPUT")
    logger.info(f"{'='*80}\n")

    for line in iter(process.stdout.readline, ''):
        if line:
            print(line, end='')

    process.wait()
    logger.info(f"\n✅ Continuous optimization complete!")
    logger.info(f"📋 Check claudedocs/continuous_optimization_history.json for results")


if __name__ == "__main__":
    asyncio.run(monitor_and_launch())
