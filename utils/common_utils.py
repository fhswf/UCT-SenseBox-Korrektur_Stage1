import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import os
from pathlib import Path

def setup_logger(logfile : str, logname : str = None, level: int = 10, use_email: bool = False):
    """
    Logger initialisieren und konfigurieren.

    Args:
        logfile (str): Pfad zur Logdatei.
        logname (str): Name des Loggers.
        level (int): Logging-Level (z.B. logging.DEBUG (10), logging.INFO (20)). Standard ist 10.
    """
    logger = logging.getLogger(logname)
    logger.setLevel(level)

    # Ensure log directory exists
    log_path = Path(logfile)
    if log_path.parent and not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing handlers to avoid duplicate logs on repeated setup
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    handlers = [
        TimedRotatingFileHandler(logfile, when="midnight", interval=1, backupCount=365, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]

    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False

    sys.excepthook = log_exception
    return logger

def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Let Ctrl+C interrupts pass through
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))