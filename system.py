import os
import json
from datetime import datetime
from core.exceptions import (
    InvalidStudentIDError,
    DuplicateAttendanceEntryError,
    InvalidAttendanceStatusError,
    LeaveRecordNotFoundError
)
from core.decorators import (
    log_attendance,
    log_leave_approval,
    log_report_generation,
    log_notification_sending
)
from models.person import Student, Faculty
from models.attendance import Attendance
from models.leave import LeaveRequest
from models.notification import Notification
from models.report import Report
from models.analytics import AttendanceAnalytics

class AttendanceManagementSystem:
    def __init__(self, data_dir=None):
        self.students = []
        self.faculty = []
        self.attendance_records = []  # Contains dicts: {"attendance_id": str, "student_id": str, "date": str, "status": str, "marked_by": str}
        self.leave_requests = []      # Contains LeaveRequest objects
        self.notifications = []        # Contains Notification objects
        
        # Composition of helper objects
        self.analytics = AttendanceAnalytics()
        
        self.data_dir = data_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def register_student(self, person_id, name, email, mobile_number, student_id, course):
        """Registers a new student. Validates that student_id is unique."""
        # Check for duplicates
        if any(s.student_id == student_id for s in self.students):
            raise DuplicateAttendanceEntryError(f"Student with ID {student_id} is already registered.")
        
        student = Student(person_id, name, email, mobile_number, student_id, course)
        self.students.append(student)
        return student

    def register_faculty(self, person_id, name, email, mobile_number, faculty_id, department):
        """Registers a new faculty member."""
        if any(f.faculty_id == faculty_id for f in self.faculty):
            raise DuplicateAttendanceEntryError(f"Faculty with ID {faculty_id} is already registered.")
        
        faculty_member = Faculty(person_id, name, email, mobile_number, faculty_id, department)
        self.faculty.append(faculty_member)
        return faculty_member

    def get_student(self, student_id):
        """Helper to get a student object by ID or raise InvalidStudentIDError."""
        for s in self.students:
            if s.student_id == student_id:
                return s
        raise InvalidStudentIDError(f"Student ID '{student_id}' does not exist.")

    def get_faculty(self, faculty_id):
        """Helper to get a faculty object by ID."""
        for f in self.faculty:
            if f.faculty_id == faculty_id:
                return f
        return None

    @log_attendance
    def mark_attendance(self, student_id, date_str, status, marked_by="System"):
        """Marks attendance for a student. Checks for duplicate entry."""
        # Check if student exists
        student = self.get_student(student_id)
        
        # Verify valid status
        if status not in Attendance.STATUS_VALUES:
            raise InvalidAttendanceStatusError(f"Invalid status '{status}'. Must be one of {Attendance.STATUS_VALUES}")

        # Check for duplicate entry
        for record in self.attendance_records:
            if record["student_id"] == student_id and record["date"] == date_str:
                raise DuplicateAttendanceEntryError(f"Attendance for Student {student_id} is already marked on {date_str}.")

        # Generate a unique attendance ID
        attendance_id = f"ATT{len(self.attendance_records) + 1:04d}"
        
        # Create Attendance object
        att_obj = Attendance(attendance_id, date_str, status)
        
        # Add to student's records (for OOP view_attendance)
        student.attendance_records.append(att_obj)
        
        # Save to main list
        self.attendance_records.append({
            "attendance_id": attendance_id,
            "student_id": student_id,
            "date": date_str,
            "status": status,
            "marked_by": marked_by
        })
        
        # Send notification if absent
        if status == "Absent":
            self.create_absent_notification(student)

        return att_obj

    def update_attendance_record(self, student_id, date_str, status, updated_by="System"):
        """Updates an existing attendance record."""
        student = self.get_student(student_id)
        if status not in Attendance.STATUS_VALUES:
            raise InvalidAttendanceStatusError(f"Invalid status '{status}'. Must be one of {Attendance.STATUS_VALUES}")
            
        found = False
        # Update system-wide record
        for record in self.attendance_records:
            if record["student_id"] == student_id and record["date"] == date_str:
                record["status"] = status
                record["marked_by"] = f"{record['marked_by']} / Updated by {updated_by}"
                found = True
                break
                
        if not found:
            # If not found, mark it as new
            return self.mark_attendance(student_id, date_str, status, marked_by=updated_by)

        # Update student's local OOP object
        for att in student.attendance_records:
            if att.date == date_str:
                att.update_attendance(status)
                break
        return True

    def has_attendance_status(self, student_id, date_str, status):
        """Helper for list comprehensions. Returns True if student has specific status on date."""
        for record in self.attendance_records:
            if record["student_id"] == student_id and record["date"] == date_str and record["status"] == status:
                return True
        return False

    def get_present_students(self, date_str):
        """List Comprehension: Returns list of student names present on a specific date."""
        return [s.name for s in self.students if self.has_attendance_status(s.student_id, date_str, "Present")]

    def get_absent_students(self, date_str):
        """List Comprehension: Returns list of student names absent on a specific date."""
        return [s.name for s in self.students if self.has_attendance_status(s.student_id, date_str, "Absent")]

    def apply_leave_request(self, student_id, reason, date_str):
        """Submits a leave request for a student."""
        # Ensure student exists
        self.get_student(student_id)
        
        leave_id = f"LR{len(self.leave_requests) + 1:04d}"
        req = LeaveRequest(leave_id, student_id, date_str, reason)
        self.leave_requests.append(req)
        return req

    @log_leave_approval
    def manage_leave(self, leave_id, status, approved_by="Faculty"):
        """Approves or rejects a leave request, and auto-updates attendance if approved."""
        target_req = None
        for req in self.leave_requests:
            if req.leave_id == leave_id:
                target_req = req
                break
        
        if not target_req:
            raise LeaveRecordNotFoundError(f"Leave request with ID {leave_id} not found.")

        if status == "Approved":
            target_req.approve_leave()
            # If approved, update attendance status for that date to "Leave"
            self.update_attendance_record(target_req.student_id, target_req.date_str, "Leave", updated_by=approved_by)
            
            # Send Notification
            msg = f"Leave approved for Student {target_req.student_id} on {target_req.date_str} by {approved_by}."
            self.send_notification_alert(msg, target_req.student_id)
        else:
            target_req.reject_leave()
            msg = f"Leave rejected for Student {target_req.student_id} on {target_req.date_str} by {approved_by}."
            self.send_notification_alert(msg, target_req.student_id)
            
        return target_req

    @log_notification_sending
    def send_notification_alert(self, message, recipient_email_or_id):
        """Creates and logs a notification."""
        notif_id = f"NOT{len(self.notifications) + 1:04d}"
        notif = Notification(notif_id, message)
        self.notifications.append(notif)
        notif.send_notification(recipient_email_or_id)
        return notif

    def create_absent_notification(self, student):
        """Triggered automatically when a student is marked Absent."""
        msg = f"ALERT: Student {student.name} ({student.student_id}) was marked ABSENT today."
        self.send_notification_alert(msg, student.email)

    def check_and_warn_defaulters(self, threshold=75.0):
        """Checks for defaulters and generates warnings for them."""
        defaulters = self.analytics.identify_defaulters(self.students, threshold)
        warnings_sent = 0
        for d in defaulters:
            msg = f"WARNING: Low attendance warning for {d['name']} ({d['student_id']}). Current rate: {d['percentage']}%."
            # Check if warning already sent recently to avoid duplication (optional, here we send it)
            self.send_notification_alert(msg, d['student_id'])
            warnings_sent += 1
        return warnings_sent

    def search_attendance_recursive(self, records, index, student_id, target_date=None, results=None):
        """Recursive Function: Recursively searches attendance records for a student."""
        if results is None:
            results = []
        
        # Base case
        if index >= len(records):
            return results
        
        record = records[index]
        if record["student_id"] == student_id:
            if not target_date or record["date"] == target_date:
                results.append(record)
                
        # Recursive step
        return self.search_attendance_recursive(records, index + 1, student_id, target_date, results)

    # Lambda Function usages
    def get_students_sorted_by_attendance(self):
        """Lambda Function: Sorts students by their attendance percentage in descending order."""
        return sorted(
            self.students, 
            key=lambda s: self.analytics.calculate_percentage(
                sum(1 for r in s.attendance_records if r.status == "Present"), 
                len(s.attendance_records)
            ),
            reverse=True
        )

    def get_student_records_sorted_by_date(self, student_id):
        """Lambda Function: Sorts a specific student's attendance records by date in ascending order."""
        student = self.get_student(student_id)
        return sorted(student.attendance_records, key=lambda r: r.date)

    @log_report_generation
    def generate_reports(self, report_type, filepath):
        """Generates a CSV report based on report_type."""
        data_rows = []
        
        if report_type == "Daily":
            # Let's use today's date or all daily logs
            for r in self.attendance_records:
                data_rows.append({
                    "Attendance ID": r["attendance_id"],
                    "Student ID": r["student_id"],
                    "Student Name": self.get_student(r["student_id"]).name,
                    "Date": r["date"],
                    "Status": r["status"],
                    "Marked By": r["marked_by"]
                })
        elif report_type == "Defaulter":
            defaulters = self.analytics.identify_defaulters(self.students)
            for d in defaulters:
                data_rows.append({
                    "Student ID": d["student_id"],
                    "Name": d["name"],
                    "Course": d["course"],
                    "Present Classes": d["present"],
                    "Total Classes": d["total"],
                    "Attendance Percentage": f"{d['percentage']}%"
                })
        elif report_type == "Leave":
            for l in self.leave_requests:
                data_rows.append({
                    "Leave ID": l.leave_id,
                    "Student ID": l.student_id,
                    "Student Name": self.get_student(l.student_id).name,
                    "Date": l.date_str,
                    "Reason": l.reason,
                    "Status": l.status
                })
        elif report_type == "Monthly":
            # Aggregate monthly summary for all students
            for s in self.students:
                records = s.attendance_records
                total = len(records)
                present = sum(1 for r in records if r.status == "Present")
                absent = sum(1 for r in records if r.status == "Absent")
                leave = sum(1 for r in records if r.status == "Leave")
                pct = self.analytics.calculate_percentage(present, total)
                
                data_rows.append({
                    "Student ID": s.student_id,
                    "Name": s.name,
                    "Course": s.course,
                    "Total Classes": total,
                    "Present": present,
                    "Absent": absent,
                    "Leaves": leave,
                    "Percentage": f"{pct}%"
                })
        
        rep_id = f"REP{datetime.now().strftime('%m%d%H%M')}"
        rep = Report(rep_id, report_type, data_rows)
        rep.export_report(filepath)
        return rep

    def save_data(self, directory=None):
        """Saves student records, attendance logs, leave requests and notifications to JSON files."""
        target_dir = directory or self.data_dir
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # 1. Students
        students_data = []
        for s in self.students:
            students_data.append({
                "person_id": s.person_id,
                "name": s.name,
                "email": s.email,
                "mobile_number": s.mobile_number,
                "student_id": s.student_id,
                "course": s.course
            })
        with open(os.path.join(target_dir, "students.json"), "w") as f:
            json.dump(students_data, f, indent=4)

        # 2. Faculty
        faculty_data = []
        for fac in self.faculty:
            faculty_data.append({
                "person_id": fac.person_id,
                "name": fac.name,
                "email": fac.email,
                "mobile_number": fac.mobile_number,
                "faculty_id": fac.faculty_id,
                "department": fac.department
            })
        with open(os.path.join(target_dir, "faculty.json"), "w") as f:
            json.dump(faculty_data, f, indent=4)

        # 3. Attendance Records
        with open(os.path.join(target_dir, "attendance.json"), "w") as f:
            json.dump(self.attendance_records, f, indent=4)

        # 4. Leave Requests
        leaves_data = []
        for l in self.leave_requests:
            leaves_data.append({
                "leave_id": l.leave_id,
                "student_id": l.student_id,
                "date_str": l.date_str,
                "reason": l.reason,
                "status": l.status
            })
        with open(os.path.join(target_dir, "leaves.json"), "w") as f:
            json.dump(leaves_data, f, indent=4)

        # 5. Notifications
        notifs_data = []
        for n in self.notifications:
            notifs_data.append({
                "notification_id": n.notification_id,
                "message": n.message,
                "notification_date": n.notification_date
            })
        with open(os.path.join(target_dir, "notifications.json"), "w") as f:
            json.dump(notifs_data, f, indent=4)

        return True

    def load_data(self, directory=None):
        """Loads data from JSON files. Handles FileNotFoundError."""
        target_dir = directory or self.data_dir
        
        # Reset collections
        self.students = []
        self.faculty = []
        self.attendance_records = []
        self.leave_requests = []
        self.notifications = []

        try:
            # 1. Load Students
            students_path = os.path.join(target_dir, "students.json")
            if os.path.exists(students_path):
                with open(students_path, "r") as f:
                    s_list = json.load(f)
                    for item in s_list:
                        self.register_student(
                            item["person_id"], item["name"], item["email"], 
                            item["mobile_number"], item["student_id"], item["course"]
                        )
            
            # 2. Load Faculty
            faculty_path = os.path.join(target_dir, "faculty.json")
            if os.path.exists(faculty_path):
                with open(faculty_path, "r") as f:
                    f_list = json.load(f)
                    for item in f_list:
                        self.register_faculty(
                            item["person_id"], item["name"], item["email"],
                            item["mobile_number"], item["faculty_id"], item["department"]
                        )
            
            # 3. Load Attendance Records
            attendance_path = os.path.join(target_dir, "attendance.json")
            if os.path.exists(attendance_path):
                with open(attendance_path, "r") as f:
                    self.attendance_records = json.load(f)
                
                # Re-populate local attendance records in student objects
                for record in self.attendance_records:
                    try:
                        student = self.get_student(record["student_id"])
                        att_obj = Attendance(record["attendance_id"], record["date"], record["status"])
                        student.attendance_records.append(att_obj)
                    except InvalidStudentIDError:
                        # Student might have been deleted, or data is corrupt. Skip.
                        pass

            # 4. Load Leaves
            leaves_path = os.path.join(target_dir, "leaves.json")
            if os.path.exists(leaves_path):
                with open(leaves_path, "r") as f:
                    l_list = json.load(f)
                    for item in l_list:
                        req = LeaveRequest(
                            item["leave_id"], item["student_id"], item["date_str"], 
                            item["reason"], item["status"]
                        )
                        self.leave_requests.append(req)

            # 5. Load Notifications
            notifs_path = os.path.join(target_dir, "notifications.json")
            if os.path.exists(notifs_path):
                with open(notifs_path, "r") as f:
                    n_list = json.load(f)
                    for item in n_list:
                        notif = Notification(
                            item["notification_id"], item["message"], item["notification_date"]
                        )
                        self.notifications.append(notif)
            
            return True
        except FileNotFoundError as e:
            # Re-raise standard file not found or log
            print(f"Data file not found: {str(e)}")
            return False

    def backup_data(self):
        """Creates a timestamped backup directory and saves files there."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(self.data_dir), f"backup_{timestamp}")
        self.save_data(backup_dir)
        return backup_dir

    def restore_data_from_backup(self, backup_dir):
        """Restores database collections from a specific backup directory."""
        if not os.path.exists(backup_dir):
            raise FileNotFoundError(f"Backup directory {backup_dir} does not exist.")
        self.load_data(backup_dir)
        # Re-save to current data folder to persist
        self.save_data()
        return True

    def __str__(self):
        return f"Smart Attendance System: {len(self.students)} Students, {len(self.faculty)} Faculty registered."

    def __repr__(self):
        return f"AttendanceManagementSystem(students_count={len(self.students)}, faculty_count={len(self.faculty)})"

    def __len__(self):
        """Magic Method: Returns the total number of students in the system."""
        return len(self.students)
