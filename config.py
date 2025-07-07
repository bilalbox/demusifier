import logging
import os
from dotenv import load_dotenv

load_dotenv()
VOLUME_DIR = os.getenv("VOLUME_DIR", "/data")
DB_URL = os.path.join(VOLUME_DIR, "demusifier.db")
LOG_PATH = os.path.join(VOLUME_DIR, "app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Define directory structure
BASE_DIR = os.path.join(VOLUME_DIR, "videos")
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
WORKING_DIR = os.path.join(BASE_DIR, "working")

# Replicate API configuration
REPLICATE_API_TOKEN = os.getenv(
    "REPLICATE_API_TOKEN"
)  # Replicate uses REPLICATE_API_TOKEN
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL")

# Ensure directories exist
for dir_path in [INPUT_DIR, OUTPUT_DIR, WORKING_DIR]:
    os.makedirs(dir_path, exist_ok=True)


def setup_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level=LOG_LEVEL)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(filename)s->%(funcName)s():%(lineno)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Add console handler if CONSOLE_LOGGING is set
        if os.getenv("CONSOLE_LOGGING", "").lower() in (
            "1",
            "true",
            "yes",
        ):  # Accept several truthy values
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger
