import sys
import logging
from fluid_voice.app import FluidVoiceApp

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    setup_logging()
    app = FluidVoiceApp(sys.argv)
    sys.exit(app.run())

if __name__ == "__main__":
    main()
