import functools
import os
from datetime import datetime

LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "system_log.txt")

def ensure_log_dir():
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

def write_to_log(message):
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE_PATH, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def log_attendance(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # args[0] is typically the system instance, args[1] student_id, args[2] date, args[3] status, etc.
        # Let's extract values dynamically based on signature
        try:
            result = func(*args, **kwargs)
            # Try to form a helpful log message
            student_id = args[1] if len(args) > 1 else kwargs.get("student_id", "Unknown")
            date = args[2] if len(args) > 2 else kwargs.get("date", "Today")
            status = args[3] if len(args) > 3 else kwargs.get("status", "Unknown")
            write_to_log(f"ATTENDANCE MARKED: Student ID {student_id} on {date} marked as {status}.")
            return result
        except Exception as e:
            write_to_log(f"ATTENDANCE FAILURE: Attempted to mark attendance for {args} {kwargs}. Error: {str(e)}")
            raise
    return wrapper

def log_leave_approval(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            leave_id = args[1] if len(args) > 1 else kwargs.get("leave_id", "Unknown")
            status = args[2] if len(args) > 2 else kwargs.get("status", "Unknown")
            write_to_log(f"LEAVE APPROVAL: Leave request {leave_id} updated to {status}.")
            return result
        except Exception as e:
            write_to_log(f"LEAVE APPROVAL FAILURE: Leave request action failed. Error: {str(e)}")
            raise
    return wrapper

def log_report_generation(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            report_type = args[1] if len(args) > 1 else kwargs.get("report_type", "General")
            write_to_log(f"REPORT GENERATED: {report_type} report successfully created.")
            return result
        except Exception as e:
            write_to_log(f"REPORT GENERATION FAILURE: Failed to generate {args} {kwargs}. Error: {str(e)}")
            raise
    return wrapper

def log_notification_sending(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # notification object is usually passed or created
            message = args[1] if len(args) > 1 else kwargs.get("message", "")
            write_to_log(f"NOTIFICATION SENT: {message[:60]}...")
            return result
        except Exception as e:
            write_to_log(f"NOTIFICATION FAILURE: Failed to send notification. Error: {str(e)}")
            raise
    return wrapper
