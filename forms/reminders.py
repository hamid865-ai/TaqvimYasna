# -*- coding: utf-8 -*-
from datetime import date, datetime

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView,
    QAbstractItemView, QTimeEdit, QComboBox
)
from PyQt5.QtCore import Qt, QTime
from PyQt5.QtGui import QColor

from database.database import get_connection
from forms.letters import JalaliCalendarDialog, today_jalali, jalali_to_gregorian
from windows_alarm import schedule_reminder_task, remove_reminder_task


class RemindersForm(QWidget):
    def __init__(self, parent=None, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self.current_reminder_id = None
        self.setWindowTitle("مدیریت یادآوری‌ها")
        self.setMinimumSize(950, 650)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("""
            QWidget { background:#F3F6F9; color:#183B56; font-family:Tahoma; font-size:9pt; }
            QLineEdit,QTextEdit,QComboBox,QTimeEdit { background:white; border:1px solid #CBD5DF; border-radius:6px; padding:6px; }
            QPushButton { background:#183B56; color:white; border:0; border-radius:6px; padding:8px 13px; min-height:26px; font-weight:bold; }
            QPushButton:hover { background:#285577; }
            QTableWidget { background:white; alternate-background-color:#F2F6F9; gridline-color:#E1E7EC; border:1px solid #D5DDE5; selection-background-color:#D4AF37; selection-color:#183B56; }
            QHeaderView::section { background:#183B56; color:white; padding:8px; border:0; font-weight:bold; }
        """)
        self.init_ui()
        self.clear_form()
        self.load_reminders()
        self.sync_pending_windows_alarms()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 12, 15, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.btn_back = QPushButton("بازگشت به داشبورد")
        title = QLabel("مدیریت یادآوری‌ها")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:16pt;font-weight:bold;color:#183B56;padding:7px;")
        top.addWidget(self.btn_back)
        top.addWidget(title, 1)
        top.addStretch()
        root.addLayout(top)
        self.btn_back.clicked.connect(self.go_back)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("عنوان یادآوری را وارد کنید")
        self.txt_date = QLineEdit()
        self.txt_date.setReadOnly(True)
        self.btn_calendar = QPushButton("انتخاب تاریخ")
        date_box = QWidget()
        date_layout = QHBoxLayout(date_box)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(self.txt_date, 1)
        date_layout.addWidget(self.btn_calendar)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(9, 0))
        self.txt_description = QTextEdit()
        self.txt_description.setPlaceholderText("توضیحات (اختیاری)")
        self.txt_description.setMaximumHeight(75)
        form.addWidget(QLabel("عنوان:"), 0, 0)
        form.addWidget(self.txt_title, 0, 1, 1, 3)
        form.addWidget(QLabel("تاریخ شمسی:"), 1, 0)
        form.addWidget(date_box, 1, 1)
        form.addWidget(QLabel("ساعت:"), 1, 2)
        form.addWidget(self.time_edit, 1, 3)
        form.addWidget(QLabel("توضیحات:"), 2, 0)
        form.addWidget(self.txt_description, 2, 1, 1, 3)
        form.setColumnStretch(1, 2)
        form.setColumnStretch(3, 1)
        root.addLayout(form)
        self.btn_calendar.clicked.connect(self.choose_date)

        actions = QHBoxLayout()
        self.btn_new = QPushButton("یادآوری جدید")
        self.btn_save = QPushButton("ذخیره یادآوری")
        self.btn_done = QPushButton("علامت‌گذاری انجام‌شده")
        self.btn_delete = QPushButton("حذف یادآوری")
        self.btn_save.setStyleSheet("background:#D4AF37;color:#183B56;")
        for button in (self.btn_new, self.btn_save, self.btn_done, self.btn_delete):
            actions.addWidget(button)
        root.addLayout(actions)
        self.btn_new.clicked.connect(self.clear_form)
        self.btn_save.clicked.connect(self.save_reminder)
        self.btn_done.clicked.connect(self.mark_done)
        self.btn_delete.clicked.connect(self.delete_reminder)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("جستجو:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو در عنوان و توضیحات...")
        self.cbo_status = QComboBox()
        self.cbo_status.addItem("همه یادآوری‌ها", "all")
        self.cbo_status.addItem("انجام‌نشده", "open")
        self.cbo_status.addItem("انجام‌شده", "done")
        filters.addWidget(self.txt_search, 1)
        filters.addWidget(QLabel("وضعیت:"))
        filters.addWidget(self.cbo_status)
        root.addLayout(filters)
        self.txt_search.textChanged.connect(self.load_reminders)
        self.cbo_status.currentIndexChanged.connect(self.load_reminders)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["شناسه", "عنوان", "تاریخ", "ساعت", "وضعیت", "توضیحات"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.select_reminder)
        root.addWidget(self.table, 1)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("color:#68778A;padding:4px;")
        root.addWidget(self.lbl_summary)

    def go_back(self):
        if callable(self.on_back):
            self.on_back()
        else:
            self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_reminders()
        self.sync_pending_windows_alarms()

    def choose_date(self):
        dialog = JalaliCalendarDialog(self, self.txt_date.text())
        if dialog.exec_() == dialog.Accepted and dialog.selected_date:
            self.txt_date.setText(dialog.selected_date)

    def clear_form(self):
        self.current_reminder_id = None
        self.txt_title.clear()
        self.txt_date.setText(today_jalali())
        self.time_edit.setTime(QTime(9, 0))
        self.txt_description.clear()
        self.table.clearSelection()

    def load_reminders(self, *args):
        search = self.txt_search.text().strip() if hasattr(self, "txt_search") else ""
        status = self.cbo_status.currentData() if hasattr(self, "cbo_status") else "all"
        conditions, params = [], []
        if search:
            conditions.append("(ReminderTitle LIKE ? OR Description LIKE ?)")
            params.extend(["%" + search + "%", "%" + search + "%"])
        if status == "open":
            conditions.append("COALESCE(IsDone, 0) = 0")
        elif status == "done":
            conditions.append("COALESCE(IsDone, 0) = 1")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""SELECT ReminderID, ReminderTitle, ReminderDate,
                COALESCE(ReminderTime, ''), COALESCE(IsDone, 0), COALESCE(Description, '')
                FROM Reminders""" + where + " ORDER BY ReminderDate, ReminderTime, ReminderID", params)
            records = cursor.fetchall()
        finally:
            conn.close()
        self.table.setRowCount(0)
        for row_index, record in enumerate(records):
            self.table.insertRow(row_index)
            status_text = "انجام‌شده" if int(record[4]) else self.get_due_status(record[2], record[3])
            values = [record[0], record[1], record[2], record[3] or "—", status_text, record[5]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value if value is not None else ""))
                self.table.setItem(row_index, col, item)
            if int(record[4]):
                for col in range(1, 6):
                    self.table.item(row_index, col).setForeground(QColor("#718096"))
            elif status_text == "سررسید گذشته":
                for col in range(1, 6):
                    self.table.item(row_index, col).setForeground(QColor("#C0392B"))
        self.lbl_summary.setText("تعداد یادآوری‌های نمایش‌داده‌شده: {}".format(len(records)))

    def sync_pending_windows_alarms(self):
        """همگام‌سازی یادآوری‌های باز با Windows Task Scheduler."""
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT ReminderID, ReminderDate, COALESCE(ReminderTime, '')
                FROM Reminders
                WHERE COALESCE(IsDone, 0) = 0
                  AND COALESCE(NotifiedAt, '') = ''
            """).fetchall()
        finally:
            conn.close()

        for reminder_id, jalali_date, time_text in rows:
            try:
                parts = [int(x) for x in jalali_date.split("/")]
                gy, gm, gd = jalali_to_gregorian(
                    parts[0], parts[1], parts[2]
                )
                hh, mm = [int(x) for x in (time_text or "23:59").split(":")[:2]]
                schedule_reminder_task(
                    reminder_id, gy, gm, gd, hh, mm
                )
            except Exception as error:
                print("Windows reminder sync error:", error)

    def get_due_status(self, jalali_date, time_text):
        try:
            parts = [int(x) for x in jalali_date.split("/")]
            from forms.letters import jalali_to_gregorian
            gy, gm, gd = jalali_to_gregorian(parts[0], parts[1], parts[2])
            due = datetime(gy, gm, gd)
            if time_text:
                hh, mm = [int(x) for x in time_text.split(":")[:2]]
                due = due.replace(hour=hh, minute=mm)
            else:
                due = due.replace(hour=23, minute=59)
            return "سررسید گذشته" if due < datetime.now() else "در انتظار"
        except Exception:
            return "در انتظار"

    def select_reminder(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        self.current_reminder_id = int(self.table.item(row, 0).text())
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""SELECT ReminderTitle, ReminderDate, ReminderTime, Description
                FROM Reminders WHERE ReminderID = ?""", (self.current_reminder_id,))
            record = cursor.fetchone()
        finally:
            conn.close()
        if record:
            self.txt_title.setText(record[0] or "")
            self.txt_date.setText(record[1] or today_jalali())
            if record[2]:
                try:
                    self.time_edit.setTime(QTime.fromString(record[2], "HH:mm"))
                except Exception:
                    self.time_edit.setTime(QTime(9, 0))
            else:
                self.time_edit.setTime(QTime(9, 0))
            self.txt_description.setPlainText(record[3] or "")

    def save_reminder(self):
        title = self.txt_title.text().strip()
        reminder_date = self.txt_date.text().strip()
        reminder_time = self.time_edit.time().toString("HH:mm")
        description = self.txt_description.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, "توجه", "عنوان یادآوری را وارد کنید.")
            self.txt_title.setFocus()
            return
        try:
            parts = reminder_date.split("/")
            if len(parts) != 3:
                raise ValueError()
            gy, gm, gd = jalali_to_gregorian(
                int(parts[0]), int(parts[1]), int(parts[2])
            )
        except Exception:
            QMessageBox.warning(self, "تاریخ نامعتبر", "تاریخ یادآوری را با تقویم شمسی انتخاب کنید.")
            return
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if self.current_reminder_id is None:
                cursor.execute("""INSERT INTO Reminders
                    (ReminderTitle, ReminderDate, Description, IsDone, ReminderTime)
                    VALUES (?, ?, ?, 0, ?)""", (title, reminder_date, description, reminder_time))
                self.current_reminder_id = cursor.lastrowid
            else:
                cursor.execute("""UPDATE Reminders SET ReminderTitle = ?, ReminderDate = ?,
                    Description = ?, ReminderTime = ?, NotifiedAt = NULL
                    WHERE ReminderID = ?""",
                    (title, reminder_date, description, reminder_time, self.current_reminder_id))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            QMessageBox.critical(self, "خطا در ذخیره", str(exc))
            return
        finally:
            conn.close()
        try:
            ok, alarm_message = schedule_reminder_task(
                self.current_reminder_id,
                gy, gm, gd,
                self.time_edit.time().hour(),
                self.time_edit.time().minute()
            )
            if not ok:
                QMessageBox.warning(
                    self, "هشدار ویندوز",
                    "یادآوری ذخیره شد، اما زمان‌بندی هشدار ویندوز انجام نشد.\n"
                    + alarm_message
                )
        except Exception as alarm_error:
            QMessageBox.warning(
                self, "هشدار ویندوز",
                "یادآوری ذخیره شد، اما ساخت هشدار ویندوز با خطا روبه‌رو شد.\n"
                + str(alarm_error)
            )
        self.load_reminders()
        QMessageBox.information(self, "ذخیره شد", "یادآوری با موفقیت ذخیره شد.")

    def mark_done(self):
        if self.current_reminder_id is None:
            QMessageBox.warning(self, "توجه", "ابتدا یک یادآوری از جدول انتخاب کنید.")
            return
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE Reminders SET IsDone = 1 WHERE ReminderID = ?", (self.current_reminder_id,))
            conn.commit()
            remove_reminder_task(self.current_reminder_id)
        finally:
            conn.close()
        self.clear_form()
        self.load_reminders()

    def delete_reminder(self):
        if self.current_reminder_id is None:
            QMessageBox.warning(self, "توجه", "ابتدا یک یادآوری از جدول انتخاب کنید.")
            return
        answer = QMessageBox.question(self, "حذف یادآوری", "آیا از حذف این یادآوری مطمئن هستید؟", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Reminders WHERE ReminderID = ?", (self.current_reminder_id,))
            conn.commit()
            remove_reminder_task(self.current_reminder_id)
        except Exception as exc:
            conn.rollback()
            QMessageBox.critical(self, "خطا در حذف", str(exc))
            return
        finally:
            conn.close()
        self.clear_form()
        self.load_reminders()
