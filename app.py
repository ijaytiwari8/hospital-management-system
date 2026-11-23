from flask import (

             Flask, render_template, request, redirect,

             url_for, flash, session

)

from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection

import os

from functools import wraps

app = Flask(

             __name__,

             template_folder=os.path.join(

                 os.path.dirname(os.path.abspath(__file__)),

                 "templates"

             )

)

app.secret_key = "hospital_project_secret_key"

# ==================================================

# HOME

# ==================================================

@app.route("/")

def home():

             return render_template("index.html")

# ==================================================

# PATIENT REGISTRATION

# ==================================================

@app.route("/patients", methods=["GET", "POST"])

def patients():

             if request.method == "POST":

                 name = request.form.get("name", "").strip()

                 age = request.form.get("age") or None

                 gender = request.form.get("gender") or None

                 phone = request.form.get("phone", "").strip()

                 address = request.form.get("address") or None

                 disease = request.form.get("disease") or None

                 password = request.form.get("password", "")

                 confirm_password = request.form.get("confirm_password", "")

                 if not all([name, phone, password, confirm_password]):

                     flash("Please fill all required fields.")

                     return redirect(url_for("patients"))

                 if password != confirm_password:

                     flash("Passwords do not match!")

                     return redirect(url_for("patients"))

                 if len(password) < 8:

                     flash("Password must contain at least 8 characters.")

                     return redirect(url_for("patients"))

                 connection = get_connection()

                 if connection is None:

                     return "Database connection failed.", 500

                 cursor = None

                 try:

                     cursor = connection.cursor()

                     cursor.execute(

                         "SELECT patient_id FROM patients WHERE phone = %s",

                         (phone,)

                     )

                     if cursor.fetchone():

                         flash("Phone number already registered. Please login.")

                         return redirect(url_for("patients"))

                     password_hash = generate_password_hash(password)

                     cursor.execute("""

                         INSERT INTO patients

                         (name, age, gender, phone, address, disease, password_hash)

                         VALUES (%s, %s, %s, %s, %s, %s, %s)

                     """, (

                         name, age, gender, phone,

                         address, disease, password_hash

                     ))

                     connection.commit()

                     flash("Registration successful! Please login.")

                     return redirect(url_for("patient_login"))

                 except Exception:

                     connection.rollback()

                     app.logger.exception("Patient registration failed")

                     return "Unable to register patient.", 500

                 finally:

                     if cursor:

                         cursor.close()

                     connection.close()

             return render_template("patients.html")

# Admin Login

@app.route("/admin-login", methods=["GET", "POST"])

def admin_login():

             if session.get("admin_logged_in"):

                 return redirect(url_for("dashboard"))

             if request.method == "POST":

                 username = request.form.get("username", "")

                 password = request.form.get("password", "")

                 admin_username = os.environ.get("ADMIN_USERNAME")

                 admin_password = os.environ.get("ADMIN_PASSWORD")

                 if not admin_username or not admin_password:

                     return "Admin credentials are not configured.", 500

                 if username == admin_username and password == admin_password:

                     session.clear()

                     session["admin_logged_in"] = True

                     return redirect(url_for("dashboard"))

                 flash("Invalid username or password!")

             return render_template("admin_login.html")

# Admin Authentication

def admin_required(view_function):

             @wraps(view_function)

             def wrapped_view(*args, **kwargs):

                 if not session.get("admin_logged_in"):

                     return redirect(url_for("admin_login"))

                 return view_function(*args, **kwargs)

             return wrapped_view

# Admin Logout

@app.route("/admin-logout")

@admin_required

def admin_logout():

             session.pop("admin_logged_in", None)

             return redirect(url_for("admin_login"))

# ==================================================

# PATIENT LOGIN

# ==================================================

@app.route("/patient-login", methods=["GET", "POST"])

def patient_login():

             if request.method == "POST":

                 phone = request.form.get("phone", "").strip()

                 password = request.form.get("password", "")

                 if not phone or not password:

                     flash("Please enter phone number and password.")

                     return redirect(url_for("patient_login"))

                 connection = get_connection()

                 if connection is None:

                     return "Database connection failed.", 500

                 cursor = None

                 try:

                     cursor = connection.cursor(dictionary=True)

                     cursor.execute("""

                         SELECT patient_id, name, phone, password_hash

                         FROM patients

                         WHERE phone = %s

                     """, (phone,))

                     patient = cursor.fetchone()

                     if (

                         patient

                         and patient["password_hash"]

                         and check_password_hash(

                             patient["password_hash"], password

                         )

                     ):

                         session.pop("doctor_id", None)

                         session.pop("patient_id", None)

                         session["patient_id"] = patient["patient_id"]

                         flash("Welcome! Login successful.")

                         return redirect(url_for("patient_dashboard"))

                     flash("Invalid phone number or password.")

                 except Exception:

                     app.logger.exception("Patient login failed")

                     return "Unable to login.", 500

                 finally:

                     if cursor:

                         cursor.close()

                     connection.close()

             return render_template("patient_login.html")

# ==================================================

# PATIENT DASHBOARD

# ==================================================

@app.route("/patient-dashboard")

