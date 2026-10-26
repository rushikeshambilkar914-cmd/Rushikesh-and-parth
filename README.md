# College Attendance Management System

A final-year project built with Python, Flask, MySQL, HTML and CSS.

## Features
- Admin and teacher sign-in
- Password hashing and role-based access
- Student and subject management
- Teacher account creation (admin only)
- Date- and subject-wise attendance (Present, Absent, Leave)
- Duplicate protection for one student/subject/date
- Attendance percentage reports and CSV export
- Change-password page
- Responsive interface

## Requirements
- Python 3.10 or newer
- MySQL Server
- pip

## Setup (Windows)
1. Install Python and MySQL Server.
2. Open MySQL Workbench or the MySQL command-line client.
3. Run the contents of `schema.sql` to create the database.
4. Open a terminal in this project folder.
5. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\\Scripts\\activate
   ```
   On macOS/Linux use `source venv/bin/activate`.
6. Install packages:
   ```bash
   pip install -r requirements.txt
   ```
7. Set database environment variables. In Windows Command Prompt:
   ```bat
   set DB_HOST=localhost
   set DB_USER=root
   set DB_PASSWORD=your_mysql_password
   set DB_NAME=college_attendance
   set SECRET_KEY=replace-with-a-long-random-secret
   ```
   On PowerShell, use `$env:DB_PASSWORD="your_mysql_password"` and similar `$env:NAME="value"` commands.
8. Initialize the tables and default administrator:
   ```bash
   flask --app app init-db
   ```
9. Start the web application:
   ```bash
   flask --app app run --debug
   ```
10. Open `http://127.0.0.1:5000` in your browser.

## First login
- Username: `admin`
- Password: `Admin@123`

Immediately use the Change Password link to replace the default password. Do not deploy this demo with the default secret key or default password.

## Suggested first-use workflow
1. Sign in as administrator and change the password.
2. Add teacher accounts under Teachers.
3. Add students under Students.
4. Add subjects under Subjects and optionally assign a teacher.
5. Open Attendance, choose a subject and date, mark each student, and save.
6. Use Reports to view percentages or export CSV.

## Notes / limitations
- Attendance is grouped by the student's course matching the selected subject's course.
- A recorded class session is represented by one subject and date. If a subject has multiple sessions per day, add a session identifier to the schema and application before using it.
- Teachers can mark attendance and view reports. Admin-only pages create students, subjects, and teachers.
- This is a local educational project starter. Before real deployment, add CSRF protection, audit logging, backups, HTTPS, stronger configuration management, and tests.

## Troubleshooting
- `Access denied for user`: check `DB_USER` and `DB_PASSWORD`.
- `Unknown database`: run `schema.sql` first.
- `ModuleNotFoundError`: activate the virtual environment and run `pip install -r requirements.txt`.
- Port already in use: run `flask --app app run --port 5001`.
