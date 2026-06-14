import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from core.system import AttendanceManagementSystem
from core.exceptions import AttendanceSystemError
from models.attendance import Attendance

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "smart_attendance_secret_key"

# Instantiate System Core
ams = AttendanceManagementSystem()

# Try to seed initial demo data if empty
def seed_demo_data():
    if len(ams.students) > 0:
        return
    
    print("Seeding initial demo data for a richer dashboard experience...")
    # Register Students
    s1 = ams.register_student("P101", "Alice Vance", "alice@univ.edu", "9876543210", "S1001", "Computer Science")
    s2 = ams.register_student("P102", "Bob Smith", "bob@univ.edu", "9876543211", "S1002", "Computer Science")
    s3 = ams.register_student("P103", "Charlie Brown", "charlie@univ.edu", "9876543212", "S1003", "Mechanical Engineering")
    s4 = ams.register_student("P104", "Diana Prince", "diana@univ.edu", "9876543213", "S1004", "Electrical Engineering")
    s5 = ams.register_student("P105", "Evan Wright", "evan@univ.edu", "9876543214", "S1005", "Computer Science")

    # Register Faculty
    ams.register_faculty("P501", "Dr. Robert Hoare", "hoare@univ.edu", "9000000001", "F1001", "Computer Science")
    ams.register_faculty("P502", "Prof. Sarah Jenkins", "jenkins@univ.edu", "9000000002", "F1002", "Mechanical Engineering")

    # Generate some attendance records for the past 10 days
    today = datetime.today()
    for i in range(10, 0, -1):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        # Alice is present 90%
        ams.mark_attendance("S1001", date_str, "Present" if i != 5 else "Absent", "Dr. Robert Hoare")
        # Bob is present 50% (Defaulter)
        ams.mark_attendance("S1002", date_str, "Present" if i % 2 == 0 else "Absent", "Dr. Robert Hoare")
        # Charlie is present 80%
        ams.mark_attendance("S1003", date_str, "Present" if i not in (3, 7) else "Absent", "Prof. Sarah Jenkins")
        # Diana is present 100%
        ams.mark_attendance("S1004", date_str, "Present", "Prof. Sarah Jenkins")
        # Evan is present 40% (Defaulter)
        ams.mark_attendance("S1005", date_str, "Present" if i <= 4 else "Absent", "Dr. Robert Hoare")

    # Add leave request
    req1 = ams.apply_leave_request("S1003", "Family Emergency", (today - timedelta(days=3)).strftime("%Y-%m-%d"))
    req2 = ams.apply_leave_request("S1002", "Medical Leave", (today - timedelta(days=1)).strftime("%Y-%m-%d"))
    
    # Approve one request
    ams.manage_leave(req1.leave_id, "Approved", "Prof. Sarah Jenkins")
    
    # Save the seeded database
    ams.save_data()
    print("Demo data seeded successfully.")

# Load database on startup, then seed if needed
try:
    ams.load_data()
    seed_demo_data()
except Exception as e:
    print(f"Error loading/seeding database: {e}")

# Matplotlib Chart generator route
@app.route("/chart.png")
def get_chart():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
        
        # Gather analytics data
        courses = {}
        for s in ams.students:
            courses[s.course] = courses.get(s.course, [])
            records = s.attendance_records
            present = sum(1 for r in records if r.status == "Present")
            total = len(records)
            pct = ams.analytics.calculate_percentage(present, total)
            courses[s.course].append(pct)
            
        avg_course_pct = {course: round(sum(pcts)/len(pcts), 1) for course, pcts in courses.items() if pcts}
        
        if not avg_course_pct:
            avg_course_pct = {"No Data": 0}

        # Plot styling
        fig, ax = plt.subplots(figsize=(6, 4), facecolor='#13151a')
        ax.set_facecolor('#13151a')
        
        courses_labels = list(avg_course_pct.keys())
        percentages = list(avg_course_pct.values())
        
        # Colors: nice neon glass gradient simulator
        colors = ['#4f46e5', '#3b82f6', '#10b981', '#f59e0b', '#ec4899']
        bars = ax.bar(courses_labels, percentages, color=colors[:len(courses_labels)], width=0.5, edgecolor='#3b82f6', linewidth=1)
        
        # Styling text and grid
        ax.spines['bottom'].set_color('#374151')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#374151')
        ax.tick_params(colors='#9ca3af', which='both')
        ax.yaxis.grid(True, color='#1f2937', linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)
        
        # Add labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', color='#ffffff', fontweight='bold', fontsize=9)
                        
        ax.set_title("Average Attendance by Course", color='#ffffff', fontsize=12, fontweight='bold', pad=15)
        ax.set_ylim(0, 110)
        
        plt.tight_layout()
        img_io = io.BytesIO()
        plt.savefig(img_io, format='png', facecolor=fig.get_facecolor(), dpi=100)
        img_io.seek(0)
        plt.close(fig)
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        print(f"Matplotlib generation failed or not installed: {e}")
        # Send a fallback blank image or static placeholder
        # We can try to use a pre-existing asset, but returning 404 is also handled in frontend with fallback to Chart.js.
        return "Matplotlib not configured", 404