def patient_dashboard():

             if "patient_id" not in session:

                 return redirect(url_for("patient_login"))

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 patient_id = session["patient_id"]

                 cursor.execute("""

                     SELECT patient_id, name, age, gender,

                            phone, address, disease

                     FROM patients

                     WHERE patient_id = %s

                 """, (patient_id,))

                 patient = cursor.fetchone()

                 if patient is None:

                     session.pop("patient_id", None)

                     return redirect(url_for("patient_login"))

                 cursor.execute("""

                     SELECT COUNT(*) AS total

                     FROM appointments

                     WHERE patient_id = %s

                 """, (patient_id,))

                 total_appointments = cursor.fetchone()["total"]

                 cursor.execute("""

                     SELECT COUNT(*) AS total

                     FROM appointments

                     WHERE patient_id = %s

                     AND status IN ('Pending', 'Scheduled', 'Accepted')

                     AND appointment_date >= CURDATE()

                 """, (patient_id,))

                 upcoming_appointments = cursor.fetchone()["total"]

                 cursor.execute("""

                     SELECT COUNT(*) AS total

                     FROM appointments

                     WHERE patient_id = %s

                     AND status = 'Completed'

                 """, (patient_id,))

                 completed_appointments = cursor.fetchone()["total"]

                 cursor.execute("""

                     SELECT

                         a.appointment_id,

                         a.appointment_date,

                         a.appointment_time,

                         a.status,

                         d.name AS doctor_name,

                         d.specialization

                     FROM appointments a

                     JOIN doctors d ON a.doctor_id = d.doctor_id

                     WHERE a.patient_id = %s

                     ORDER BY a.appointment_date DESC,

                              a.appointment_time DESC

                 """, (patient_id,))

                 appointments = cursor.fetchall()

                 return render_template(

                     "patient_dashboard.html",

                     patient=patient,

                     appointments=appointments,

                     total_appointments=total_appointments,

                     upcoming_appointments=upcoming_appointments,

                     completed_appointments=completed_appointments

                 )

             except Exception:

                 app.logger.exception("Patient dashboard failed")

                 return "Unable to load patient dashboard.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================
# PATIENT EDIT PROFILE
# ==================================================

@app.route("/patient-edit-profile", methods=["GET", "POST"])
def patient_edit_profile():
    if "patient_id" not in session:
        return redirect(url_for("patient_login"))

    patient_id = session["patient_id"]
    connection = get_connection()
    if connection is None:
        return "Database connection failed.", 500

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            age = request.form.get("age") or None
            gender = request.form.get("gender") or None
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip() or None
            disease = request.form.get("disease", "").strip() or None

            if not name or not phone:
                flash("Name and phone number are required.")
                return redirect(url_for("patient_edit_profile"))

            if age:
                try:
                    age_value = int(age)
                    if age_value < 1 or age_value > 120:
                        raise ValueError
                except (TypeError, ValueError):
                    flash("Please enter a valid age between 1 and 120.")
                    return redirect(url_for("patient_edit_profile"))

            cursor.execute(
                "SELECT patient_id FROM patients WHERE phone = %s AND patient_id != %s",
                (phone, patient_id)
            )
            if cursor.fetchone():
                flash("This phone number is already registered.")
                return redirect(url_for("patient_edit_profile"))

            cursor.execute("""
                UPDATE patients
                SET name = %s, age = %s, gender = %s, phone = %s,
                    address = %s, disease = %s
                WHERE patient_id = %s
            """, (name, age, gender, phone, address, disease, patient_id))
            connection.commit()
            flash("Profile updated successfully!")
            return redirect(url_for("patient_dashboard"))

        cursor.execute("""
            SELECT name, age, gender, phone, address, disease
            FROM patients WHERE patient_id = %s
        """, (patient_id,))
        patient = cursor.fetchone()
        if patient is None:
            session.pop("patient_id", None)
            flash("Patient account not found. Please login again.")
            return redirect(url_for("patient_login"))

        return render_template("patient_edit_profile.html", patient=patient)

    except Exception:
        connection.rollback()
        app.logger.exception("Patient profile update failed")
        return "Unable to update patient profile.", 500
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ==================================================

# PATIENT LOGOUT

# ==================================================

@app.route("/patient-logout")

def patient_logout():

             session.pop("patient_id", None)

             flash("Patient logged out successfully!")

             return redirect(url_for("patient_login"))

# ==================================================

# ADMIN DASHBOARD

# ==================================================

@app.route("/dashboard")

@admin_required

