import logging
from datetime import datetime

def setup_logger(name='app'):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f'logs/{name}-{timestamp}.log'

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_filename, mode='w')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