# Core routes
@app.route("/")
@app.route("/dashboard")
def dashboard():
    stats = ams.analytics.generate_statistics(ams.students)
    
    # Calculate some extra dashboard widgets details
    defaulters_list = ams.analytics.identify_defaulters(ams.students)
    recent_leaves = sorted(ams.leave_requests, key=lambda l: l.leave_id, reverse=True)[:5]
    
    # List of unique dates with attendance records
    unique_dates = sorted(list(set(r["date"] for r in ams.attendance_records)), reverse=True)
    recent_dates = unique_dates[:5]
    
    # Map dates to summary count
    recent_summaries = []
    for d in recent_dates:
        present = len(ams.get_present_students(d))
        absent = len(ams.get_absent_students(d))
        recent_summaries.append({"date": d, "present": present, "absent": absent, "total": present + absent})
        
    # Chart.js data packages (sent to frontend as JSON context)
    chart_labels = []
    chart_data = []
    for s in ams.students:
        records = s.attendance_records
        present = sum(1 for r in records if r.status == "Present")
        total = len(records)
        pct = ams.analytics.calculate_percentage(present, total)
        chart_labels.append(s.name)
        chart_data.append(pct)
        
    return render_template(
        "dashboard.html",
        stats=stats,
        defaulters=defaulters_list,
        recent_leaves=recent_leaves,
        recent_summaries=recent_summaries,
        chart_labels=chart_labels,
        chart_data=chart_data,
        total_students=len(ams),
        total_faculty=len(ams.faculty)
    )

@app.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        try:
            person_id = request.form.get("person_id")
            student_id = request.form.get("student_id")
            name = request.form.get("name")
            email = request.form.get("email")
            mobile = request.form.get("mobile_number")
            course = request.form.get("course")
            
            if not all([person_id, student_id, name, email, mobile, course]):
                raise AttendanceSystemError("All registration fields must be completed.")
                
            ams.register_student(person_id, name, email, mobile, student_id, course)
            ams.save_data()
            flash(f"Student {name} registered successfully!", "success")
        except AttendanceSystemError as e:
            flash(str(e), "danger")
        return redirect(url_for("students"))
        
    search_q = request.args.get("query", "").strip()
    if search_q:
        # Filter matching student objects
        filtered_students = [s for s in ams.students if search_q.lower() in s.name.lower() or search_q.lower() in s.student_id.lower() or search_q.lower() in s.course.lower()]
    else:
        filtered_students = ams.students
        
    # Inject attendance details for list rendering
    student_details = []
    for s in filtered_students:
        records = s.attendance_records
        present = sum(1 for r in records if r.status == "Present")
        total = len(records)
        pct = ams.analytics.calculate_percentage(present, total)
        student_details.append({
            "obj": s,
            "profile_string": s.display_details(),
            "present": present,
            "total": total,
            "percentage": pct
        })
        
    return render_template("students.html", students=student_details, query=search_q)