def dashboard():

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 cursor.execute("SELECT COUNT(*) AS total FROM patients")

                 total_patients = cursor.fetchone()["total"]

                 cursor.execute("SELECT COUNT(*) AS total FROM doctors")

                 total_doctors = cursor.fetchone()["total"]

                 cursor.execute("SELECT COUNT(*) AS total FROM appointments")

                 total_appointments = cursor.fetchone()["total"]

                 cursor.execute("""

                     SELECT

                         COALESCE(SUM(status = 'Pending'), 0) AS pending,

                         COALESCE(SUM(status = 'Scheduled'), 0) AS scheduled,

                         COALESCE(SUM(status = 'Accepted'), 0) AS accepted,

                         COALESCE(SUM(status = 'Rejected'), 0) AS rejected,

                         COALESCE(SUM(status = 'Completed'), 0) AS completed

                     FROM appointments

                 """)

                 status_counts = cursor.fetchone()

                 cursor.execute("""

                     SELECT patient_id, name, age, gender, phone

                     FROM patients

                     ORDER BY patient_id DESC

                     LIMIT 5

                 """)

                 recent_patients = cursor.fetchall()

                 cursor.execute("""

                     SELECT

                         a.appointment_id,

                         p.name AS patient_name,

                         d.name AS doctor_name,

                         a.appointment_date,

                         a.appointment_time,

                         a.status

                     FROM appointments a

                     JOIN patients p ON a.patient_id = p.patient_id

                     JOIN doctors d ON a.doctor_id = d.doctor_id

                     ORDER BY a.appointment_id DESC

                     LIMIT 5

                 """)

                 recent_appointments = cursor.fetchall()

                 return render_template(

                     "dashboard.html",

                     total_patients=total_patients,

                     total_doctors=total_doctors,

                     total_appointments=total_appointments,

                     status_counts=status_counts,

                     recent_patients=recent_patients,

                     recent_appointments=recent_appointments

                 )

             except Exception:

                 app.logger.exception("Admin dashboard failed")

                 return "Unable to load dashboard.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

@app.route("/reports")

@admin_required

def reports():

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 cursor.execute("SELECT COUNT(*) AS total FROM patients")

                 total_patients = cursor.fetchone()["total"]

                 cursor.execute("SELECT COUNT(*) AS total FROM doctors")

                 total_doctors = cursor.fetchone()["total"]

                 cursor.execute("SELECT COUNT(*) AS total FROM appointments")

                 total_appointments = cursor.fetchone()["total"]

                 cursor.execute("""

                     SELECT

                         COALESCE(SUM(status = 'Pending'), 0) AS pending,

                         COALESCE(SUM(status = 'Scheduled'), 0) AS scheduled,

                         COALESCE(SUM(status = 'Accepted'), 0) AS accepted,

                         COALESCE(SUM(status = 'Rejected'), 0) AS rejected,

                         COALESCE(SUM(status = 'Completed'), 0) AS completed

                     FROM appointments

                 """)

                 status_counts = cursor.fetchone()

                 cursor.execute("""

                     SELECT DATE_FORMAT(appointment_date, '%b %Y') AS month_label,

                            COUNT(*) AS total

                     FROM appointments

                     WHERE appointment_date >= DATE_SUB(CURDATE(), INTERVAL 5 MONTH)

                     GROUP BY YEAR(appointment_date), MONTH(appointment_date),

                              DATE_FORMAT(appointment_date, '%b %Y')

                     ORDER BY YEAR(appointment_date), MONTH(appointment_date)

                 """)

                 monthly_appointments = cursor.fetchall()

                 cursor.execute("""

                     SELECT d.name AS doctor_name,

                            d.specialization,

                            COUNT(a.appointment_id) AS total_appointments

                     FROM doctors d

                     LEFT JOIN appointments a ON a.doctor_id = d.doctor_id

                     GROUP BY d.doctor_id, d.name, d.specialization

                     ORDER BY total_appointments DESC, d.name ASC

                 """)

                 doctor_stats = cursor.fetchall()

                 return render_template(

                     "reports.html",

                     total_patients=total_patients,

                     total_doctors=total_doctors,

                     total_appointments=total_appointments,

                     status_counts=status_counts,

                     monthly_appointments=monthly_appointments,

                     doctor_stats=doctor_stats

                 )

             except Exception:

                 app.logger.exception("Reports page failed")

                 return "Unable to load reports.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

@app.route("/patients-list")

@admin_required

def patients_list():

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 cursor.execute("""

                     SELECT patient_id, name, age, gender,

                            phone, address, disease, created_at

                     FROM patients

                     ORDER BY patient_id DESC

                 """)

                 patients = cursor.fetchall()

                 return render_template(

                     "patients_list.html",

                     patients=patients

                 )

             except Exception:

                 app.logger.exception("Unable to fetch patients")

                 return "Unable to load patients.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# DOCTOR REGISTRATION

# ==================================================

@app.route("/doctors", methods=["GET", "POST"])

@admin_required

def doctors():

             if request.method == "POST":

                 name = request.form.get("name", "").strip()

                 specialization = request.form.get("specialization")

                 phone = request.form.get("phone")

                 email = request.form.get("email")

                 available_days = request.form.get("available_days")

                 if not name:

                     return "Doctor name is required.", 400

                 connection = get_connection()

                 if connection is None:

                     return "Database connection failed.", 500

                 cursor = None

                 try:

                     cursor = connection.cursor()

                     cursor.execute("""

                         INSERT INTO doctors

                         (name, specialization, phone, email, available_days)

                         VALUES (%s, %s, %s, %s, %s)

                     """, (

                         name, specialization, phone,

                         email, available_days

                     ))

                     connection.commit()

                     flash("Doctor added successfully!")

                     return redirect(url_for("doctors"))

                 except Exception:

                     connection.rollback()

                     app.logger.exception("Doctor registration failed")

                     return "Unable to add doctor.", 500

                 finally:

                     if cursor:

                         cursor.close()

                     connection.close()

             return render_template("doctors.html")

# ==================================================

# ADMIN APPOINTMENT BOOKING

# ==================================================

@app.route("/appointments", methods=["GET", "POST"])

