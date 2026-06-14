import os
import sys
from datetime import datetime
from core.system import AttendanceManagementSystem
from core.exceptions import AttendanceSystemError, IncorrectUserInputError

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_input(prompt, required=True, default=None):
    val = input(prompt).strip()
    if not val and default is not None:
        return default
    if not val and required:
        raise IncorrectUserInputError("This field is required. Input cannot be empty.")
    return val

def display_menu():
    print("\n" + "=" * 50)
    print("      SMART ATTENDANCE MANAGEMENT SYSTEM - CLI")
    print("=" * 50)
    print("1. Student Management")
    print("2. Faculty Management")
    print("3. Attendance Management")
    print("4. Leave Management")
    print("5. Attendance Analytics")
    print("6. Notifications")
    print("7. Report Generation")
    print("8. Save Data")
    print("9. Load Data")
    print("10. Exit")
    print("=" * 50)

def student_management(ams):
    print("\n--- Student Management ---")
    print("1. Register Student")
    print("2. Search Student Attendance (Recursive)")
    print("3. View Student Profile Details")
    choice = get_input("Select Option (1-3): ")
    
    if choice == "1":
        person_id = get_input("Enter Person ID (e.g. P101): ")
        student_id = get_input("Enter Student ID (e.g. S1001): ")
        name = get_input("Enter Full Name: ")
        email = get_input("Enter Email Address: ")
        mobile = get_input("Enter Mobile Number: ")
        course = get_input("Enter Course/Class (e.g. Computer Science): ")
        
        student = ams.register_student(person_id, name, email, mobile, student_id, course)
        print(f"\n[Success] Registered: {student}")
        
    elif choice == "2":
        student_id = get_input("Enter Student ID to search: ")
        # verify student exists
        ams.get_student(student_id)
        
        date_query = input("Enter date (YYYY-MM-DD) or press Enter to search all: ").strip()
        if not date_query:
            date_query = None
            
        print(f"\nSearching attendance records recursively for {student_id}...")
        results = ams.search_attendance_recursive(ams.attendance_records, 0, student_id, date_query)
        
        if not results:
            print("No matching attendance records found.")
        else:
            print(f"Found {len(results)} record(s):")
            for r in results:
                print(f"- Date: {r['date']} | Status: {r['status']} | Marked By: {r['marked_by']}")
                
    elif choice == "3":
        student_id = get_input("Enter Student ID: ")
        student = ams.get_student(student_id)
        print("\n" + student.display_details())
    else:
        print("[Error] Invalid choice.")

def faculty_management(ams):
    print("\n--- Faculty Management ---")
    print("1. Register Faculty")
    print("2. View Faculty Details")
    choice = get_input("Select Option (1-2): ")
    
    if choice == "1":
        person_id = get_input("Enter Person ID (e.g. P501): ")
        faculty_id = get_input("Enter Faculty ID (e.g. F1001): ")
        name = get_input("Enter Full Name: ")
        email = get_input("Enter Email Address: ")
        mobile = get_input("Enter Mobile Number: ")
        department = get_input("Enter Department (e.g. Computer Science): ")
        
        faculty = ams.register_faculty(person_id, name, email, mobile, faculty_id, department)
        print(f"\n[Success] Registered: {faculty}")
        
    elif choice == "2":
        faculty_id = get_input("Enter Faculty ID: ")
        fac = ams.get_faculty(faculty_id)
        if not fac:
            print(f"[Error] Faculty member with ID {faculty_id} not found.")
        else:
            print("\n" + fac.display_details())
    else:
        print("[Error] Invalid choice.")

