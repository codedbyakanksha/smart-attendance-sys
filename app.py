
import os
import json
import base64
import secrets
import re
from datetime import datetime, date
from functools import wraps

import cv2
import numpy as np

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", secrets.token_hex(32)
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FACES_DIR = os.path.join(BASE_DIR, "faces")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FACES_DIR, exist_ok=True)

STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.json")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")

# LBPH face recognition settings
CONFIDENCE_LIMIT = 70

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

recognizer = None
face_labels = {}


# -------------------------------
# JSON FUNCTIONS
# -------------------------------

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else default
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    os.replace(temp_path, path)


def get_students():
    return read_json(STUDENTS_FILE, [])


def get_attendance():
    return read_json(ATTENDANCE_FILE, [])


# Create JSON files if they do not exist
if not os.path.exists(STUDENTS_FILE):
    write_json(STUDENTS_FILE, [])

if not os.path.exists(ATTENDANCE_FILE):
    write_json(ATTENDANCE_FILE, [])


# -------------------------------
# LOGIN PROTECTION
# -------------------------------

def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return function(*args, **kwargs)

    return wrapper


@app.route("/")
def home():
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("dashboard"))

        flash("Invalid username or password", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------------------
# FACE RECOGNITION FUNCTIONS
# -------------------------------

def get_face_crop(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    if len(faces) == 0:
        return None, "No face detected. Try again."

    if len(faces) > 1:
        return None, "More than one face detected. Only one person should be in the frame."

    x, y, w, h = faces[0]

    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (200, 200))

    return face, None


def decode_image(data_url):
    if not data_url:
        return None

    if not isinstance(data_url, str):
        return None

    if not data_url.startswith("data:image/"):
        return None

    try:
        encoded = data_url.split(",", 1)[1]

        if len(encoded) > 7_000_000:
            return None

        image_bytes = base64.b64decode(encoded, validate=True)

        if len(image_bytes) > 5_000_000:
            return None

        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        return image

    except Exception:
        return None


def train_face_model():
    global recognizer, face_labels

    recognizer = None
    face_labels = {}

    if not hasattr(cv2, "face"):
        print("OpenCV contrib package is required for LBPH.")
        return

    images = []
    labels = []

    students = get_students()
    label_number = 0

    for student in students:
        if not student.get("face_enrolled"):
            continue

        face_file = student.get("face_file")

        if not face_file:
            continue

        # Prevent filenames from escaping the faces folder
        if os.path.basename(face_file) != face_file:
            continue

        image_path = os.path.join(FACES_DIR, face_file)

        if not os.path.exists(image_path):
            continue

        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

        if image is None:
            continue

        image = cv2.resize(image, (200, 200))

        images.append(image)
        labels.append(label_number)
        face_labels[label_number] = student["id"]

        label_number += 1

    if not images:
        print("No enrolled face samples available.")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(images, np.array(labels, dtype=np.int32))

    print("Face recognition model trained successfully.")


# -------------------------------
# DASHBOARD
# -------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    students = get_students()
    records = get_attendance()

    today = date.today().isoformat()

    todays_records = [
        r for r in records
        if r.get("date") == today
        and r.get("status") == "Present"
    ]

    present = len(set(r["student_id"] for r in todays_records))
    total = len(students)
    absent = max(total - present, 0)

    rate = round((present / total) * 100, 1) if total else 0

    recent = sorted(
        records,
        key=lambda r: (r.get("date", ""), r.get("time", "")),
        reverse=True
    )[:7]

    return render_template(
        "dashboard.html",
        total=total,
        present=present,
        absent=absent,
        rate=rate,
        recent=recent,
        today=today
    )


# -------------------------------
# STUDENTS
# -------------------------------

@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":

        name = request.form.get("name", "").strip()
        roll = request.form.get("roll", "").strip()
        course = request.form.get("course", "").strip()
        email = request.form.get("email", "").strip()

        face_image = request.form.get("face_image", "")
        consent = request.form.get("consent") == "yes"

        if not name or not roll:
            flash("Name and roll number are required.", "error")
            return redirect(url_for("students"))

        all_students = get_students()

        if any(s.get("roll") == roll for s in all_students):
            flash("Roll number already exists.", "error")
            return redirect(url_for("students"))

        student_id = secrets.token_hex(6)

        student = {
            "id": student_id,
            "name": name,
            "roll": roll,
            "course": course,
            "email": email,
            "created_at": datetime.now().isoformat(),
            "face_enrolled": False,
            "face_file": None
        }

        # Face data is saved only with explicit consent
        if face_image and consent:

            image = decode_image(face_image)

            if image is None:
                flash("Invalid or oversized face image.", "error")
                return redirect(url_for("students"))

            face_crop, error = get_face_crop(image)

            if error:
                flash(error, "error")
                return redirect(url_for("students"))

            face_filename = student_id + ".jpg"
            face_path = os.path.join(FACES_DIR, face_filename)

            success = cv2.imwrite(face_path, face_crop)

            if not success:
                flash("Could not save face image.", "error")
                return redirect(url_for("students"))

            student["face_enrolled"] = True
            student["face_file"] = face_filename

        elif face_image and not consent:
            flash("Face enrollment requires consent.", "error")
            return redirect(url_for("students"))

        all_students.append(student)
        write_json(STUDENTS_FILE, all_students)

        train_face_model()

        flash("Student added successfully.", "success")
        return redirect(url_for("students"))

    return render_template(
        "students.html",
        students=get_students()
    )


# -------------------------------
# DELETE STUDENT
# -------------------------------

@app.route("/students/<student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id):

    students_list = get_students()

    student = next(
        (s for s in students_list if s.get("id") == student_id),
        None
    )

    if student is None:
        flash("Student not found.", "error")
        return redirect(url_for("students"))

    face_file = student.get("face_file")

    if face_file and os.path.basename(face_file) == face_file:
        face_path = os.path.join(FACES_DIR, face_file)

        if os.path.exists(face_path):
            os.remove(face_path)

    students_list = [
        s for s in students_list
        if s.get("id") != student_id
    ]

    write_json(STUDENTS_FILE, students_list)

    # Historical attendance records are retained
    train_face_model()

    flash("Student deleted successfully.", "success")

    return redirect(url_for("students"))


# -------------------------------
# ATTENDANCE PAGE
# -------------------------------

@app.route("/attendance")
@login_required
def attendance():
    return render_template(
        "attendance.html",
        students=get_students()
    )


# -------------------------------
# CAMERA FACE RECOGNITION API
# -------------------------------

@app.route("/api/recognize", methods=["POST"])
@login_required
def recognize_face():

    data = request.get_json(silent=True) or {}
    image = decode_image(data.get("image"))

    if image is None:
        return jsonify({
            "ok": False,
            "message": "Camera image is missing or invalid."
        }), 400

    face_crop, error = get_face_crop(image)

    if error:
        return jsonify({
            "ok": False,
            "message": error
        }), 400

    if recognizer is None:
        return jsonify({
            "ok": False,
            "message": "No enrolled face samples. Add a student with consent first."
        }), 400

    try:
        label, confidence = recognizer.predict(face_crop)

    except cv2.error:
        return jsonify({
            "ok": False,
            "message": "Face recognition failed. Please try again."
        }), 400

    if confidence > CONFIDENCE_LIMIT:
        return jsonify({
            "ok": False,
            "message": "Face not recognized. Please verify manually."
        }), 200

    student_id = face_labels.get(label)

    student = next(
        (s for s in get_students() if s.get("id") == student_id),
        None
    )

    if student is None:
        return jsonify({
            "ok": False,
            "message": "Student record not found."
        }), 404

    records = get_attendance()
    today = date.today().isoformat()

    already_marked = any(
        r.get("student_id") == student_id
        and r.get("date") == today
        and r.get("status") == "Present"
        for r in records
    )

    if already_marked:
        return jsonify({
            "ok": False,
            "message": student["name"] + " is already marked present today."
        })

    new_record = {
        "id": secrets.token_hex(6),
        "student_id": student_id,
        "student_name": student["name"],
        "date": today,
        "time": datetime.now().strftime("%H:%M:%S"),
        "status": "Present",
        "method": "Face Recognition"
    }

    records.append(new_record)
    write_json(ATTENDANCE_FILE, records)

    return jsonify({
        "ok": True,
        "message": "Attendance marked for " + student["name"]
    })


# -------------------------------
# ATTENDANCE RECORDS
# -------------------------------

@app.route("/records")
@login_required
def records():

    all_records = sorted(
        get_attendance(),
        key=lambda r: (r.get("date", ""), r.get("time", "")),
        reverse=True
    )

    return render_template(
        "records.html",
        records=all_records
    )


# -------------------------------
# ANALYSIS
# -------------------------------

@app.route("/analysis")
@login_required
def analysis():

    students_list = get_students()
    records_list = get_attendance()

    total = len(students_list)

    dates = set(
        r.get("date") for r in records_list
        if r.get("status") == "Present"
    )

    total_days = len(dates)
    summary = []

    for student in students_list:

        attended = len(set(
            r.get("date")
            for r in records_list
            if r.get("student_id") == student["id"]
            and r.get("status") == "Present"
        ))

        percent = (
            round((attended / total_days) * 100, 1)
            if total_days else 0
        )

        summary.append({
            "name": student["name"],
            "roll": student["roll"],
            "attended": attended,
            "percent": percent
        })

    return render_template(
        "analysis.html",
        summary=summary,
        total=total
    )


# -------------------------------
# PERFORMANCE
# -------------------------------

@app.route("/performance")
@login_required
def performance():

    students_list = get_students()
    records_list = get_attendance()

    dates = set(
        r.get("date") for r in records_list
        if r.get("status") == "Present"
    )

    total_days = len(dates)
    ranked = []

    for student in students_list:

        attended = len(set(
            r.get("date")
            for r in records_list
            if r.get("student_id") == student["id"]
            and r.get("status") == "Present"
        ))

        rate = (
            round((attended / total_days) * 100, 1)
            if total_days else 0
        )

        ranked.append({
            "name": student["name"],
            "roll": student["roll"],
            "attended": attended,
            "rate": rate
        })

    ranked.sort(key=lambda x: x["rate"], reverse=True)

    return render_template(
        "performance.html",
        ranked=ranked
    )


# -------------------------------
# START APPLICATION
# -------------------------------

if __name__ == "__main__":

    train_face_model()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
