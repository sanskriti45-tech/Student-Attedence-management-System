import unittest
import os
import shutil
from datetime import datetime

from core.system import AttendanceManagementSystem
from core.exceptions import (
    InvalidStudentIDError,
    DuplicateAttendanceEntryError,
    InvalidAttendanceStatusError,
    LeaveRecordNotFoundError
)
from models.person import Student, Faculty
from models.attendance import Attendance

class TestSmartAttendanceSystem(unittest.TestCase):
    def setUp(self):
        # Create a temp folder for test databases
        self.test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data_dir")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        self.ams = AttendanceManagementSystem(data_dir=self.test_dir)

    def tearDown(self):
        # Clean up files created
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
        # Clean up logs created inside system_log.txt during tests
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "system_log.txt")
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
            except OSError:
                pass

    def test_oop_principles(self):
        """Tests Abstraction, Inheritance, and Polymorphism."""
        # 1. Register student and faculty
        student = self.ams.register_student("P001", "Student Name", "s@univ.edu", "123", "S001", "CS")
        faculty = self.ams.register_faculty("P002", "Faculty Name", "f@univ.edu", "456", "F001", "Math")
        
        # Test Inheritance
        self.assertIsInstance(student, Student)
        self.assertIsInstance(faculty, Faculty)
        
        # Test Polymorphism on display_details()
        student_details = student.display_details()
        faculty_details = faculty.display_details()
        
        self.assertIn("Student Profile", student_details)
        self.assertIn("Faculty Profile", faculty_details)
        self.assertIn("Course: CS", student_details)
        self.assertIn("Department: Math", faculty_details)

    def test_encapsulation(self):
        """Tests that student records are protected and access properties exist."""
        student = self.ams.register_student("P001", "Student Name", "s@univ.edu", "123", "S001", "CS")
        self.assertTrue(hasattr(student, "_attendance_records"))
        
        # Adding to records
        att = Attendance("A01", "2026-06-10", "Present")
        student.attendance_records.append(att)
        
        self.assertEqual(len(student.view_attendance()), 1)
        self.assertEqual(student.view_attendance()[0].status, "Present")

    def test_attendance_marking_exceptions(self):
        """Tests double marking and invalid status exception throws."""
        self.ams.register_student("P001", "Student Name", "s@univ.edu", "123", "S001", "CS")
        
        # Mark valid attendance
        self.ams.mark_attendance("S001", "2026-06-10", "Present", "Faculty A")
        
        # Test DuplicateAttendanceEntryError
        with self.assertRaises(DuplicateAttendanceEntryError):
            self.ams.mark_attendance("S001", "2026-06-10", "Present", "Faculty A")
            
        # Test InvalidStudentIDError
        with self.assertRaises(InvalidStudentIDError):
            self.ams.mark_attendance("S999", "2026-06-10", "Present", "Faculty A")

        # Test InvalidAttendanceStatusError
        with self.assertRaises(InvalidAttendanceStatusError):
            self.ams.mark_attendance("S001", "2026-06-11", "SuperPresent", "Faculty A")

    def test_leave_management(self):
        """Tests leave application, approval, status change and exceptions."""
        self.ams.register_student("P001", "Student Name", "s@univ.edu", "123", "S001", "CS")
        
        # Mark initial absent
        self.ams.mark_attendance("S001", "2026-06-10", "Absent", "Faculty A")
        
        # Apply leave request
        req = self.ams.apply_leave_request("S001", "Sick", "2026-06-10")
        self.assertEqual(req.status, "Pending")
        
        # Approve leave request - should trigger decorator logs and auto-update attendance to "Leave"
        self.ams.manage_leave(req.leave_id, "Approved", "Faculty A")
        self.assertEqual(req.status, "Approved")
        
        student = self.ams.get_student("S001")
        self.assertEqual(student.attendance_records[0].status, "Leave")
        
        # Test LeaveRecordNotFoundError
        with self.assertRaises(LeaveRecordNotFoundError):
            self.ams.manage_leave("LR9999", "Approved", "Faculty A")

    def test_recursive_search(self):
        """Tests the recursive search method on attendance records."""
        self.ams.register_student("P001", "Alice", "alice@univ.edu", "123", "S001", "CS")
        self.ams.register_student("P002", "Bob", "bob@univ.edu", "456", "S002", "CS")
        
        self.ams.mark_attendance("S001", "2026-06-01", "Present")
        self.ams.mark_attendance("S002", "2026-06-01", "Present")
        self.ams.mark_attendance("S001", "2026-06-02", "Absent")
        self.ams.mark_attendance("S001", "2026-06-03", "Present")
        
        # Recursive search for S001 all dates
        res = self.ams.search_attendance_recursive(self.ams.attendance_records, 0, "S001")
        self.assertEqual(len(res), 3)
        
        # Recursive search for S001 specific date
        res_date = self.ams.search_attendance_recursive(self.ams.attendance_records, 0, "S001", "2026-06-02")
        self.assertEqual(len(res_date), 1)
        self.assertEqual(res_date[0]["status"], "Absent")

    def test_analytics_lambdas_and_stats(self):
        """Tests analytics threshold calculations, class methods and sorting lambdas."""
        s1 = self.ams.register_student("P001", "Alice", "alice@univ.edu", "123", "S001", "CS")
        s2 = self.ams.register_student("P002", "Bob", "bob@univ.edu", "456", "S002", "CS")
        
        # Alice 100% (2/2)
        self.ams.mark_attendance("S001", "2026-06-01", "Present")
        self.ams.mark_attendance("S001", "2026-06-02", "Present")
        
        # Bob 50% (1/2)
        self.ams.mark_attendance("S002", "2026-06-01", "Present")
        self.ams.mark_attendance("S002", "2026-06-02", "Absent")
        
        # Defaulters list (Threshold 75%)
        defaulters = self.ams.analytics.identify_defaulters(self.ams.students, 75.0)
        self.assertEqual(len(defaulters), 1)
        self.assertEqual(defaulters[0]["student_id"], "S002")
        self.assertEqual(defaulters[0]["percentage"], 50.0)
        
        # Sort students by percentage (Alice should be first)
        sorted_students = self.ams.get_students_sorted_by_attendance()
        self.assertEqual(sorted_students[0].student_id, "S001")
        self.assertEqual(sorted_students[1].student_id, "S002")

    def test_file_saving_and_loading(self):
        """Tests serialization and deserialization of JSON files."""
        self.ams.register_student("P001", "Alice", "alice@univ.edu", "123", "S001", "CS")
        self.ams.register_faculty("P002", "Doctor", "doc@univ.edu", "456", "F001", "CS")
        self.ams.mark_attendance("S001", "2026-06-01", "Present", "Doctor")
        self.ams.apply_leave_request("S001", "Flu", "2026-06-02")
        
        # Save to JSON database files
        self.ams.save_data()
        
        # Create a new system and load the data
        new_ams = AttendanceManagementSystem(data_dir=self.test_dir)
        new_ams.load_data()
        
        self.assertEqual(len(new_ams.students), 1)
        self.assertEqual(len(new_ams.faculty), 1)
        self.assertEqual(len(new_ams.attendance_records), 1)
        self.assertEqual(len(new_ams.leave_requests), 1)
        
        # Check that loaded student object has their local attendance object loaded
        student_obj = new_ams.get_student("S001")
        self.assertEqual(len(student_obj.attendance_records), 1)
        self.assertEqual(student_obj.attendance_records[0].status, "Present")

if __name__ == "__main__":
    unittest.main()