@admin_required

def appointments():

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 if request.method == "POST":

                     patient_id = request.form.get("patient_id")

                     doctor_id = request.form.get("doctor_id")

                     appointment_date = request.form.get("appointment_date")

                     appointment_time = request.form.get("appointment_time")

                     if not all([

                         patient_id, doctor_id,

                         appointment_date, appointment_time

                     ]):

                         flash("Please fill all appointment details.")

                         return redirect(url_for("appointments"))

                     cursor.execute("""

                         SELECT doctor_id

                         FROM doctors

                         WHERE doctor_id = %s

                         AND availability_status = 'Available'

                     """, (doctor_id,))

                     available_doctor = cursor.fetchone()

                     if not available_doctor:

                         flash("This doctor is currently unavailable.")

                         return redirect(url_for("appointments"))

                     cursor.execute("""

                         INSERT INTO appointments

                         (patient_id, doctor_id, appointment_date, appointment_time)

                         VALUES (%s, %s, %s, %s)

                     """, (

                         patient_id, doctor_id,

                         appointment_date, appointment_time

                     ))

                     connection.commit()

                     flash("Appointment booked successfully!")

                     return redirect(url_for("appointments"))

                 cursor.execute("""

                     SELECT patient_id, name

                     FROM patients

                     ORDER BY name

                 """)

                 patients_data = cursor.fetchall()

                 cursor.execute("""

                     SELECT doctor_id, name, specialization

                     FROM doctors

                     WHERE availability_status = 'Available'

                     ORDER BY name

                 """)

                 doctors_data = cursor.fetchall()

                 return render_template(

                     "appointments.html",

                     patients=patients_data,

                     doctors=doctors_data

                 )

             except Exception:

                 connection.rollback()

                 app.logger.exception("Appointment booking failed")

                 return "Unable to process appointment.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# APPOINTMENT LIST

# ==================================================

@app.route("/appointments-list")

@admin_required

def appointments_list():

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 cursor.execute("""

                     SELECT

                         a.appointment_id,

                         p.name AS patient_name,

                         d.name AS doctor_name,

                         a.appointment_date,

                         a.appointment_time,

                         a.status

                     FROM appointments a

                     JOIN patients p ON a.patient_id = p.patient_id

                     JOIN doctors d ON a.doctor_id = d.doctor_id

                     ORDER BY a.appointment_id DESC

                 """)

                 appointments_data = cursor.fetchall()

                 return render_template(

                     "appointments_list.html",

                     appointments=appointments_data

                 )

             except Exception:

                 app.logger.exception("Unable to fetch appointments")

                 return "Unable to load appointments.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

@app.route("/admin-update-appointment-status/<int:appointment_id>", methods=["POST"])

@admin_required

def admin_update_appointment_status(appointment_id):

             allowed_statuses = ["Accepted", "Rejected", "Completed"]

             new_status = request.form.get("status")

             if new_status not in allowed_statuses:

                 return "Invalid appointment status.", 400

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor()

                 cursor.execute("""

                     UPDATE appointments

                     SET status = %s

                     WHERE appointment_id = %s

                 """, (new_status, appointment_id))

                 if cursor.rowcount == 0:

                     connection.rollback()

                     return "Appointment not found.", 404

                 connection.commit()

                 return redirect(url_for("appointments_list"))

             except Exception:

                 connection.rollback()

                 app.logger.exception("Admin appointment status update failed")

                 return "Unable to update appointment status.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# DOCTOR LIST

# ==================================================

@app.route("/doctors-list")

@admin_required

def doctors_list():

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 cursor.execute("SELECT * FROM doctors")

                 doctors_data = cursor.fetchall()

                 return render_template(

                     "doctors_list.html",

                     doctors=doctors_data

                 )

             except Exception:

                 app.logger.exception("Unable to fetch doctors")

                 return "Unable to load doctors.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# EDIT DOCTOR

# ==================================================

@app.route("/doctors/edit/<int:doctor_id>", methods=["GET", "POST"])

@admin_required

def edit_doctor(doctor_id):

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 if request.method == "POST":

                     name = request.form.get("name", "").strip()

                     specialization = request.form.get("specialization")

                     phone = request.form.get("phone")

                     email = request.form.get("email")

                     available_days = request.form.get("available_days")

                     if not name:

                         return "Doctor name is required.", 400

                     cursor.execute("""

                         UPDATE doctors

                         SET name=%s,

                             specialization=%s,

                             phone=%s,

                             email=%s,

                             available_days=%s

                         WHERE doctor_id=%s

                     """, (

                         name, specialization, phone,

                         email, available_days, doctor_id

                     ))

                     connection.commit()

                     flash("Doctor details updated successfully!")

                     return redirect(url_for("doctors_list"))

                 cursor.execute(

                     "SELECT * FROM doctors WHERE doctor_id=%s",

                     (doctor_id,)

                 )

                 doctor = cursor.fetchone()

                 if doctor is None:

                     return "Doctor not found.", 404

                 return render_template("edit_doctor.html", doctor=doctor)

             except Exception:

                 connection.rollback()

                 app.logger.exception("Doctor update failed")

                 return "Unable to update doctor.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# DELETE DOCTOR

# ==================================================

@app.route("/doctors/delete/<int:doctor_id>", methods=["POST"])