def attendance_management(ams):
    print("\n--- Attendance Management ---")
    print("1. Mark Daily Attendance")
    print("2. Update Attendance Record")
    print("3. View Daily Attendance Summary")
    choice = get_input("Select Option (1-3): ")
    
    if choice == "1":
        if not ams.students:
            print("[Warning] No students registered in the system.")
            return
            
        date_str = get_input("Enter Date (YYYY-MM-DD) [Default: Today]: ", required=False, default=datetime.today().strftime("%Y-%m-%d"))
        marked_by = get_input("Enter Faculty/Marked By name [Default: System]: ", required=False, default="System")
        
        print("\nMarking attendance for students:")
        for student in ams.students:
            # Check if already marked to avoid raising exception in bulk
            already_marked = False
            for r in ams.attendance_records:
                if r["student_id"] == student.student_id and r["date"] == date_str:
                    already_marked = True
                    break
            
            if already_marked:
                print(f"- {student.name} ({student.student_id}): Already marked.")
                continue
                
            status = get_input(f"- Status for {student.name} ({student.student_id}) (Present/Absent/Leave): ")
            try:
                ams.mark_attendance(student.student_id, date_str, status, marked_by)
                print("  Marked successfully.")
            except AttendanceSystemError as e:
                print(f"  [Error] {str(e)}")
                
    elif choice == "2":
        student_id = get_input("Enter Student ID: ")
        date_str = get_input("Enter Date (YYYY-MM-DD): ")
        status = get_input("Enter New Status (Present/Absent/Leave): ")
        marked_by = get_input("Updated By [Default: Admin]: ", required=False, default="Admin")
        
        ams.update_attendance_record(student_id, date_str, status, marked_by)
        print(f"\n[Success] Attendance updated for {student_id} on {date_str} to {status}.")
        
    elif choice == "3":
        date_str = get_input("Enter Date (YYYY-MM-DD) [Default: Today]: ", required=False, default=datetime.today().strftime("%Y-%m-%d"))
        
        # Present / Absent List Comprehensions
        present_list = ams.get_present_students(date_str)
        absent_list = ams.get_absent_students(date_str)
        
        print(f"\nDaily Summary for {date_str}:")
        print(f"Present Students ({len(present_list)}): {', '.join(present_list) if present_list else 'None'}")
        print(f"Absent Students ({len(absent_list)}): {', '.join(absent_list) if absent_list else 'None'}")
    else:
        print("[Error] Invalid choice.")

def leave_management(ams):
    print("\n--- Leave Management ---")
    print("1. Apply for Leave (Student)")
    print("2. Approve/Reject Leave Request (Faculty)")
    print("3. View Leave Request History")
    choice = get_input("Select Option (1-3): ")
    
    if choice == "1":
        student_id = get_input("Enter Student ID: ")
        date_str = get_input("Enter Leave Date (YYYY-MM-DD): ")
        reason = get_input("Enter Reason for Leave: ")
        
        req = ams.apply_leave_request(student_id, reason, date_str)
        print(f"\n[Success] Applied for Leave request ID: {req.leave_id}")
        
    elif choice == "2":
        leave_id = get_input("Enter Leave Request ID: ")
        status = get_input("Select Action (Approved/Rejected): ")
        approved_by = get_input("Faculty Member Name: ")
        
        req = ams.manage_leave(leave_id, status, approved_by)
        print(f"\n[Success] Leave Request {leave_id} has been marked as {req.status}.")
        
    elif choice == "3":
        if not ams.leave_requests:
            print("No leave requests found.")
        else:
            print("\nLeave Requests:")
            for req in ams.leave_requests:
                print(f"- ID: {req.leave_id} | Student: {req.student_id} | Date: {req.date_str} | Reason: {req.reason} | Status: {req.status}")
    else:
        print("[Error] Invalid choice.")

