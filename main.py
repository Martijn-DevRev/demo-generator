from flask import Flask, render_template, jsonify, request, session, send_file
import os
from dotenv import load_dotenv
import uuid
import threading
from functools import wraps
import time
import json
from pathlib import Path
import logging
import zipfile
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import existing script functionality
from create_org import main as create_org_main
from devrev_objects import clean_org

# Configuration
DEVREV_BASE_URL = "https://api.devrev.ai/internal/"

# Disable Werkzeug logging
logging.getLogger('werkzeug').setLevel(logging.INFO)
from werkzeug.serving import WSGIRequestHandler
WSGIRequestHandler.log = lambda self, _args, *kwargs: None

# Store running tasks and their status
tasks = {}

class TaskStatus:
    def __init__(self):
        self.progress = 0
        self.status = "Initializing..."
        self.complete = False
        self.error = None
        self.session_dir = None
        self.last_update = time.time()

    def update(self, status, progress):
        self.status = status
        self.progress = progress
        self.last_update = time.time()

def create_session_directories(session_id):
    """Create session-specific directories for input/output files"""
    base_path = Path("sessions") / session_id
    input_path = base_path / "input_files"
    output_path = base_path / "output_files"
    input_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    return base_path

def cleanup_session_files(session_id):
    """Clean up session-specific files after completion"""
    import shutil
    session_path = Path("sessions") / session_id
    if session_path.exists():
        shutil.rmtree(session_path)

