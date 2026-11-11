# -*- coding: utf-8 -*-
import os
import json
import shutil
import hashlib
import secrets
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTabWidget, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt

from database.database import get_connection, DB_PATH


class SettingsUsersForm(QWidget):
    def __init__(self, parent=None, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self.selected_user_id = None
        self.setWindowTitle("تنظیمات و مدیریت کاربران یسنا")
        self.setMinimumSize(950, 650)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("""
            QWidget { background:#F3F6F9; color:#183B56; font-family:Tahoma; font-size:9pt; }
            QLineEdit,QComboBox { background:white; border:1px solid #CBD5DF; border-radius:6px; padding:7px; }
            QPushButton { background:#183B56; color:white; border:0; border-radius:6px; padding:8px 14px; min-height:25px; }
            QPushButton:hover { background:#285577; }
            QTableWidget { background:white; alternate-background-color:#F2F6F9; gridline-color:#E1E7EC; selection-background-color:#D4AF37; selection-color:#183B56; }
            QHeaderView::section { background:#183B56; color:white; padding:8px; border:0; font-weight:bold; }
            QGroupBox { border:1px solid #CBD5DF; border-radius:8px; margin-top:10px; padding:10px; font-weight:bold; }
            QGroupBox::title { subcontrol-origin:margin; right:12px; padding:0 5px; }
        """)
        self.build_ui()
        self.load_settings()
        self.load_users()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 15, 18, 15)
        root.setSpacing(10)

        top = QHBoxLayout()
        back = QPushButton("بازگشت به داشبورد")
        back.clicked.connect(self.go_back)
        title = QLabel("تنظیمات برنامه و مدیریت کاربران")
        title.setStyleSheet("font-size:17pt;font-weight:bold;color:#183B56;padding:7px;")
        top.addWidget(back)
        top.addWidget(title, 1)
        root.addLayout(top)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.build_general_tab()
        self.build_users_tab()

    def build_general_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)
        self.org_name = QLineEdit()
        self.user_name = QLineEdit()
        self.letters_path = QLineEdit()
        path_row = QHBoxLayout()
        path_row.addWidget(self.letters_path, 1)
        browse = QPushButton("انتخاب پوشه")
        browse.clicked.connect(self.choose_letters_path)
        path_row.addWidget(browse)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("روشن", "light")
        self.theme_combo.addItem("تیره", "dark")
        form.addRow("نام سازمان:", self.org_name)
        form.addRow("نام کاربر فعلی:", self.user_name)
        form.addRow("مسیر پیش‌فرض ذخیره نامه‌ها:", path_widget)
        form.addRow("قالب ظاهری:", self.theme_combo)
        layout.addLayout(form)

        actions = QHBoxLayout()
        save = QPushButton("ذخیره تنظیمات")
        save.setStyleSheet("background:#D4AF37;color:#183B56;font-weight:bold;")
        save.clicked.connect(self.save_settings)
        backup = QPushButton("تهیه نسخه پشتیبان")
        backup.clicked.connect(self.create_backup)
        actions.addWidget(save)
        actions.addWidget(backup)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()
        note = QLabel("نسخه پشتیبان شامل فایل پایگاه داده یسنا (نامه‌ها، اشخاص، یادآوری‌ها و کاربران) است.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#68778A;padding:8px;")
        layout.addWidget(note)
        self.tabs.addTab(page, "تنظیمات عمومی")

    def build_users_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        self.users_table = QTableWidget(0, 5)
        self.users_table.setHorizontalHeaderLabels(
            ["شناسه", "نام کاربری", "نام نمایشی", "نقش", "وضعیت"]
        )
        self.users_table.setColumnHidden(0, True)
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.users_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.itemSelectionChanged.connect(self.select_user)
        layout.addWidget(self.users_table, 1)

        group = QGroupBox("اطلاعات حساب کاربری")
        form = QGridLayout(group)
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("برای کاربر جدید الزامی؛ برای ویرایش خالی بگذارید")
        self.role = QComboBox()
        self.role.addItems(["مدیر سیستم", "کاربر عادی", "فقط مشاهده"])
        self.active = QCheckBox("حساب فعال باشد")
        self.active.setChecked(True)
        form.addWidget(QLabel("نام کاربری:"), 0, 0)
        form.addWidget(self.username, 0, 1)
        form.addWidget(QLabel("نام نمایشی:"), 0, 2)
        form.addWidget(self.full_name, 0, 3)
        form.addWidget(QLabel("رمز عبور:"), 1, 0)
        form.addWidget(self.password, 1, 1)
        form.addWidget(QLabel("نقش:"), 1, 2)
        form.addWidget(self.role, 1, 3)
        form.addWidget(self.active, 2, 1, 1, 2)
        layout.addWidget(group)

        permissions_group = QGroupBox("سطح دسترسی بخش‌ها")
        permissions_layout = QGridLayout(permissions_group)
        self.permission_checks = {}
        permission_items = [
            ("dashboard", "داشبورد"), ("letters", "نامه‌های اداری"),
            ("postal", "نامه‌های پستی"), ("persons", "اشخاص"),
            ("reminders", "یادآوری‌ها"), ("reports", "گزارش‌گیری"),
            ("settings", "تنظیمات و کاربران")
        ]
        for index, (key, label) in enumerate(permission_items):
            check = QCheckBox(label)
            check.setChecked(True)
            self.permission_checks[key] = check
            permissions_layout.addWidget(check, index // 4, index % 4)
        layout.addWidget(permissions_group)

        buttons = QHBoxLayout()
        new_button = QPushButton("کاربر جدید")
        save_button = QPushButton("ذخیره / ویرایش کاربر")
        save_button.setStyleSheet("background:#D4AF37;color:#183B56;font-weight:bold;")
        deactivate_button = QPushButton("غیرفعال‌کردن کاربر")
        clear_button = QPushButton("پاک‌کردن فرم")
        new_button.clicked.connect(self.clear_user_form)
        save_button.clicked.connect(self.save_user)
        deactivate_button.clicked.connect(self.deactivate_user)
        clear_button.clicked.connect(self.clear_user_form)
        for button in (new_button, save_button, deactivate_button, clear_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.tabs.addTab(page, "مدیریت کاربران")

    def go_back(self):
        if callable(self.on_back):
            self.on_back()
        else:
            self.hide()

    def choose_letters_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "انتخاب پوشه ذخیره نامه‌ها", self.letters_path.text()
        )
        if path:
            self.letters_path.setText(os.path.abspath(path))

    def load_settings(self):
        conn = get_connection()
        try:
            rows = conn.execute("SELECT SettingKey, SettingValue FROM AppSettings").fetchall()
        finally:
            conn.close()
        values = dict(rows)
        self.org_name.setText(values.get("organization_name", ""))
        self.user_name.setText(values.get("current_user_name", ""))
        self.letters_path.setText(values.get("letters_default_path", os.path.join(os.path.expanduser("~"), "Documents", "Yasna", "Letters")))
        index = self.theme_combo.findData(values.get("theme", "light"))
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)

    def save_settings(self):
        values = {
            "organization_name": self.org_name.text().strip(),
            "current_user_name": self.user_name.text().strip(),
            "letters_default_path": self.letters_path.text().strip(),
            "theme": self.theme_combo.currentData()
        }
        conn = get_connection()
        try:
            for key, value in values.items():
                conn.execute(
                    "INSERT OR REPLACE INTO AppSettings (SettingKey, SettingValue) VALUES (?, ?)",
                    (key, value)
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            QMessageBox.critical(self, "خطا در ذخیره تنظیمات", str(exc))
            return
        finally:
            conn.close()

        app = self.window().windowHandle()
        application = self.parent()
        if application is not None and hasattr(application, "apply_theme"):
            application.apply_theme(values["theme"])
        QMessageBox.information(self, "یسنا", "تنظیمات با موفقیت ذخیره شد.")

    def create_backup(self):
        if not os.path.isfile(DB_PATH):
            QMessageBox.warning(self, "پشتیبان‌گیری", "فایل پایگاه داده پیدا نشد.")
            return
        default_name = "Yasna_Backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
        target, _ = QFileDialog.getSaveFileName(
            self, "ذخیره نسخه پشتیبان", os.path.join(os.path.dirname(DB_PATH), default_name),
            "SQLite Database (*.db)"
        )
        if not target:
            return
        if not target.lower().endswith(".db"):
            target += ".db"
        try:
            source = get_connection()
            destination = __import__("sqlite3").connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            QMessageBox.information(self, "پشتیبان‌گیری", "نسخه پشتیبان با موفقیت ساخته شد.\n" + target)
        except Exception as exc:
            QMessageBox.critical(self, "خطا در پشتیبان‌گیری", str(exc))

    @staticmethod
    def hash_password(password, salt=None):
        if salt is None:
            salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 150000)
        return digest.hex(), salt.hex()

    def load_users(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT UserID, Username, FullName, Role, IsActive FROM AppUsers ORDER BY UserID DESC"
            ).fetchall()
        finally:
            conn.close()
        self.users_table.setRowCount(0)
        for record in rows:
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)
            values = [record[0], record[1], record[2] or "", record[3], "فعال" if record[4] else "غیرفعال"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                self.users_table.setItem(row, col, item)

    def select_user(self):
        row = self.users_table.currentRow()
        if row < 0 or self.users_table.item(row, 0) is None:
            return
        self.selected_user_id = int(self.users_table.item(row, 0).text())
        conn = get_connection()
        try:
            record = conn.execute(
                "SELECT Username, FullName, Role, IsActive, Permissions FROM AppUsers WHERE UserID=?",
                (self.selected_user_id,)
            ).fetchone()
        finally:
            conn.close()
        if not record:
            return
        self.username.setText(record[0] or "")
        self.full_name.setText(record[1] or "")
        self.password.clear()
        self.role.setCurrentText(record[2] or "کاربر عادی")
        self.active.setChecked(bool(record[3]))
        try:
            permissions = json.loads(record[4] or "{}")
        except Exception:
            permissions = {}
        for key, check in self.permission_checks.items():
            check.setChecked(bool(permissions.get(key, True)))

    def clear_user_form(self):
        self.selected_user_id = None
        self.username.clear()
        self.full_name.clear()
        self.password.clear()
        self.role.setCurrentIndex(1)
        self.active.setChecked(True)
        for check in self.permission_checks.values():
            check.setChecked(True)
        self.users_table.clearSelection()
        self.username.setFocus()

    def save_user(self):
        username = self.username.text().strip()
        full_name = self.full_name.text().strip()
        password = self.password.text()
        if not username or not full_name:
            QMessageBox.warning(self, "اطلاعات ناقص", "نام کاربری و نام نمایشی را وارد کنید.")
            return
        if self.selected_user_id is None and len(password) < 6:
            QMessageBox.warning(self, "رمز عبور", "رمز عبور کاربر جدید باید حداقل ۶ نویسه باشد.")
            return
        permissions = json.dumps(
            {key: check.isChecked() for key, check in self.permission_checks.items()},
            ensure_ascii=False
        )
        conn = get_connection()
        try:
            if self.selected_user_id is None:
                password_hash, salt = self.hash_password(password)
                conn.execute("""
                    INSERT INTO AppUsers
                    (Username, FullName, PasswordHash, PasswordSalt, Role, IsActive, Permissions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (username, full_name, password_hash, salt, self.role.currentText(),
                      1 if self.active.isChecked() else 0, permissions))
            else:
                if password:
                    if len(password) < 6:
                        QMessageBox.warning(self, "رمز عبور", "رمز عبور باید حداقل ۶ نویسه باشد.")
                        return
                    password_hash, salt = self.hash_password(password)
                    conn.execute("""
                        UPDATE AppUsers SET Username=?, FullName=?, PasswordHash=?, PasswordSalt=?,
                        Role=?, IsActive=?, Permissions=? WHERE UserID=?
                    """, (username, full_name, password_hash, salt, self.role.currentText(),
                          1 if self.active.isChecked() else 0, permissions, self.selected_user_id))
                else:
                    conn.execute("""
                        UPDATE AppUsers SET Username=?, FullName=?, Role=?, IsActive=?,
                        Permissions=? WHERE UserID=?
                    """, (username, full_name, self.role.currentText(),
                          1 if self.active.isChecked() else 0, permissions, self.selected_user_id))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            QMessageBox.critical(self, "خطا در ذخیره کاربر", str(exc))
            return
        finally:
            conn.close()
        self.load_users()
        self.clear_user_form()
        QMessageBox.information(self, "مدیریت کاربران", "اطلاعات کاربر ذخیره شد.")

    def deactivate_user(self):
        if self.selected_user_id is None:
            QMessageBox.warning(self, "انتخاب کاربر", "ابتدا یک کاربر را از جدول انتخاب کنید.")
            return
        answer = QMessageBox.question(
            self, "غیرفعال‌کردن کاربر",
            "حساب این کاربر غیرفعال شود؟ اطلاعات او حذف نخواهد شد.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE AppUsers SET IsActive=0 WHERE UserID=?", (self.selected_user_id,))
            conn.commit()
        finally:
            conn.close()
        self.load_users()
        self.clear_user_form()
        QMessageBox.information(self, "مدیریت کاربران", "حساب کاربری غیرفعال شد.")