@admin_required

def delete_doctor(doctor_id):

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor()

                 cursor.execute("""

                     SELECT COUNT(*)

                     FROM appointments

                     WHERE doctor_id=%s

                 """, (doctor_id,))

                 result = cursor.fetchone()

                 if result[0] > 0:

                     flash("Doctor cannot be deleted because appointments exist.")

                     return redirect(url_for("doctors_list"))

                 cursor.execute(

                     "DELETE FROM doctors WHERE doctor_id=%s",

                     (doctor_id,)

                 )

                 connection.commit()

                 flash("Doctor deleted successfully!")

                 return redirect(url_for("doctors_list"))

             except Exception:

                 connection.rollback()

                 app.logger.exception("Doctor deletion failed")

                 return "Unable to delete doctor.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# DOCTOR LOGIN

# ==================================================

@app.route("/doctor-login", methods=["GET", "POST"])

def doctor_login():

             if request.method == "POST":

                 email = request.form.get("email", "").strip()

                 password = request.form.get("password", "")

                 connection = get_connection()

                 if connection is None:

                     return "Database connection failed.", 500

                 cursor = None

                 try:

                     cursor = connection.cursor(dictionary=True)

                     cursor.execute(

                         "SELECT * FROM doctors WHERE email = %s",

                         (email,)

                     )

                     doctor = cursor.fetchone()

                     if (

                         doctor

                         and doctor["password_hash"]

                         and check_password_hash(

                             doctor["password_hash"], password

                         )

                     ):

                         session.pop("patient_id", None)

                         session.pop("doctor_id", None)

                         session["doctor_id"] = doctor["doctor_id"]

                         flash("Login successful!")

                         return redirect(url_for("doctor_dashboard"))

                     flash("Invalid email or password.")

                 except Exception:

                     app.logger.exception("Doctor login failed")

                     return "Unable to login.", 500

                 finally:

                     if cursor:

                         cursor.close()

                     connection.close()

             return render_template("doctor_login.html")

# ==================================================

# DOCTOR DASHBOARD

# ==================================================

@app.route("/doctor-dashboard")

def doctor_dashboard():

             if "doctor_id" not in session:

                 return redirect(url_for("doctor_login"))

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 cursor.execute("""

                     SELECT

                         doctor_id,

                         name,

                         email,

                         specialization,

                         availability_status

                     FROM doctors

                     WHERE doctor_id = %s

                 """, (session["doctor_id"],))

                 doctor = cursor.fetchone()

                 if doctor is None:

                     session.pop("doctor_id", None)

                     return redirect(url_for("doctor_login"))

                 return render_template(

                     "doctor_dashboard.html",

                     doctor=doctor

                 )

             except Exception:

                 app.logger.exception("Doctor dashboard failed")

                 return "Unable to load doctor dashboard.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================

# DOCTOR LOGOUT

# ==================================================

@app.route("/doctor-logout")

def doctor_logout():

             session.pop("doctor_id", None)

             flash("Logged out successfully!")

             return redirect(url_for("doctor_login"))

# ==================================================

# DOCTOR AVAILABILITY

# ==================================================

@app.route("/doctor-availability", methods=["POST"])

def doctor_availability():

             if "doctor_id" not in session:

                 return redirect(url_for("doctor_login"))

             status = request.form.get("availability_status")

             if status not in ["Available", "Unavailable"]:

                 flash("Invalid availability status!")

                 return redirect(url_for("doctor_dashboard"))

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = connection.cursor()

             try:

                 cursor.execute("""

                     UPDATE doctors

                     SET availability_status = %s

                     WHERE doctor_id = %s

                 """, (status, session["doctor_id"]))

                 connection.commit()

                 flash("Availability updated successfully!")

             except Exception:

                 connection.rollback()

                 app.logger.exception("Availability update failed")

                 flash("Error updating availability!")

             finally:

                 cursor.close()

                 connection.close()

             return redirect(url_for("doctor_dashboard"))

# ==================================================

# DOCTOR APPOINTMENTS

# ==================================================

@app.route("/doctor-appointments")

def doctor_appointments():

             if "doctor_id" not in session:

                 return redirect(url_for("doctor_login"))

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = connection.cursor(dictionary=True)

             try:

                 cursor.execute("""

                     SELECT

                         a.appointment_id,

                         a.appointment_date,

                         a.appointment_time,

                         a.status,

                         p.name AS patient_name,

                         p.age,

                         p.gender,

                         p.phone,

                         p.disease

                     FROM appointments a

                     JOIN patients p ON a.patient_id = p.patient_id

                     WHERE a.doctor_id = %s

                     ORDER BY a.appointment_date DESC,

                              a.appointment_time DESC

                 """, (session["doctor_id"],))

                 appointments_data = cursor.fetchall()

             finally:

                 cursor.close()

                 connection.close()

             return render_template(

                 "doctor_appointments.html",

                 appointments=appointments_data

             )

# ==================================================

# UPDATE APPOINTMENT STATUS - DOCTOR

# ==================================================

@app.route(

             "/update-appointment-status/<int:appointment_id>",

             methods=["POST"]

)

