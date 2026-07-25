import sys
import logging
from datetime import datetime
from pathlib import Path
from fluid_voice.config import get_app_data_dir
from fluid_voice.app import FluidVoiceApp

def setup_logging():
    """Initializes dual logging to both stdout and persistent session log files on disk."""
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_log_file = log_dir / f"velovoice_session_{timestamp}.log"
    latest_log_file = log_dir / "velovoice_latest.log"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(session_log_file, encoding="utf-8"),
        logging.FileHandler(latest_log_file, mode="w", encoding="utf-8"),
    ]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )

    logger = logging.getLogger("VeloVoice")
    logger.info(f"⚡ VeloVoice logging initialized.")
    logger.info(f"📜 Session Log File: {session_log_file}")
    logger.info(f"📜 Latest Log File: {latest_log_file}")

def main():
    setup_logging()
    app = FluidVoiceApp(sys.argv)
    sys.exit(app.run())

if __name__ == "__main__":
    main()
