import logging
import sys
from app.core.config import settings


def setup_logging():
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Quiet noisy libs
    for lib in ("httpx", "httpcore", "boto3", "botocore", "urllib3", "s3transfer"):
        logging.getLogger(lib).setLevel(logging.WARNING)