@app.route("/faculty", methods=["GET", "POST"])
def faculty():
    if request.method == "POST":
        try:
            person_id = request.form.get("person_id")
            faculty_id = request.form.get("faculty_id")
            name = request.form.get("name")
            email = request.form.get("email")
            mobile = request.form.get("mobile_number")
            department = request.form.get("department")
            
            if not all([person_id, faculty_id, name, email, mobile, department]):
                raise AttendanceSystemError("All registration fields must be completed.")
                
            ams.register_faculty(person_id, name, email, mobile, faculty_id, department)
            ams.save_data()
            flash(f"Faculty Member {name} registered successfully!", "success")
        except AttendanceSystemError as e:
            flash(str(e), "danger")
        return redirect(url_for("faculty"))
        
    return render_template("faculty.html", faculty=ams.faculty)

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    today_str = datetime.today().strftime("%Y-%m-%d")
    selected_date = request.args.get("date", today_str)
    
    if request.method == "POST":
        # Process bulk marking form
        marked_by = request.form.get("marked_by", "System Admin")
        for s in ams.students:
            status_key = f"status_{s.student_id}"
            status = request.form.get(status_key)
            if status:
                try:
                    # Check if already marked for this date
                    already_marked = False
                    for r in ams.attendance_records:
                        if r["student_id"] == s.student_id and r["date"] == selected_date:
                            already_marked = True
                            break
                            
                    if already_marked:
                        ams.update_attendance_record(s.student_id, selected_date, status, updated_by=marked_by)
                    else:
                        ams.mark_attendance(s.student_id, selected_date, status, marked_by)
                except AttendanceSystemError as e:
                    print(f"Error marking {s.student_id}: {e}")
                    
        ams.save_data()
        flash(f"Attendance for {selected_date} saved successfully!", "success")
        return redirect(url_for("attendance", date=selected_date))
        
    # Build list of students with their marked status for this date if it exists
    students_status = []
    for s in ams.students:
        status = ""
        for r in ams.attendance_records:
            if r["student_id"] == s.student_id and r["date"] == selected_date:
                status = r["status"]
                break
        students_status.append({"obj": s, "status": status})
        
    # Get overall unique dates logged in system for navigation dropdown
    unique_dates = sorted(list(set(r["date"] for r in ams.attendance_records)), reverse=True)
    if today_str not in unique_dates:
        unique_dates.insert(0, today_str)

    # Present / Absent counts for lists
    present_names = ams.get_present_students(selected_date)
    absent_names = ams.get_absent_students(selected_date)
    
    return render_template(
        "attendance.html",
        date=selected_date,
        students_status=students_status,
        unique_dates=unique_dates,
        present_count=len(present_names),
        absent_count=len(absent_names),
        present_names=present_names,
        absent_names=absent_names
    )

@app.route("/leaves", methods=["GET", "POST"])
def leaves():
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "apply":
            try:
                student_id = request.form.get("student_id")
                date_str = request.form.get("date")
                reason = request.form.get("reason")
                
                if not all([student_id, date_str, reason]):
                    raise AttendanceSystemError("All leave request details are required.")
                    
                req = ams.apply_leave_request(student_id, reason, date_str)
                ams.save_data()
                flash(f"Leave request applied for Student {student_id} on {date_str} (ID: {req.leave_id})", "success")
            except AttendanceSystemError as e:
                flash(str(e), "danger")
                
        elif action in ("Approve", "Reject"):
            try:
                leave_id = request.form.get("leave_id")
                status = "Approved" if action == "Approve" else "Rejected"
                faculty_name = request.form.get("faculty_name", "Faculty Reviewer")
                
                ams.manage_leave(leave_id, status, faculty_name)
                ams.save_data()
                flash(f"Leave request {leave_id} marked as {status}!", "success")
            except AttendanceSystemError as e:
                flash(str(e), "danger")
                
        return redirect(url_for("leaves"))
        
    return render_template(
        "leaves.html",
        leaves=ams.leave_requests,
        students=ams.students,
        faculty=ams.faculty
    )

@app.route("/analytics")
def analytics():
    threshold = float(request.args.get("threshold", "75.0"))
    defaulters = ams.analytics.identify_defaulters(ams.students, threshold)
    stats = ams.analytics.generate_statistics(ams.students)
    
    # Subject-wise attendance (simulated: group by course)
    course_stats = {}
    for s in ams.students:
        course_stats[s.course] = course_stats.get(s.course, {"present": 0, "total": 0, "students_count": 0})
        records = s.attendance_records
        course_stats[s.course]["present"] += sum(1 for r in records if r.status == "Present")
        course_stats[s.course]["total"] += len(records)
        course_stats[s.course]["students_count"] += 1
        
    for course, val in course_stats.items():
        val["percentage"] = ams.analytics.calculate_percentage(val["present"], val["total"])
        
    return render_template(
        "analytics.html",
        defaulters=defaulters,
        threshold=threshold,
        stats=stats,
        course_stats=course_stats
    )

@app.route("/analytics/warn-defaulters", methods=["POST"])
def warn_defaulters():
    threshold = float(request.form.get("threshold", "75.0"))
    count = ams.check_and_warn_defaulters(threshold)
    ams.save_data()
    flash(f"Warning notifications sent to {count} students with attendance below {threshold}%.", "warning")
    return redirect(url_for("analytics", threshold=threshold))

@app.route("/notifications")
def notifications():
    return render_template("notifications.html", notifications=sorted(ams.notifications, key=lambda n: n.notification_date, reverse=True))

