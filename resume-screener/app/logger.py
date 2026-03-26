import sys
from pathlib import Path
from loguru import logger

LOG_FILE = Path(__file__).parent.parent / "logs" / "app.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logger.remove()

# Console output
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

# File output - rotate at 5MB, keep last 7 days
logger.add(
    LOG_FILE,
    rotation="5 MB",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)
