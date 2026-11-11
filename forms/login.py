# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import secrets

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFormLayout, QMessageBox
)

from database.database import get_connection


def make_password_hash(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 150000
    )
    return digest.hex(), salt.hex()


def verify_password(password, stored_hash, stored_salt):
    try:
        salt = bytes.fromhex(stored_salt)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, 150000
        ).hex()
        return hmac.compare_digest(digest, stored_hash)
    except Exception:
        return False


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user = None
        self.first_run = False
        self.setWindowTitle("ورود به سامانه یسنا")
        self.setFixedSize(440, 390)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("""
            QDialog { background:#F3F6F9; color:#183B56; }
            QLabel { font-family:Tahoma; font-size:10pt; }
            QLineEdit { background:white; border:1px solid #CBD5DF;
                border-radius:6px; padding:9px; min-height:24px;
                font-family:Tahoma; }
            QPushButton { background:#183B56; color:white; border:0;
                border-radius:6px; padding:9px 16px; min-height:28px;
                font-family:Tahoma; font-weight:bold; }
            QPushButton:hover { background:#285577; }
        """)
        self.build_ui()
        self.check_first_run()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 25, 28, 25)
        root.setSpacing(14)

        title = QLabel("✦  YASNA")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size:25pt;font-weight:bold;color:#D4AF37;padding:8px;"
        )
        root.addWidget(title)

        self.heading = QLabel("ورود به سامانه مدیریت مکاتبات")
        self.heading.setAlignment(Qt.AlignCenter)
        self.heading.setStyleSheet(
            "font-size:13pt;font-weight:bold;color:#183B56;"
        )
        root.addWidget(self.heading)

        self.form_box = QWidget()
        self.form_layout = QFormLayout(self.form_box)
        self.form_layout.setSpacing(11)

        self.username = QLineEdit()
        self.username.setPlaceholderText("نام کاربری")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("رمز عبور")

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("نام و نام خانوادگی مدیر")
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setPlaceholderText("تکرار رمز عبور")

        self.form_layout.addRow("نام کاربری:", self.username)
        self.form_layout.addRow("رمز عبور:", self.password)
        root.addWidget(self.form_box)

        self.btn_login = QPushButton("ورود")
        self.btn_login.clicked.connect(self.login)
        root.addWidget(self.btn_login)

        self.password.returnPressed.connect(self.login)
        self.username.returnPressed.connect(self.password.setFocus)

    def check_first_run(self):
        conn = get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM AppUsers "
                "WHERE Role='مدیر سیستم' AND IsActive=1"
            ).fetchone()[0]
        finally:
            conn.close()

        self.first_run = count == 0
        if self.first_run:
            self.setFixedSize(460, 470)
            self.heading.setText("ایجاد مدیر سیستم اولیه")
            self.form_layout.addRow("نام نمایشی:", self.full_name)
            self.form_layout.addRow("تکرار رمز:", self.confirm_password)
            self.btn_login.setText("ایجاد مدیر و ورود")
            self.password.returnPressed.disconnect()
            self.confirm_password.returnPressed.connect(self.create_admin)

    def login(self):
        if self.first_run:
            self.create_admin()
            return

        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(
                self, "ورود", "نام کاربری و رمز عبور را وارد کنید."
            )
            return

        conn = get_connection()
        try:
            row = conn.execute("""
                SELECT UserID, Username, FullName, PasswordHash,
                       PasswordSalt, Role, IsActive, Permissions
                FROM AppUsers WHERE Username = ?
            """, (username,)).fetchone()
        finally:
            conn.close()

        if not row or not row[6] or not verify_password(
            password, row[3], row[4]
        ):
            QMessageBox.warning(
                self, "ورود ناموفق",
                "نام کاربری یا رمز عبور نادرست است، یا حساب غیرفعال شده است."
            )
            self.password.clear()
            self.password.setFocus()
            return

        try:
            permissions = json.loads(row[7] or "{}")
        except Exception:
            permissions = {}

        self.user = {
            "UserID": int(row[0]),
            "Username": row[1],
            "FullName": row[2],
            "Role": row[5],
            "IsActive": bool(row[6]),
            "Permissions": permissions
        }
        self.accept()

    def create_admin(self):
        username = self.username.text().strip()
        full_name = self.full_name.text().strip()
        password = self.password.text()
        confirm = self.confirm_password.text()

        if not username or not full_name:
            QMessageBox.warning(
                self, "اطلاعات ناقص",
                "نام کاربری و نام نمایشی مدیر را وارد کنید."
            )
            return
        if len(password) < 8:
            QMessageBox.warning(
                self, "رمز عبور",
                "رمز عبور مدیر باید حداقل ۸ نویسه داشته باشد."
            )
            return
        if password != confirm:
            QMessageBox.warning(
                self, "تأیید رمز عبور",
                "رمز عبور و تکرار آن یکسان نیستند."
            )
            return

        password_hash, salt = make_password_hash(password)
        permissions = {
            "dashboard": True, "letters": True, "postal": True,
            "persons": True, "reminders": True, "reports": True,
            "settings": True
        }

        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO AppUsers
                (Username, FullName, PasswordHash, PasswordSalt,
                 Role, IsActive, Permissions)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (
                username, full_name, password_hash, salt,
                "مدیر سیستم",
                json.dumps(permissions, ensure_ascii=False)
            ))
            conn.commit()
        except Exception as error:
            conn.rollback()
            QMessageBox.critical(
                self, "خطا در ایجاد مدیر",
                "ایجاد مدیر سیستم انجام نشد.\n{}".format(error)
            )
            return
        finally:
            conn.close()

        conn = get_connection()
        try:
            user_id_row = conn.execute(
                "SELECT UserID FROM AppUsers WHERE Username=?",
                (username,)
            ).fetchone()
        finally:
            conn.close()

        self.user = {
            "UserID": int(user_id_row[0]) if user_id_row else None,
            "Username": username,
            "FullName": full_name, "Role": "مدیر سیستم",
            "IsActive": True, "Permissions": permissions
        }
        QMessageBox.information(
            self, "مدیر سیستم",
            "حساب مدیر اولیه ایجاد شد. اکنون وارد یسنا می‌شوید."
        )
        self.accept()