@app.route("/reports", methods=["GET", "POST"])
def reports():
    if request.method == "POST":
        report_type = request.form.get("report_type")
        
        exports_dir = os.path.join(app.root_path, "static", "exports")
        if not os.path.exists(exports_dir):
            os.makedirs(exports_dir)
            
        filename = f"{report_type.lower()}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(exports_dir, filename)
        
        try:
            rep = ams.generate_reports(report_type, filepath)
            ams.save_data()
            flash(f"Generated {report_type} report successfully!", "success")
            # Return file for download
            return send_file(filepath, as_attachment=True, download_name=filename)
        except Exception as e:
            flash(f"Failed to generate report: {str(e)}", "danger")
            
    # List generated reports in exports folder
    exports_dir = os.path.join(app.root_path, "static", "exports")
    generated_files = []
    if os.path.exists(exports_dir):
        for f in os.listdir(exports_dir):
            if f.endswith(".csv"):
                path = os.path.join(exports_dir, f)
                stat = os.stat(path)
                generated_files.append({
                    "name": f,
                    "size": f"{stat.st_size / 1024:.2f} KB",
                    "time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
                
    return render_template("reports.html", reports=generated_files)

@app.route("/data", methods=["GET", "POST"])
def data_management():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "save":
                ams.save_data()
                flash("System database saved successfully to JSON files.", "success")
            elif action == "load":
                ams.load_data()
                flash("System database loaded successfully from JSON files.", "success")
            elif action == "backup":
                backup_path = ams.backup_data()
                flash(f"Backup created successfully: {os.path.basename(backup_path)}", "success")
            elif action == "restore":
                backup_folder = request.form.get("backup_folder")
                full_backup_path = os.path.join(os.path.dirname(ams.data_dir), backup_folder)
                ams.restore_data_from_backup(full_backup_path)
                flash(f"Database restored from backup: {backup_folder}", "success")
        except Exception as e:
            flash(f"Data action failed: {str(e)}", "danger")
        return redirect(url_for("data_management"))

    # Get list of existing backups
    parent_dir = os.path.dirname(ams.data_dir)
    backups = []
    if os.path.exists(parent_dir):
        for item in os.listdir(parent_dir):
            if item.startswith("backup_"):
                path = os.path.join(parent_dir, item)
                stat = os.stat(path)
                backups.append({
                    "folder": item,
                    "time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
                
    # Read the log file contents
    log_content = ""
    log_path = os.path.join(ams.data_dir, "system_log.txt")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            # Get last 100 lines
            lines = f.readlines()
            log_content = "".join(lines[-100:])
            
    return render_template("data.html", backups=sorted(backups, key=lambda b: b["folder"], reverse=True), log_content=log_content)

@app.route("/qr")
def qr_attendance():
    today_str = datetime.today().strftime("%Y-%m-%d")
    return render_template("qr_attendance.html", date=today_str, students=ams.students)

@app.route("/qr/scan", methods=["POST"])
def qr_scan_api():
    # Simulated API endpoint for QR scanning
    try:
        student_id = request.json.get("student_id")
        date_str = request.json.get("date", datetime.today().strftime("%Y-%m-%d"))
        marked_by = request.json.get("marked_by", "QR Scanner")
        
        # Verify student exists
        student = ams.get_student(student_id)
        
        # Mark attendance
        att = ams.mark_attendance(student_id, date_str, "Present", marked_by)
        ams.save_data()
        
        return jsonify({
            "success": True, 
            "message": f"Present marked for {student.name} ({student_id}) via QR Code."
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/face")
def face_attendance():
    today_str = datetime.today().strftime("%Y-%m-%d")
    return render_template("face_attendance.html", date=today_str, students=ams.students)

@app.route("/face/detect", methods=["POST"])
def face_detect_api():
    # Simulated API endpoint for face matching
    try:
        # Client sends photo as dataURL in JSON
        # Since running OpenCV on arbitrary browser video can be complex,
        # we simulate a 90% chance of successful matching a student from list
        import random
        student_id = request.json.get("student_id")
        date_str = request.json.get("date", datetime.today().strftime("%Y-%m-%d"))
        marked_by = request.json.get("marked_by", "Face Camera")
        
        if not student_id:
            # Pick a random student for the mockup scan behavior
            if not ams.students:
                raise AttendanceSystemError("No students in the database.")
            student_id = random.choice(ams.students).student_id
            
        student = ams.get_student(student_id)
        
        # Mark present
        att = ams.mark_attendance(student_id, date_str, "Present", marked_by)
        ams.save_data()
        
        return jsonify({
            "success": True, 
            "student_id": student.student_id,
            "name": student.name,
            "course": student.course,
            "message": f"Face matched! {student.name} marked Present."
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
