import logging
import os
import sys
from datetime import datetime

def setup_logger():
    """Tworzy logger zapisujący do pliku"""
    
    # Ścieżka do logów
    if sys.platform == "darwin":
        log_dir = os.path.expanduser("~/Library/Logs/TrainTrack")
    else:
        log_dir = os.path.expanduser("~/.traintrack/logs")
    
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"traintrack_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('TrainTrack')

logger = setup_logger()