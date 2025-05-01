import logging
import os

# Define log file paths
LOG_DIR = os.path.join(os.path.dirname(__file__), '../../logs')
os.makedirs(LOG_DIR, exist_ok=True)
INFO_LOG_FILE = os.path.join(LOG_DIR, 'rooBroker.log')
DEBUG_LOG_FILE = os.path.join(LOG_DIR, 'rooBroker_debug.log')

# Create a logger
logger = logging.getLogger('rooBroker')
logger.setLevel(logging.DEBUG)

# Create file handlers
info_handler = logging.FileHandler(INFO_LOG_FILE)
info_handler.setLevel(logging.INFO)

debug_handler = logging.FileHandler(DEBUG_LOG_FILE)
debug_handler.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)

# Define a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
info_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(info_handler)
logger.addHandler(debug_handler)
logger.addHandler(console_handler)