def attendance_analytics(ams):
    print("\n--- Attendance Analytics ---")
    print("1. View Student Attendance Percentage")
    print("2. View Institution-wide Statistics")
    print("3. View Defaulter List (Below 75%)")
    choice = get_input("Select Option (1-3): ")
    
    if choice == "1":
        student_id = get_input("Enter Student ID: ")
        student = ams.get_student(student_id)
        records = student.attendance_records
        present = sum(1 for r in records if r.status == "Present")
        total = len(records)
        pct = ams.analytics.calculate_percentage(present, total)
        print(f"\nAttendance rate for {student.name}: {pct}% ({present}/{total} present)")
        
    elif choice == "2":
        # Class method call
        stats = ams.analytics.generate_statistics(ams.students)
        print("\nInstitution-Wide Attendance Statistics:")
        print(f"- Total Students: {stats['total_students']}")
        print(f"- Average Attendance Rate: {stats['overall_attendance_avg']}%")
        print(f"- Students with 100% Attendance: {stats['perfect_attendance_count']}")
        print(f"- Defaulter Students (< 75%): {stats['low_attendance_count']}")
        
    elif choice == "3":
        threshold = float(get_input("Enter threshold percentage [Default: 75.0]: ", required=False, default="75.0"))
        defaulters = ams.analytics.identify_defaulters(ams.students, threshold)
        
        if not defaulters:
            print(f"\nNo defaulters found below {threshold}%.")
        else:
            print(f"\nDefaulters List (Below {threshold}%):")
            # Defaulters sorted by percentage via analytics lambda function
            for d in defaulters:
                print(f"- {d['name']} ({d['student_id']}): {d['percentage']}% ({d['present']}/{d['total']} classes) | Course: {d['course']}")
    else:
        print("[Error] Invalid choice.")

def notification_management(ams):
    print("\n--- Notification Center ---")
    if not ams.notifications:
        print("No notification logs found.")
    else:
        print(f"\nTotal Logs: {len(ams.notifications)}")
        for n in ams.notifications:
            print(n.display_notification())

def report_management(ams):
    print("\n--- Report Generation ---")
    print("Select Report Type:")
    print("1. Daily Attendance Report")
    print("2. Monthly Summary Report")
    print("3. Defaulter Report")
    print("4. Leave Report")
    choice = get_input("Select Option (1-4): ")
    
    report_types = {
        "1": "Daily",
        "2": "Monthly",
        "3": "Defaulter",
        "4": "Leave"
    }
    
    rep_type = report_types.get(choice)
    if not rep_type:
        print("[Error] Invalid choice.")
        return
        
    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
        
    filename = f"{rep_type.lower()}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(exports_dir, filename)
    
    print(f"\nGenerating {rep_type} report...")
    rep = ams.generate_reports(rep_type, filepath)
    print(f"[Success] {rep}")
    print(f"Report exported to: {filepath}")

def main():
    ams = AttendanceManagementSystem()
    print("Loading database records...")
    ams.load_data()
    print(f"Database loaded. Total Students registered: {len(ams)}")
    
    while True:
        try:
            display_menu()
            choice = get_input("Select Option (1-10): ")
            
            if choice == "1":
                student_management(ams)
            elif choice == "2":
                faculty_management(ams)
            elif choice == "3":
                attendance_management(ams)
            elif choice == "4":
                leave_management(ams)
            elif choice == "5":
                attendance_analytics(ams)
            elif choice == "6":
                notification_management(ams)
            elif choice == "7":
                report_management(ams)
            elif choice == "8":
                print("Saving data to JSON files...")
                ams.save_data()
                print("[Success] Data saved successfully.")
            elif choice == "9":
                print("Loading data from JSON files...")
                ams.load_data()
                print(f"[Success] Data loaded. Total Students: {len(ams)}")
            elif choice == "10":
                print("\nSaving data before exit...")
                ams.save_data()
                print("Goodbye!")
                sys.exit(0)
            else:
                print("[Error] Invalid option. Please select 1 to 10.")
        except AttendanceSystemError as ase:
            print(f"\n[System Error] {str(ase)}")
        except Exception as e:
            print(f"\n[Error] An unexpected error occurred: {str(e)}")
            
        input("\nPress Enter to continue...")
        clear_console()

if __name__ == "__main__":
    main()