def update_appointment_status(appointment_id):

             if "doctor_id" not in session:

                 return redirect(url_for("doctor_login"))

             status = request.form.get("status")

             allowed_statuses = ["Accepted", "Rejected", "Completed"]

             if status not in allowed_statuses:

                 flash("Invalid appointment status!")

                 return redirect(url_for("doctor_appointments"))

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = connection.cursor()

             try:

                 cursor.execute("""

                     UPDATE appointments

                     SET status = %s

                     WHERE appointment_id = %s

                     AND doctor_id = %s

                 """, (

                     status,

                     appointment_id,

                     session["doctor_id"]

                 ))

                 connection.commit()

                 if cursor.rowcount > 0:

                     flash("Appointment status updated successfully!")

                 else:

                     flash("Appointment not found!")

             except Exception:

                 connection.rollback()

                 app.logger.exception("Appointment status update failed")

                 flash("Unable to update appointment status!")

             finally:

                 cursor.close()

                 connection.close()

             return redirect(url_for("doctor_appointments"))

# ==================================================

# PATIENT BOOK APPOINTMENT

# ==================================================

@app.route("/patient-book-appointment", methods=["GET", "POST"])

def patient_book_appointment():

             if "patient_id" not in session:

                 flash("Please login first.")

                 return redirect(url_for("patient_login"))

             connection = get_connection()

             if connection is None:

                 return "Database connection failed.", 500

             cursor = None

             try:

                 cursor = connection.cursor(dictionary=True)

                 if request.method == "POST":

                     doctor_id = request.form.get("doctor_id")

                     appointment_date = request.form.get("appointment_date")

                     appointment_time = request.form.get("appointment_time")

                     if not all([

                         doctor_id,

                         appointment_date,

                         appointment_time

                     ]):

                         flash("Please fill all appointment details.")

                         return redirect(url_for("patient_book_appointment"))

                     cursor.execute("""

                         SELECT doctor_id

                         FROM doctors

                         WHERE doctor_id = %s

                         AND availability_status = 'Available'

                     """, (doctor_id,))

                     doctor = cursor.fetchone()

                     if not doctor:

                         flash("Selected doctor is unavailable.")

                         return redirect(url_for("patient_book_appointment"))

                     cursor.execute("""

                         INSERT INTO appointments

                         (

                             patient_id,

                             doctor_id,

                             appointment_date,

                             appointment_time,

                             status

                         )

                         VALUES (%s, %s, %s, %s, %s)

                     """, (

                         session["patient_id"],

                         doctor_id,

                         appointment_date,

                         appointment_time,

                         "Pending"

                     ))

                     connection.commit()

                     flash("Appointment booked successfully!")

                     return redirect(url_for("patient_dashboard"))

                 cursor.execute("""

                     SELECT doctor_id, name, specialization

                     FROM doctors

                     WHERE availability_status = 'Available'

                     ORDER BY name

                 """)

                 doctors_data = cursor.fetchall()

                 return render_template(

                     "patient_book_appointment.html",

                     doctors=doctors_data

                 )

             except Exception:

                 connection.rollback()

                 app.logger.exception("Patient appointment booking failed")

                 return "Unable to process appointment.", 500

             finally:

                 if cursor:

                     cursor.close()

                 connection.close()

# ==================================================
# PATIENT MEDICAL HISTORY
# ==================================================

# DOCTOR - ADD MEDICAL HISTORY
@app.route("/doctor/add-medical-history/<int:appointment_id>", methods=["GET", "POST"])
def add_medical_history(appointment_id):

    if "doctor_id" not in session:
        return redirect(url_for("doctor_login"))

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                a.appointment_id,
                a.patient_id,
                a.status,
                p.name AS patient_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.appointment_id = %s
            AND a.doctor_id = %s
            AND a.status = 'Completed'
        """, (appointment_id, session["doctor_id"]))

        appointment = cursor.fetchone()

        if appointment is None:
            flash("Completed appointment not found.")
            return redirect(url_for("doctor_appointments"))

        if request.method == "POST":

            diagnosis = request.form.get("diagnosis", "").strip()
            symptoms = request.form.get("symptoms", "").strip()
            treatment = request.form.get("treatment", "").strip()
            notes = request.form.get("notes", "").strip()

            if not diagnosis:
                flash("Diagnosis is required.")
                return redirect(url_for(
                    "add_medical_history",
                    appointment_id=appointment_id
                ))

            cursor.execute("""
                INSERT INTO medical_history
                (patient_id, doctor_id, appointment_id,
                 diagnosis, symptoms, treatment, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                appointment["patient_id"],
                session["doctor_id"],
                appointment_id,
                diagnosis,
                symptoms,
                treatment,
                notes
            ))

            connection.commit()

            flash("Medical history added successfully!")
            return redirect(url_for("doctor_appointments"))

        return render_template(
            "add_medical_history.html",
            appointment=appointment
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Medical history insertion failed")
        return "Unable to add medical history.", 500

    finally:
        if cursor:
            cursor.close()
        connection.close()


# PATIENT - VIEW OWN MEDICAL HISTORY
@app.route("/patient-medical-history")
def patient_medical_history():

    if "patient_id" not in session:
        return redirect(url_for("patient_login"))

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                mh.*,
                d.name AS doctor_name,
                d.specialization
            FROM medical_history mh
            JOIN doctors d ON mh.doctor_id = d.doctor_id
            WHERE mh.patient_id = %s
            ORDER BY mh.created_at DESC
        """, (session["patient_id"],))

        history = cursor.fetchall()

        return render_template(
            "patient_medical_history.html",
            history=history
        )

    except Exception:
        app.logger.exception("Patient medical history loading failed")
        return "Unable to load medical history.", 500

    finally:
        if cursor:
            cursor.close()
        connection.close()


# ADMIN - VIEW ALL MEDICAL HISTORY
@app.route("/admin-medical-history")
@admin_required
def admin_medical_history():

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                mh.*,
                p.name AS patient_name,
                d.name AS doctor_name
            FROM medical_history mh
            JOIN patients p ON mh.patient_id = p.patient_id
            JOIN doctors d ON mh.doctor_id = d.doctor_id
            ORDER BY mh.created_at DESC
        """)

        history = cursor.fetchall()

        return render_template(
            "admin_medical_history.html",
            history=history
        )

    except Exception:
        app.logger.exception("Admin medical history loading failed")
        return "Unable to load medical history.", 500

    finally:
        if cursor:
            cursor.close()
        connection.close()

