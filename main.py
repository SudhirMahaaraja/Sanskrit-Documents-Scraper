import subprocess
import sys
import os
import logging

# Configure logging for main.py
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the base directory of your project
# This assumes main.py is in the same directory as crawler.py, metadata.py, etc.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Define the paths to your scripts
CRAWLER_SCRIPT = os.path.join(PROJECT_ROOT, "crawler.py")
METADATA_SCRIPT = os.path.join(PROJECT_ROOT, "metadata.py")
EXTRACTOR_SCRIPT = os.path.join(PROJECT_ROOT, "extractor.py")
DELTA_SCRIPT = os.path.join(PROJECT_ROOT, "delta.py")

def run_script(script_path, script_name):
    """
    Runs a Python script using subprocess.
    Args:
        script_path (str): The full path to the Python script.
        script_name (str): A user-friendly name for the script (for logging).
    Returns:
        bool: True if the script ran successfully, False otherwise.
    """
    logger.info(f"--- Starting {script_name} ---")
    try:
        # Use sys.executable to ensure the script runs with the same Python interpreter
        # that is running main.py (important for virtual environments).
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True, # Capture output as text (decoded)
            check=False # Do not raise CalledProcessError for non-zero exit codes
        )

        if result.returncode == 0:
            logger.info(f"--- {script_name} completed successfully ---")
            if result.stdout:
                logger.info(f"{script_name} Output:\n{result.stdout}")
        else:
            logger.error(f"--- {script_name} FAILED with exit code {result.returncode} ---")
            if result.stdout:
                logger.error(f"{script_name} Standard Output:\n{result.stdout}")
            if result.stderr:
                logger.error(f"{script_name} Standard Error:\n{result.stderr}")
            return False
        return True
    except FileNotFoundError:
        logger.error(f"Error: {script_name} not found at {script_path}. Please ensure the path is correct.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while running {script_name}: {e}")
        return False

def main():
    """
    Main function to orchestrate the execution of all scripts.
    """
    logger.info("Starting the full Sanskrit Documents Scraper workflow...")

    # Step 1: Run the Crawler
    if not run_script(CRAWLER_SCRIPT, "Crawler"):
        logger.error("Crawler failed. Aborting workflow.")
        sys.exit(1) # Exit if crawler fails, as subsequent steps depend on it

    # Step 2: Run the Metadata Extractor
    if not run_script(METADATA_SCRIPT, "Metadata Extractor"):
        logger.error("Metadata Extractor failed. Aborting workflow.")
        sys.exit(1) # Exit if metadata fails, as delta depends on it

    # Step 3: Run the Text Extractor
    # This step is often independent of delta, but crucial for content.
    # We'll let it run even if it fails, but log the error.
    if not run_script(EXTRACTOR_SCRIPT, "Text Extractor"):
        logger.warning("Text Extractor encountered issues, but continuing workflow.")

    # Step 4: Run the Delta Processor
    if not run_script(DELTA_SCRIPT, "Delta Processor"):
        logger.error("Delta Processor failed. Workflow completed with errors.")
    else:
        logger.info("Full Sanskrit Documents Scraper workflow completed successfully.")

if __name__ == "__main__":
    main()
