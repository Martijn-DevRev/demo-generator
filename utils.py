"""
Common utilities used across the application
"""
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

def save_payload_to_file(json_payload, object_payload, session_path=None):
    """
    Save JSON payload to file in session directory or default directory
    Args:
        json_payload: The JSON data to save
        object_payload: The type of payload (e.g., 'tickets', 'issues', 'devusers')
        session_path: Path to session directory
    """
    try:
        if session_path:
            # Determine appropriate subdirectory based on file type
            if any(suffix in object_payload for suffix in ['_responses', '_processed', '_existing', '_failed']):
                output_path = Path(session_path) / "output_files"
            else:
                output_path = Path(session_path) / "input_files"
            
            output_file = output_path / f"{object_payload}.json"
            logger.info(f"Saving to session directory: {output_file}")
        else:
            # Use default directory as fallback
            if any(suffix in object_payload for suffix in ['_responses', '_processed', '_existing', '_failed']):
                output_path = Path("./output_files")
            else:
                output_path = Path("./input_files")
            output_file = output_path / f"{object_payload}.json"
            logger.warning(f"No session path provided, using default directory: {output_file}")

        # Ensure directory exists
        output_path.mkdir(parents=True, exist_ok=True)

        # Save the file
        with open(output_file, 'w') as json_file:
            json.dump(json_payload, json_file, indent=2)

        logger.info(f"Successfully saved {object_payload} with {len(json_payload)} items")
        return output_file

    except Exception as e:
        logger.error(f"Error saving {object_payload} payload to file: {str(e)}")
        raise