# ==================================================
# DOCTOR ADD DIGITAL PRESCRIPTION
# ==================================================

@app.route(
    "/doctor/add-prescription/<int:appointment_id>",
    methods=["GET", "POST"]
)
def add_prescription(appointment_id):

    if "doctor_id" not in session:
        return redirect(url_for("doctor_login"))

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                a.appointment_id,
                a.patient_id,
                p.name AS patient_name,
                p.age,
                p.gender,
                p.phone,
                d.name AS doctor_name,
                d.specialization

            FROM appointments a

            JOIN patients p ON a.patient_id = p.patient_id
            JOIN doctors d ON a.doctor_id = d.doctor_id

            WHERE a.appointment_id = %s
            AND a.doctor_id = %s
            AND a.status = 'Completed'
        """, (appointment_id, session["doctor_id"]))

        appointment = cursor.fetchone()

        if appointment is None:
            flash("Completed appointment not found.")
            return redirect(url_for("doctor_appointments"))

        if request.method == "POST":

            diagnosis = request.form.get("diagnosis", "").strip()
            instructions = request.form.get("instructions", "").strip()

            medicine_names = request.form.getlist("medicine_name[]")
            dosages = request.form.getlist("dosage[]")
            frequencies = request.form.getlist("frequency[]")
            durations = request.form.getlist("duration[]")
            quantities = request.form.getlist("quantity[]")
            medicine_instructions = request.form.getlist("medicine_instructions[]")

            if not diagnosis:
                flash("Diagnosis is required.")
                return redirect(
                    url_for("add_prescription", appointment_id=appointment_id)
                )

            medicines = []

            for i, name in enumerate(medicine_names):
                name = name.strip()

                if not name:
                    continue

                medicines.append((
                    name,
                    dosages[i].strip() if i < len(dosages) else None,
                    frequencies[i].strip() if i < len(frequencies) else None,
                    durations[i].strip() if i < len(durations) else None,
                    quantities[i].strip() if i < len(quantities) else None,
                    medicine_instructions[i].strip()
                    if i < len(medicine_instructions) else None
                ))

            if not medicines:
                flash("Please add at least one medicine.")
                return redirect(
                    url_for("add_prescription", appointment_id=appointment_id)
                )

            try:
                cursor.execute("""
                    INSERT INTO prescriptions
                    (patient_id, doctor_id, appointment_id, diagnosis, instructions)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    appointment["patient_id"],
                    session["doctor_id"],
                    appointment_id,
                    diagnosis,
                    instructions or None
                ))

                prescription_id = cursor.lastrowid

                for medicine in medicines:
                    cursor.execute("""
                        INSERT INTO prescription_items
                        (
                            prescription_id,
                            medicine_name,
                            dosage,
                            frequency,
                            duration,
                            quantity,
                            medicine_instructions
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (prescription_id, *medicine))

                connection.commit()

                flash("Prescription created successfully!")

                return redirect(url_for("doctor_appointments"))

            except Exception:
                connection.rollback()
                app.logger.exception("Prescription creation failed")
                return "Unable to save prescription.", 500

        return render_template(
            "add_prescription.html",
            appointment=appointment
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Add prescription page failed")
        return "Unable to load prescription page.", 500

    finally:
        if cursor:
            cursor.close()

        connection.close()

# ==================================================
# PATIENT VIEW DIGITAL PRESCRIPTIONS
# ==================================================

@app.route("/patient-prescriptions")
def patient_prescriptions():

    if "patient_id" not in session:
        flash("Please login first.")
        return redirect(url_for("patient_login"))

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        patient_id = session["patient_id"]

        cursor.execute("""
            SELECT
                p.prescription_id,
                p.patient_id,
                p.appointment_id,
                p.diagnosis,
                p.instructions,
                p.created_at,
                d.name AS doctor_name,
                d.specialization,
                a.appointment_date

            FROM prescriptions p

            JOIN doctors d
                ON p.doctor_id = d.doctor_id

            LEFT JOIN appointments a
                ON p.appointment_id = a.appointment_id

            WHERE p.patient_id = %s

            ORDER BY p.created_at DESC
        """, (patient_id,))

        prescriptions = cursor.fetchall()

        for prescription in prescriptions:

            cursor.execute("""
                SELECT
                    medicine_name,
                    dosage,
                    frequency,
                    duration,
                    quantity,
                    medicine_instructions

                FROM prescription_items

                WHERE prescription_id = %s

                ORDER BY item_id
            """, (prescription["prescription_id"],))

            prescription["medicines"] = cursor.fetchall()

        return render_template(
            "patient_prescriptions.html",
            prescriptions=prescriptions
        )

    except Exception:
        app.logger.exception("Patient prescriptions loading failed")
        return "Unable to load prescriptions.", 500

    finally:
        if cursor:
            cursor.close()

        connection.close()
        # ==================================================
# ADMIN GENERATE BILL
# ==================================================

@app.route("/generate-bill", methods=["GET", "POST"])
@admin_required
def generate_bill():

    from decimal import Decimal, InvalidOperation

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":

            appointment_id = request.form.get("appointment_id", "").strip()

            try:
                appointment_id = int(appointment_id)

                consultation_fee = Decimal(
                    request.form.get("consultation_fee", "0")
                )

                medicine_charges = Decimal(
                    request.form.get("medicine_charges", "0")
                )

                other_charges = Decimal(
                    request.form.get("other_charges", "0")
                )

                if not all([
                    consultation_fee.is_finite(),
                    medicine_charges.is_finite(),
                    other_charges.is_finite()
                ]):
                    raise ValueError

                if min(
                    consultation_fee,
                    medicine_charges,
                    other_charges
                ) < 0:
                    raise ValueError

            except (ValueError, InvalidOperation):
                flash("Please enter valid appointment and charge details.")
                return redirect(url_for("generate_bill"))

            cursor.execute("""
                SELECT
                    a.appointment_id,
                    a.patient_id,
                    a.status,
                    p.name AS patient_name

                FROM appointments a

                JOIN patients p
                    ON a.patient_id = p.patient_id

                WHERE a.appointment_id = %s
                AND a.status = 'Completed'
            """, (appointment_id,))

            appointment = cursor.fetchone()

            if appointment is None:
                flash("Please select a valid completed appointment.")
                return redirect(url_for("generate_bill"))

            cursor.execute("""
                SELECT bill_id
                FROM bills
                WHERE appointment_id = %s
            """, (appointment_id,))

            existing_bill = cursor.fetchone()

            if existing_bill:
                flash("A bill already exists for this appointment.")
                return redirect(url_for("generate_bill"))

            total_amount = (
                consultation_fee +
                medicine_charges +
                other_charges
            )

            notes = request.form.get("notes", "").strip() or None

            cursor.execute("""
                INSERT INTO bills (
                    patient_id,
                    appointment_id,
                    consultation_fee,
                    medicine_charges,
                    other_charges,
                    total_amount,
                    payment_status,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
            """, (
                appointment["patient_id"],
                appointment_id,
                consultation_fee,
                medicine_charges,
                other_charges,
                total_amount,
                notes
            ))

            connection.commit()

            flash(
                f"Bill generated successfully! Total amount: ₹{total_amount}"
            )

            return redirect(url_for("generate_bill"))

        # Show only completed appointments without an existing bill

        cursor.execute("""
            SELECT
                a.appointment_id,
                a.appointment_date,
                a.appointment_time,
                p.patient_id,
                p.name AS patient_name

            FROM appointments a

            JOIN patients p
                ON a.patient_id = p.patient_id

            LEFT JOIN bills b
                ON a.appointment_id = b.appointment_id

            WHERE a.status = 'Completed'
            AND b.bill_id IS NULL

            ORDER BY a.appointment_date DESC,
                     a.appointment_time DESC
        """)

        appointments_for_billing = cursor.fetchall()

        return render_template(
            "generate_bill.html",
            appointments=appointments_for_billing
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Bill generation failed")
        return "Unable to generate bill.", 500

    finally:
        if cursor:
            cursor.close()

        connection.close()
@app.route("/patient-bills")
def patient_bills():

    if "patient_id" not in session:
        flash("Please login first.")
        return redirect(url_for("patient_login"))

    connection = get_connection()

    if connection is None:
        return "Database connection failed.", 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        patient_id = session["patient_id"]

        cursor.execute("""
            SELECT
                b.bill_id,
                b.appointment_id,
                b.consultation_fee,
                b.medicine_charges,
                b.other_charges,
                b.total_amount,
                b.payment_status,
                b.payment_method,
                b.notes,
                b.created_at,
                a.appointment_date,
                a.appointment_time,
                d.name AS doctor_name
            FROM bills b
            LEFT JOIN appointments a
                ON b.appointment_id = a.appointment_id
            LEFT JOIN doctors d
                ON a.doctor_id = d.doctor_id
            WHERE b.patient_id = %s
            ORDER BY b.created_at DESC
        """, (patient_id,))

        bills = cursor.fetchall()

        return render_template(
            "patient_bills.html",
            bills=bills
        )

    except Exception:
        app.logger.exception("Patient bills loading failed")
        return "Unable to load your bills.", 500

    finally:
        if cursor:
            cursor.close()
        connection.close()




# ==================================================

# RUN APPLICATION

# ==================================================

if __name__ == "__main__":

             app.run(debug=True, port=5001)
