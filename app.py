import os
import csv
import io
from datetime import date, datetime
from functools import wraps

import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-secret")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "college_attendance"),
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    # Create the database separately first using schema.sql.
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('admin','teacher') NOT NULL DEFAULT 'teacher',
            full_name VARCHAR(120) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_no VARCHAR(40) UNIQUE NOT NULL,
            full_name VARCHAR(120) NOT NULL,
            course VARCHAR(100) NOT NULL,
            year_level VARCHAR(30) NOT NULL,
            email VARCHAR(150),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(40) UNIQUE NOT NULL,
            name VARCHAR(120) NOT NULL,
            course VARCHAR(100) NOT NULL,
            teacher_id INT NULL,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            subject_id INT NOT NULL,
            attendance_date DATE NOT NULL,
            status ENUM('Present','Absent','Leave') NOT NULL,
            marked_by INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_student_subject_day (student_id, subject_id, attendance_date),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (marked_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    conn.commit()
    # Create a default admin only if the user table is empty.
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (%s,%s,'admin',%s)",
            ("admin", generate_password_hash("Admin@123"), "System Administrator")
        )
        conn.commit()
    cur.close()
    conn.close()

def db_query(sql, params=(), one=False, many=False):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    result = cur.fetchall() if many else cur.fetchone() if one else None
    cur.close()
    conn.close()
    return result

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Administrator access is required for that action.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapped

@app.template_filter("datefmt")
def datefmt(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return value

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db_query("SELECT * FROM users WHERE username=%s", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash("Welcome back, " + user["full_name"] + "!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    students = db_query("SELECT COUNT(*) AS n FROM students WHERE active=1", one=True)["n"]
    subjects = db_query("SELECT COUNT(*) AS n FROM subjects", one=True)["n"]
    teachers = db_query("SELECT COUNT(*) AS n FROM users WHERE role='teacher'", one=True)["n"]
    today_count = db_query("SELECT COUNT(*) AS n FROM attendance WHERE attendance_date=%s", (date.today(),), one=True)["n"]
    recent = db_query("""
        SELECT a.attendance_date, a.status, s.full_name AS student_name,
               s.roll_no, sub.name AS subject_name
        FROM attendance a
        JOIN students s ON s.id=a.student_id
        JOIN subjects sub ON sub.id=a.subject_id
        ORDER BY a.attendance_date DESC, a.id DESC LIMIT 8
    """, many=True)
    return render_template("dashboard.html", students=students, subjects=subjects,
                           teachers=teachers, today_count=today_count, recent=recent)

@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":
        if session.get("role") != "admin":
            flash("Only an administrator can add students.", "danger")
            return redirect(url_for("students"))
        roll = request.form.get("roll_no", "").strip()
        name = request.form.get("full_name", "").strip()
        course = request.form.get("course", "").strip()
        year_level = request.form.get("year_level", "").strip()
        email = request.form.get("email", "").strip() or None
        if not all([roll, name, course, year_level]):
            flash("Roll number, name, course and year are required.", "danger")
        else:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""INSERT INTO students (roll_no,full_name,course,year_level,email)
                               VALUES (%s,%s,%s,%s,%s)""",
                            (roll, name, course, year_level, email))
                conn.commit()
                cur.close()
                conn.close()
                flash("Student added successfully.", "success")
                return redirect(url_for("students"))
            except Error as exc:
                flash("Could not add student. Check that the roll number is unique. " + str(exc), "danger")
    rows = db_query("SELECT * FROM students ORDER BY course, year_level, roll_no", many=True)
    return render_template("students.html", students=rows)

@app.route("/students/<int:student_id>/toggle", methods=["POST"])
@admin_required
def toggle_student(student_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE students SET active = NOT active WHERE id=%s", (student_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Student status updated.", "success")
    return redirect(url_for("students"))

@app.route("/subjects", methods=["GET", "POST"])
@login_required
def subjects():
    if request.method == "POST":
        if session.get("role") != "admin":
            flash("Only an administrator can add subjects.", "danger")
            return redirect(url_for("subjects"))
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        teacher_id = request.form.get("teacher_id") or None
        if not all([code, name, course]):
            flash("Subject code, name and course are required.", "danger")
        else:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("INSERT INTO subjects (code,name,course,teacher_id) VALUES (%s,%s,%s,%s)",
                            (code, name, course, teacher_id))
                conn.commit()
                cur.close()
                conn.close()
                flash("Subject added successfully.", "success")
                return redirect(url_for("subjects"))
            except Error as exc:
                flash("Could not add subject. Check that the subject code is unique. " + str(exc), "danger")
    rows = db_query("""
        SELECT sub.*, u.full_name AS teacher_name
        FROM subjects sub LEFT JOIN users u ON u.id=sub.teacher_id
        ORDER BY sub.course, sub.name
    """, many=True)
    teachers = db_query("SELECT id, full_name FROM users WHERE role='teacher' ORDER BY full_name", many=True)
    return render_template("subjects.html", subjects=rows, teachers=teachers)

@app.route("/teachers", methods=["GET", "POST"])
@admin_required
def teachers():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not all([full_name, username, password]):
            flash("All teacher fields are required.", "danger")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
        else:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("INSERT INTO users (username,password_hash,role,full_name) VALUES (%s,%s,'teacher',%s)",
                            (username, generate_password_hash(password), full_name))
                conn.commit()
                cur.close()
                conn.close()
                flash("Teacher account created.", "success")
                return redirect(url_for("teachers"))
            except Error:
                flash("Username already exists or account could not be created.", "danger")
    rows = db_query("SELECT id, full_name, username, created_at FROM users WHERE role='teacher' ORDER BY full_name", many=True)
    return render_template("teachers.html", teachers=rows)

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    subjects = db_query("SELECT id, code, name, course FROM subjects ORDER BY course,name", many=True)
    selected_subject = request.values.get("subject_id", "")
    selected_date = request.values.get("attendance_date", date.today().isoformat())
    roster = []
    existing = {}
    if selected_subject:
        roster = db_query("""SELECT id, roll_no, full_name FROM students
                             WHERE active=1 AND course=(SELECT course FROM subjects WHERE id=%s)
                             ORDER BY roll_no""", (selected_subject,), many=True)
        records = db_query("""SELECT student_id,status FROM attendance
                              WHERE subject_id=%s AND attendance_date=%s""",
                           (selected_subject, selected_date), many=True)
        existing = {r["student_id"]: r["status"] for r in records}
    if request.method == "POST":
        if not selected_subject:
            flash("Please select a subject.", "danger")
            return redirect(url_for("attendance"))
        try:
            chosen_date = date.fromisoformat(selected_date)
            if chosen_date > date.today():
                flash("Attendance cannot be recorded for a future date.", "danger")
                return redirect(url_for("attendance", subject_id=selected_subject, attendance_date=selected_date))
        except ValueError:
            flash("Please select a valid date.", "danger")
            return redirect(url_for("attendance"))
        conn = get_db()
        cur = conn.cursor()
        try:
            for student in roster:
                status = request.form.get("status_" + str(student["id"]), "Absent")
                if status not in ("Present", "Absent", "Leave"):
                    status = "Absent"
                cur.execute("""
                    INSERT INTO attendance (student_id,subject_id,attendance_date,status,marked_by)
                    VALUES (%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE status=VALUES(status), marked_by=VALUES(marked_by)
                """, (student["id"], int(selected_subject), chosen_date, status, session["user_id"]))
            conn.commit()
            flash("Attendance saved successfully.", "success")
            return redirect(url_for("attendance", subject_id=selected_subject, attendance_date=selected_date))
        except Error as exc:
            conn.rollback()
            flash("Attendance could not be saved: " + str(exc), "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("attendance.html", subjects=subjects, roster=roster,
                           existing=existing, selected_subject=str(selected_subject),
                           selected_date=selected_date, today=date.today().isoformat())

@app.route("/reports")
@login_required
def reports():
    course = request.args.get("course", "").strip()
    params = []
    where = ""
    if course:
        where = "WHERE s.course=%s"
        params.append(course)
    rows = db_query(f"""
        SELECT s.roll_no, s.full_name, s.course, s.year_level,
               sub.code AS subject_code, sub.name AS subject_name,
               COUNT(a.id) AS total_classes,
               SUM(a.status='Present') AS present_count,
               SUM(a.status='Absent') AS absent_count,
               SUM(a.status='Leave') AS leave_count,
               ROUND(100.0 * SUM(a.status='Present') / NULLIF(COUNT(a.id),0), 2) AS percentage
        FROM students s
        LEFT JOIN attendance a ON a.student_id=s.id
        LEFT JOIN subjects sub ON sub.id=a.subject_id
        {where}
        GROUP BY s.id, sub.id
        ORDER BY s.course, s.roll_no, sub.name
    """, tuple(params), many=True)
    courses = db_query("SELECT DISTINCT course FROM students ORDER BY course", many=True)
    return render_template("reports.html", rows=rows, courses=courses, selected_course=course)

@app.route("/reports/export")
@login_required
def export_report():
    course = request.args.get("course", "").strip()
    params = []
    where = ""
    if course:
        where = "WHERE s.course=%s"
        params.append(course)
    rows = db_query(f"""
        SELECT s.roll_no, s.full_name, s.course, s.year_level,
               sub.code AS subject_code, sub.name AS subject_name,
               COUNT(a.id) AS total_classes,
               COALESCE(SUM(a.status='Present'),0) AS present_count,
               COALESCE(SUM(a.status='Absent'),0) AS absent_count,
               COALESCE(SUM(a.status='Leave'),0) AS leave_count,
               ROUND(100.0 * SUM(a.status='Present') / NULLIF(COUNT(a.id),0), 2) AS percentage
        FROM students s
        LEFT JOIN attendance a ON a.student_id=s.id
        LEFT JOIN subjects sub ON sub.id=a.subject_id
        {where}
        GROUP BY s.id, sub.id
        ORDER BY s.course, s.roll_no, sub.name
    """, tuple(params), many=True)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Student", "Course", "Year", "Subject Code", "Subject",
                     "Total Recorded Classes", "Present", "Absent", "Leave", "Attendance %"])
    for r in rows:
        writer.writerow([r["roll_no"], r["full_name"], r["course"], r["year_level"],
                         r["subject_code"] or "", r["subject_name"] or "", r["total_classes"],
                         r["present_count"] or 0, r["absent_count"] or 0, r["leave_count"] or 0,
                         r["percentage"] if r["percentage"] is not None else "N/A"])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=attendance_report.csv"})

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        user = db_query("SELECT password_hash FROM users WHERE id=%s", (session["user_id"],), one=True)
        if not check_password_hash(user["password_hash"], current):
            flash("Current password is incorrect.", "danger")
        elif len(new) < 8:
            flash("New password must contain at least 8 characters.", "danger")
        else:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                        (generate_password_hash(new), session["user_id"]))
            conn.commit()
            cur.close()
            conn.close()
            flash("Password changed successfully.", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")

@app.cli.command("init-db")
def init_db_command():
    """Create application tables and a default administrator."""
    try:
        init_db()
        print("Database initialized. Default login: admin / Admin@123")
        print("Change the default password after signing in.")
    except Error as exc:
        print("Database initialization failed:", exc)

if __name__ == "__main__":
    app.run(debug=True)