def requires_auth(f):
    """Decorator to check if DevOrg PAT is provided and valid"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_data = request.get_json()
        if not auth_data or 'devorgPat' not in auth_data:
            logger.warning("Missing PAT in request")
            return jsonify({'error': 'DevOrg PAT is required'}), 400
        
        pat = auth_data['devorgPat']
        if not pat.startswith('ey'): # DevRev PATs start with 'ey'
            logger.warning("Invalid PAT format")
            return jsonify({'error': 'Invalid PAT format. DevRev PAT should start with "ey"'}), 400
            
        return f(*args, **kwargs)
    return decorated

app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET', 'your-secret-key')

@app.route('/')
def index():
    """Serve the main application page"""
    logger.debug("Serving index page")
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
@requires_auth
def generate():
    """Handle content generation request"""
    try:
        data = request.get_json()
        logger.info("Received generate request with settings: %s",
            {k: v for k, v in data.get('settings', {}).items()})

        session_id = str(uuid.uuid4())
        logger.debug("Created session ID: %s", session_id)

        # Create task status object
        task_status = TaskStatus()
        tasks[session_id] = task_status

        def run_generation():
            logger.debug("Starting generation thread")
            try:
                # Update status
                task_status.status = "Starting content generation..."
                task_status.progress = 5
                logger.debug("Updated initial status")

                # Create session directory and store path
                task_status.session_dir = create_session_directories(session_id)
                logger.info(f"Created session directory: {task_status.session_dir}")

                # Prepare arguments for create_org_main
                args = type('Args', (), {
                    'pat': data['devorgPat'],
                    'company_url': data['websiteUrl'],
                    'support_url': data.get('knowledgebaseUrl', ''),
                    'max_tickets': data.get('numArticles', 0),
                    'max_issues': data.get('numIssues', 0),
                    'settings': data.get('settings', {})
                })
                logger.info("Created args object with settings: %s",
                    {k: v for k, v in data.get('settings', {}).items()})

                # Run the main function with progress callback
                def progress_callback(status, progress):
                    logger.debug("Progress callback: %s - %s", status, progress)
                    task_status.update(status, progress)

                logger.debug("Starting create_org_main")
                create_org_main(args, task_status.session_dir, progress_callback)
                logger.debug("Finished create_org_main")

                # Update completion status
                task_status.progress = 100
                task_status.status = "Content generation completed successfully"
                task_status.complete = True

                # Add console completion message
                print("\n========================================")
                print("✅ Content generation process completed successfully!")
                print("========================================")
                logger.debug("Task completed successfully")

            except Exception as e:
                logger.error("Error in generation thread: %s", str(e), exc_info=True)
                task_status.error = str(e)
                task_status.status = f"Error: {str(e)}"
                # Add console error message
                print("\n========================================")
                print("❌ Error in content generation process:")
                print(f" {str(e)}")
                print("========================================")
            finally:
                # Cleanup session files after delay
                logger.debug("Scheduling cleanup for session: %s", session_id)
                threading.Timer(3600, cleanup_session_files, args=[session_id]).start()

        # Start generation in background
        logger.debug("Starting background thread")
        thread = threading.Thread(target=run_generation)
        thread.daemon = True
        thread.start()
        logger.debug("Background thread started")

        return jsonify({
            'sessionId': session_id,
            'message': 'Content generation started'
        })

    except Exception as e:
        logger.error("Error in generate endpoint: %s", str(e), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
@requires_auth
def cleanup():
    """Handle cleanup request"""
    try:
        data = request.get_json()
        logger.debug("Received cleanup request")
        session_id = str(uuid.uuid4())

        # Create task status object
        task_status = TaskStatus()
        tasks[session_id] = task_status

        def run_cleanup():
            logger.debug("Starting cleanup thread")
            try:
                # Create session directory and store path
                task_status.session_dir = create_session_directories(session_id)
                logger.info(f"Created session directory: {task_status.session_dir}")

                task_status.status = "Starting cleanup..."
                task_status.progress = 10

                clean_org(
                    data['devorgPat'],
                    base_url=DEVREV_BASE_URL,
                    session_path=task_status.session_dir,
                    progress_callback=lambda status, prog: task_status.update(status, prog)
                )

                task_status.progress = 100
                task_status.status = "Cleanup completed successfully"
                task_status.complete = True

            except Exception as e:
                logger.error("Error in cleanup thread: %s", str(e), exc_info=True)
                task_status.error = str(e)
                task_status.status = f"Error: {str(e)}"
            finally: 
                # Cleanup session files after delay
                threading.Timer(3600, cleanup_session_files, args=[session_id]).start()

        # Start cleanup in background
        thread = threading.Thread(target=run_cleanup)
        thread.daemon = True
        thread.start()

        return jsonify({
            'sessionId': session_id,
            'message': 'Cleanup started'
        })

    except Exception as e:
        logger.error("Error in cleanup endpoint: %s", str(e), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/progress/<session_id>')
def progress(session_id):
    """Get progress status for a specific task"""
    logger.debug("Progress check for session: %s", session_id)
    task_status = tasks.get(session_id)
    if not task_status:
        logger.warning("Invalid session ID: %s", session_id)
        return jsonify({'error': 'Invalid session ID'}), 404

    # Check for timeout
    if time.time() - task_status.last_update > 300: # 5 minutes
        task_status.error = "Operation timed out"
        task_status.status = "Error: Operation timed out"

    response_data = {
        'progress': task_status.progress,
        'status': task_status.status,
        'complete': task_status.complete,
        'error': task_status.error
    }
    logger.debug("Progress response: %s", response_data)
    return jsonify(response_data)

@app.route('/api/download/<session_id>')
def download_session(session_id):
    """Download all files for a specific session as a zip file"""
    try:
        session_path = Path("sessions") / session_id
        if not session_path.exists():
            logger.error(f"Session directory not found: {session_path}")
            return jsonify({'error': 'Session not found'}), 404

        # Create in-memory zip file
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Walk through all files in session directory
            for root, dirs, files in os.walk(session_path):
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(session_path)
                    zf.write(file_path, arc_name)
                    logger.info(f"Added file to zip: {arc_name}")

        # Prepare response
        memory_file.seek(0)
        logger.info(f"Prepared zip file for session: {session_id}")
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'session_{session_id}.zip'
        )

    except Exception as e:
        logger.error(f"Error creating download for session {session_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

def cleanup_old_sessions():
    """Periodic cleanup of old session directories"""
    while True:
        current_time = time.time()
        sessions_dir = Path("sessions")
        if sessions_dir.exists():
            for session_dir in sessions_dir.iterdir():
                if session_dir.is_dir():
                    # Clean up sessions older than 1 hour
                    if current_time - session_dir.stat().st_mtime > 3600:
                        cleanup_session_files(session_dir.name)
        time.sleep(3600)  # Run every hour

if __name__ == '__main__':
    logger.info("Starting Flask application")
    # Create sessions directory if it doesn't exist
    Path("sessions").mkdir(exist_ok=True)
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_sessions, daemon=True)
    cleanup_thread.start()
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=False)