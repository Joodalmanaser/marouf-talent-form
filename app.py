# -*- coding: utf-8 -*-
"""
معروف – نموذج دعم المواهب الكروية للأطفال
Flask backend: يستقبل الطلبات، يخزّنها في قاعدة بيانات SQLite،
ويوفّر لوحة إدارة بسيطة مع تصدير Excel، ودعم اختياري لـ Google Sheets.
"""

import os
import io
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, send_file, abort
)
from openpyxl import Workbook

# ---------------------------------------------------------------------------
# إعدادات عامة
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "submissions.db")

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
# مفتاح الجلسة – غيّره في الإنتاج عبر متغيّر البيئة SECRET_KEY
app.secret_key = os.environ.get("SECRET_KEY", "marouf-dev-secret-change-me")

# كلمة مرور لوحة الإدارة – غيّرها عبر متغيّر البيئة ADMIN_PASSWORD
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "marouf2025")

# الأعمدة بالترتيب (المفتاح في القاعدة -> العنوان العربي للعرض/التصدير)
FIELDS = [
    ("full_name",     "الاسم الرباعي"),
    ("birth_date",    "تاريخ الميلاد"),
    ("guardian_phone", "رقم هاتف ولي الأمر"),
    ("address",       "مكان السكن"),
    ("email",         "البريد الإلكتروني"),
    ("position",      "المركز"),
    ("status",        "الحالة"),
    ("club",          "النادي / الأكاديمية"),
    ("experience",    "سنوات الخبرة"),
    ("level",         "تقييم المستوى"),
    ("tournaments",   "شارك في بطولات"),
    ("achievements",  "الإنجازات"),
    ("created_at",    "تاريخ الإرسال"),
]

REQUIRED = ["full_name", "birth_date", "guardian_phone", "address"]


# ---------------------------------------------------------------------------
# قاعدة البيانات
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            guardian_phone TEXT NOT NULL,
            address TEXT NOT NULL,
            email TEXT,
            position TEXT,
            status TEXT,
            club TEXT,
            experience TEXT,
            level TEXT,
            tournaments TEXT,
            achievements TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# Google Sheets (اختياري) – يعمل تلقائياً إذا توفّرت بيانات الاعتماد
# ---------------------------------------------------------------------------
def append_to_google_sheet(row_dict):
    """
    يضيف سطراً إلى Google Sheets إذا كان متغيّر البيئة
    GOOGLE_SHEET_ID و ملف الاعتماد متوفّرين. وإلا يتجاهل بصمت.
    التفاصيل في README.
    """
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    creds_file = os.environ.get("GOOGLE_CREDS_FILE", os.path.join(BASE_DIR, "credentials.json"))
    if not sheet_id or not os.path.exists(creds_file):
        return  # غير مفعّل

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1

        # كتابة رؤوس الأعمدة مرة واحدة إذا كانت الورقة فارغة
        if not sheet.get_all_values():
            sheet.append_row([ar for _, ar in FIELDS])

        sheet.append_row([row_dict.get(key, "") for key, _ in FIELDS])
    except Exception as e:  # لا نوقف الحفظ المحلي بسبب خطأ في الشيت
        app.logger.warning("Google Sheets sync failed: %s", e)


# ---------------------------------------------------------------------------
# أدوات مساعدة
# ---------------------------------------------------------------------------
def clean(text, max_len=500):
    if text is None:
        return ""
    return str(text).strip()[:max_len]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# المسارات العامة
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or request.form.to_dict()

    record = {key: clean(data.get(key, "")) for key, _ in FIELDS if key != "created_at"}

    # تحقّق من الحقول المطلوبة
    missing = [ar for key, ar in FIELDS if key in REQUIRED and not record.get(key)]
    if missing:
        return jsonify({
            "ok": False,
            "message": "الرجاء تعبئة الحقول المطلوبة: " + "، ".join(missing)
        }), 400

    # تحقّق بسيط من رقم الهاتف
    phone_digits = re.sub(r"\D", "", record.get("guardian_phone", ""))
    if len(phone_digits) < 7:
        return jsonify({"ok": False, "message": "رقم الهاتف غير صحيح."}), 400

    record["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute(
        """
        INSERT INTO submissions
        (full_name, birth_date, guardian_phone, address, email, position,
         status, club, experience, level, tournaments, achievements, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record["full_name"], record["birth_date"], record["guardian_phone"],
            record["address"], record["email"], record["position"],
            record["status"], record["club"], record["experience"],
            record["level"], record["tournaments"], record["achievements"],
            record["created_at"],
        ),
    )
    conn.commit()
    conn.close()

    # مزامنة اختيارية مع Google Sheets
    append_to_google_sheet(record)

    return jsonify({"ok": True, "message": "شكراً لك، تم استلام بياناتك بنجاح."})


# ---------------------------------------------------------------------------
# لوحة الإدارة
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(request.args.get("next") or url_for("admin"))
        error = "كلمة المرور غير صحيحة."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM submissions ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("admin.html", rows=rows, fields=FIELDS, total=len(rows))


@app.route("/admin/download")
@login_required
def download():
    conn = get_db()
    rows = conn.execute("SELECT * FROM submissions ORDER BY id ASC").fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "الطلبات"
    ws.sheet_view.rightToLeft = True

    ws.append(["#"] + [ar for _, ar in FIELDS])
    for i, r in enumerate(rows, start=1):
        ws.append([i] + [r[key] for key, _ in FIELDS])

    # عرض أعمدة معقول
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"marouf_submissions_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
