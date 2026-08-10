import functools
import logging
import os
import time
from datetime import datetime

# 1. Configure the Global Logger
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"mindpalace_{datetime.now().strftime('%Y-%m-%d')}.log")

# Setup a rotating format (writes to file and terminal simultaneously)
logger = logging.getLogger("MindPalaceOS")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) # Keep console cleaner

formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 2. Create the Future-Proof Decorator
def audit_log(func):
    """
    A decorator that automatically logs the execution of a function.
    It records the function name, arguments, execution time, and any errors.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Format arguments nicely, ignoring 'self' for cleaner logs
        args_repr = [repr(a) for a in args if not str(a).startswith('<')]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)

        logger.debug(f"Executing: {func.__name__}({signature})")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            run_time = time.time() - start_time
            logger.debug(f"Completed: {func.__name__} in {run_time:.4f}s")
            return result
        except Exception as e:
            run_time = time.time() - start_time
            logger.error(f"CRASH in {func.__name__}: {e!s} (Failed after {run_time:.4f}s)", exc_info=True)
            raise # Re-raise the exception after logging it

    return wrapper
