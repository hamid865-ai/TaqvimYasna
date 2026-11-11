# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QComboBox, QFormLayout,
    QDialog, QFileDialog, QSizePolicy
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice, QPoint
from PyQt5.QtGui import QPainter, QPen, QImage, QPixmap
from database.database import get_connection
from forms.letters import JalaliCalendarDialog, today_jalali

STYLE = """
QWidget { background:#F3F5F8; color:#142D4E; font-family:Tahoma; }
QLineEdit,QTextEdit,QComboBox { background:white; border:1px solid #DCE2E9;
 border-radius:5px; padding:7px; }
QPushButton { background:#142D4E; color:white; border:0; border-radius:5px;
 padding:8px 13px; }
QPushButton#save { background:#D8B66A; color:#142D4E; font-weight:bold; }
QPushButton#delete { background:#A94442; }
QPushButton#secondary { background:#52677F; }
QTableWidget { background:white; gridline-color:#E5E9EF;
 selection-background-color:#D8B66A; }
QHeaderView::section { background:#142D4E; color:white; padding:7px; }
"""


class SignatureCanvas(QWidget):
    """A simple mouse-based signature canvas; stores a PNG image in memory."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(460, 190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.image = QImage(900, 360, QImage.Format_ARGB32)
        self.image.fill(Qt.white)
        self.last_point = QPoint()
        self.has_strokes = False
        self.setStyleSheet("background:white;border:1px solid #AAB5C2;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.white)
        painter.drawImage(self.rect(), self.image)
        painter.setPen(QPen(Qt.lightGray, 1, Qt.DashLine))
        painter.drawLine(12, self.height() - 28, self.width() - 12, self.height() - 28)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_point = event.pos()
            self.has_strokes = True
            painter = QPainter(self.image)
            pen = QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPoint(self._to_image_point(event.pos()))
            painter.end()
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            painter = QPainter(self.image)
            pen = QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(
                self._to_image_point(self.last_point),
                self._to_image_point(event.pos())
            )
            painter.end()
            self.last_point = event.pos()
            self.has_strokes = True
            self.update()

    def _to_image_point(self, point):
        x = int(point.x() * self.image.width() / max(1, self.width()))
        y = int(point.y() * self.image.height() / max(1, self.height()))
        return QPoint(x, y)

    def clear(self):
        self.image.fill(Qt.white)
        self.has_strokes = False
        self.update()

    def to_png(self):
        if not self.has_strokes:
            return None
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        self.image.save(buffer, "PNG")
        buffer.close()
        return bytes(data)


class SignatureDialog(QDialog):
    def __init__(self, caption, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ثبت امضا با ماوس")
        self.setMinimumWidth(540)
        self.setLayoutDirection(Qt.RightToLeft)
        layout = QVBoxLayout(self)
        info = QLabel(caption + "؛ امضا را داخل کادر رسم کنید.")
        info.setStyleSheet("font-weight:bold;color:#142D4E;padding:5px;")
        layout.addWidget(info)
        self.canvas = SignatureCanvas()
        layout.addWidget(self.canvas)
        buttons = QHBoxLayout()
        clear_button = QPushButton("پاک کردن")
        clear_button.setObjectName("secondary")
        ok_button = QPushButton("تأیید امضا")
        ok_button.setObjectName("save")
        cancel_button = QPushButton("انصراف")
        buttons.addWidget(clear_button)
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(ok_button)
        layout.addLayout(buttons)
        clear_button.clicked.connect(self.canvas.clear)
        cancel_button.clicked.connect(self.reject)
        ok_button.clicked.connect(self.accept_signature)
        self.signature_data = None

    def accept_signature(self):
        self.signature_data = self.canvas.to_png()
        if not self.signature_data:
            QMessageBox.warning(self, "امضا ثبت نشده", "لطفاً ابتدا امضا را داخل کادر رسم کنید.")
            return
        self.accept()


class DirectoryTab(QWidget):
    def __init__(self, table, id_column, name_column, extra_fields, parent=None):
        super().__init__(parent)
        self.table_name = table
        self.id_column = id_column
        self.name_column = name_column
        self.extra_fields = extra_fields
        self.selected_id = None
        self.setLayoutDirection(Qt.RightToLeft)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجو...")
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 2 + len(extra_fields))
        self.table.setHorizontalHeaderLabels(
            ["شناسه", "نام"] + [field[1] for field in extra_fields]
        )
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("نام")
        layout.addWidget(self.name_edit)
        self.extra_edits = []
        for column, caption in extra_fields:
            edit = QLineEdit()
            edit.setPlaceholderText(caption)
            self.extra_edits.append(edit)
            layout.addWidget(edit)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("ذخیره")
        self.save_button.setObjectName("save")
        self.new_button = QPushButton("جدید")
        self.delete_button = QPushButton("حذف")
        self.delete_button.setObjectName("delete")
        for button in (self.save_button, self.new_button, self.delete_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.search.textChanged.connect(self.load_rows)
        self.table.itemSelectionChanged.connect(self.select_row)
        self.save_button.clicked.connect(self.save_row)
        self.new_button.clicked.connect(self.clear_form)
        self.delete_button.clicked.connect(self.delete_row)
        self.load_rows()

    def load_rows(self):
        columns = [self.id_column, self.name_column] + [x[0] for x in self.extra_fields]
        sql = "SELECT {} FROM {}".format(",".join(columns), self.table_name)
        key = self.search.text().strip()
        params = ()
        if key:
            sql += " WHERE {} LIKE ?".format(self.name_column)
            params = ("%" + key + "%",)
        sql += " ORDER BY {} DESC".format(self.id_column)
        connection = get_connection()
        try:
            rows = connection.execute(sql, params).fetchall()
        finally:
            connection.close()
        self.table.setRowCount(0)
        for record in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate(record):
                self.table.setItem(row, col, QTableWidgetItem("" if value is None else str(value)))

    def select_row(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return
        self.selected_id = int(self.table.item(row, 0).text())
        self.name_edit.setText(self.table.item(row, 1).text())
        for index, edit in enumerate(self.extra_edits):
            edit.setText(self.table.item(row, index + 2).text())

    def clear_form(self):
        self.selected_id = None
        self.name_edit.clear()
        for edit in self.extra_edits:
            edit.clear()
        self.table.clearSelection()
        self.name_edit.setFocus()

    def save_row(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "توجه", "نام را وارد کنید.")
            return
        columns = [self.name_column] + [x[0] for x in self.extra_fields]
        values = [name] + [edit.text().strip() for edit in self.extra_edits]
        connection = get_connection()
        try:
            if self.selected_id is None:
                marks = ",".join(["?"] * len(columns))
                connection.execute(
                    "INSERT INTO {} ({}) VALUES ({})".format(
                        self.table_name, ",".join(columns), marks
                    ), values
                )
            else:
                assignments = ",".join([column + "=?" for column in columns])
                connection.execute(
                    "UPDATE {} SET {} WHERE {}=?".format(
                        self.table_name, assignments, self.id_column
                    ), values + [self.selected_id]
                )
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا", str(error))
            return
        finally:
            connection.close()
        self.clear_form()
        self.load_rows()

    def delete_row(self):
        if self.selected_id is None:
            return
        answer = QMessageBox.question(
            self, "تأیید حذف", "این مورد حذف شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        connection = get_connection()
        try:
            connection.execute(
                "DELETE FROM {} WHERE {}=?".format(self.table_name, self.id_column),
                (self.selected_id,)
            )
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا", str(error))
        finally:
            connection.close()
        self.clear_form()
        self.load_rows()


class PostalForm(QWidget):
    def __init__(self, parent=None, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self.selected_id = None
        self.sender_signature_data = None
        self.receiver_signature_data = None
        self.sender_signature_method = None
        self.receiver_signature_method = None
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("مدیریت نامه‌های پستی")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#142D4E;")
        top.addWidget(title)
        top.addStretch()
        self.back_button = QPushButton("بازگشت به داشبورد")
        self.back_button.clicked.connect(self.go_back)
        top.addWidget(self.back_button)
        root.addLayout(top)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.records_tab = QWidget()
        self.tabs.addTab(self.records_tab, "ثبت و جستجوی مرسولات")
        self.build_records_tab()
        self.tabs.addTab(DirectoryTab(
            "PostalSenders", "SenderID", "SenderName",
            [("Organization", "سازمان"), ("Phone", "تلفن"),
             ("Address", "نشانی"), ("Description", "توضیحات")]
        ), "مدیریت فرستندگان")
        self.tabs.addTab(DirectoryTab(
            "PostalReceivers", "ReceiverID", "ReceiverName",
            [("Organization", "سازمان"), ("Phone", "تلفن"),
             ("Address", "نشانی"), ("Description", "توضیحات")]
        ), "مدیریت گیرندگان")
        self.tabs.addTab(DirectoryTab(
            "Subjects", "SubjectID", "SubjectName",
            [("SubjectDescription", "توضیحات")]
        ), "مدیریت موضوعات")
        self.tabs.addTab(DirectoryTab(
            "Signators", "SignatorID", "SignatorName",
            [("SignatorJob", "سمت")]
        ), "مدیریت امضاکنندگان")
        self.load_records()

    def go_back(self):
        if callable(self.on_back):
            self.on_back()

    def build_records_tab(self):
        layout = QVBoxLayout(self.records_tab)
        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجو با شماره نامه، بارکد، فرستنده یا گیرنده...")
        self.search.textChanged.connect(self.load_records)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["شناسه", "شماره نامه", "تاریخ", "کد رهگیری", "فرستنده", "گیرنده", "موضوع", "وضعیت"]
        )
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.select_record)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.number_edit = QLineEdit()
        self.date_edit = QLineEdit(today_jalali())
        self.date_edit.setReadOnly(True)
        self.date_edit.setPlaceholderText("تاریخ شمسی")
        self.date_button = QPushButton("انتخاب تاریخ")
        self.date_button.setMaximumWidth(115)
        self.date_button.clicked.connect(self.open_calendar)
        date_widget = QWidget()
        date_layout = QHBoxLayout(date_widget)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(self.date_edit, 1)
        date_layout.addWidget(self.date_button)
        self.tracking_edit = QLineEdit()
        self.tracking_edit.setPlaceholderText("اسکن بارکد؛ با فشردن Enter جستجو می‌شود")
        self.tracking_edit.returnPressed.connect(self.barcode_enter)
        self.sender_combo = QComboBox()
        self.receiver_combo = QComboBox()
        self.subject_combo = QComboBox()
        self.signator_combo = QComboBox()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(55)
        for caption, widget in (
            ("شماره نامه", self.number_edit), ("تاریخ ثبت", date_widget),
            ("کد رهگیری / بارکد", self.tracking_edit), ("فرستنده", self.sender_combo),
            ("گیرنده", self.receiver_combo), ("موضوع", self.subject_combo),
            ("امضاکننده نامه", self.signator_combo), ("توضیحات", self.description_edit)
        ):
            form.addRow(caption, widget)
        layout.addLayout(form)

        signature_row = QHBoxLayout()
        signature_row.addWidget(self._build_signature_group("فرستنده", "sender"))
        signature_row.addWidget(self._build_signature_group("گیرنده", "receiver"))
        layout.addLayout(signature_row)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("ذخیره مرسوله")
        self.save_button.setObjectName("save")
        self.new_button = QPushButton("جدید")
        self.delete_button = QPushButton("حذف مرسوله")
        self.delete_button.setObjectName("delete")
        self.sent_button = QPushButton("ثبت ارسال")
        self.delivered_button = QPushButton("ثبت تحویل")
        for button in (self.save_button, self.new_button, self.delete_button,
                       self.sent_button, self.delivered_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.save_button.clicked.connect(self.save_record)
        self.new_button.clicked.connect(self.reset_record)
        self.delete_button.clicked.connect(self.delete_record)
        self.sent_button.clicked.connect(self.mark_sent)
        self.delivered_button.clicked.connect(self.mark_delivered)
        self.refresh_combos()

    def _build_signature_group(self, title, party):
        from PyQt5.QtWidgets import QGroupBox
        group = QGroupBox("امضای " + title)
        group.setStyleSheet("QGroupBox{font-weight:bold;border:1px solid #C8D1DC;border-radius:6px;margin-top:8px;padding:8px;} QGroupBox::title{subcontrol-origin:margin;right:10px;padding:0 5px;}")
        layout = QVBoxLayout(group)
        preview = QLabel("هنوز امضایی ثبت نشده است")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumHeight(75)
        preview.setMaximumHeight(95)
        preview.setStyleSheet("background:white;border:1px dashed #AAB5C2;color:#78889A;")
        layout.addWidget(preview)
        method_label = QLabel("روش ثبت: —")
        method_label.setStyleSheet("color:#52677F;font-size:10px;")
        layout.addWidget(method_label)
        buttons = QHBoxLayout()
        draw_button = QPushButton("رسم با ماوس")
        upload_button = QPushButton("بارگذاری تصویر")
        pad_button = QPushButton("پد امضا (آینده)")
        pad_button.setEnabled(False)
        clear_button = QPushButton("پاک‌کردن امضای جدید")
        clear_button.setObjectName("secondary")
        for button in (draw_button, upload_button, pad_button, clear_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        draw_button.clicked.connect(lambda checked=False, p=party: self.capture_mouse_signature(p))
        upload_button.clicked.connect(lambda checked=False, p=party: self.upload_signature(p))
        clear_button.clicked.connect(lambda checked=False, p=party: self.clear_signature(p))
        if party == "sender":
            self.sender_preview = preview
            self.sender_method_label = method_label
        else:
            self.receiver_preview = preview
            self.receiver_method_label = method_label
        return group

    def open_calendar(self):
        dialog = JalaliCalendarDialog(self, self.date_edit.text())
        if dialog.exec_() == QDialog.Accepted and dialog.selected_date:
            self.date_edit.setText(dialog.selected_date)

    def refresh_combos(self):
        connection = get_connection()
        try:
            definitions = (
                (self.sender_combo, "PostalSenders", "SenderID", "SenderName"),
                (self.receiver_combo, "PostalReceivers", "ReceiverID", "ReceiverName"),
                (self.subject_combo, "Subjects", "SubjectID", "SubjectName"),
                (self.signator_combo, "Signators", "SignatorID", "SignatorName")
            )
            for widget, table, id_col, name_col in definitions:
                widget.clear()
                widget.addItem("— انتخاب نشده —", None)
                rows = connection.execute(
                    "SELECT {},{} FROM {} ORDER BY {}".format(id_col, name_col, table, name_col)
                ).fetchall()
                for row in rows:
                    widget.addItem(row[1], row[0])
        finally:
            connection.close()

    def load_records(self):
        if not hasattr(self, "table"):
            return
        key = self.search.text().strip()
        sql = """SELECT p.PostalID, p.LetterNumber, p.PostalDate,
            p.TrackingCode, COALESCE(s.SenderName,''),
            COALESCE(r.ReceiverName,p.ReceiverName,''), COALESCE(sb.SubjectName,''),
            COALESCE(p.PostalStatus,'ثبت‌شده')
            FROM PostalLetters p
            LEFT JOIN PostalSenders s ON s.SenderID=p.SenderID
            LEFT JOIN PostalReceivers r ON r.ReceiverID=p.ReceiverID
            LEFT JOIN Subjects sb ON sb.SubjectID=p.SubjectID"""
        params = ()
        if key:
            sql += " WHERE p.LetterNumber LIKE ? OR p.TrackingCode LIKE ? OR " \
                   "r.ReceiverName LIKE ? OR p.ReceiverName LIKE ? OR s.SenderName LIKE ?"
            params = ("%" + key + "%",) * 5
        sql += " ORDER BY p.PostalID DESC"
        connection = get_connection()
        try:
            rows = connection.execute(sql, params).fetchall()
        finally:
            connection.close()
        self.table.setRowCount(0)
        for record in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate(record):
                self.table.setItem(row, col, QTableWidgetItem("" if value is None else str(value)))

    def barcode_enter(self):
        code = self.tracking_edit.text().strip()
        if not code:
            return
        self.search.setText(code)
        connection = get_connection()
        try:
            found = connection.execute(
                "SELECT PostalID FROM PostalLetters WHERE TrackingCode=? ORDER BY PostalID DESC LIMIT 1",
                (code,)
            ).fetchone()
        finally:
            connection.close()
        if found:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and int(item.text()) == int(found[0]):
                    self.table.selectRow(row)
                    break
        else:
            self.selected_id = None
            self.number_edit.setFocus()

    def select_record(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return
        self.selected_id = int(self.table.item(row, 0).text())
        connection = get_connection()
        try:
            record = connection.execute("""SELECT LetterNumber,PostalDate,TrackingCode,
                SenderID,ReceiverID,SubjectID,SignatorID,Description
                FROM PostalLetters WHERE PostalID=?""", (self.selected_id,)).fetchone()
            signatures = connection.execute("""SELECT PartyType,SignatureMethod,SignatureData
                FROM PostalSignatures WHERE PostalID=? ORDER BY SignatureID DESC""",
                (self.selected_id,)).fetchall()
        finally:
            connection.close()
        if not record:
            return
        self.number_edit.setText(record[0] or "")
        self.date_edit.setText(record[1] or "")
        self.tracking_edit.setText(record[2] or "")
        for widget, value in zip(
            (self.sender_combo, self.receiver_combo, self.subject_combo, self.signator_combo),
            record[3:7]
        ):
            index = widget.findData(value)
            widget.setCurrentIndex(index if index >= 0 else 0)
        self.description_edit.setPlainText(record[7] or "")
        self.sender_signature_data = None
        self.receiver_signature_data = None
        self.sender_signature_method = None
        self.receiver_signature_method = None
        seen = set()
        for party, method, data in signatures:
            if party in seen:
                continue
            seen.add(party)
            self._set_signature(party, bytes(data), method, update_memory=True)
        if "sender" not in seen:
            self._show_empty_signature("sender")
        if "receiver" not in seen:
            self._show_empty_signature("receiver")

    def _set_signature(self, party, data, method, update_memory=True):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if party == "sender":
            if update_memory:
                self.sender_signature_data = data
                self.sender_signature_method = method
            preview = self.sender_preview
            method_label = self.sender_method_label
        else:
            if update_memory:
                self.receiver_signature_data = data
                self.receiver_signature_method = method
            preview = self.receiver_preview
            method_label = self.receiver_method_label
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(420, 82, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            preview.setText("")
        else:
            preview.setPixmap(QPixmap())
            preview.setText("تصویر امضا قابل نمایش نیست")
        method_names = {"mouse": "رسم با ماوس", "image": "تصویر بارگذاری‌شده", "pad": "پد امضا"}
        method_label.setText("روش ثبت: " + method_names.get(method, method))

    def _show_empty_signature(self, party):
        if party == "sender":
            preview, label = self.sender_preview, self.sender_method_label
        else:
            preview, label = self.receiver_preview, self.receiver_method_label
        preview.setPixmap(QPixmap())
        preview.setText("هنوز امضایی ثبت نشده است")
        label.setText("روش ثبت: —")

    def capture_mouse_signature(self, party):
        if not self._ensure_saved_record():
            return
        caption = "فرستنده" if party == "sender" else "گیرنده"
        dialog = SignatureDialog(caption, self)
        if dialog.exec_() == QDialog.Accepted and dialog.signature_data:
            self._set_signature(party, dialog.signature_data, "mouse")
            self._save_signature(party)

    def upload_signature(self, party):
        if not self._ensure_saved_record():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب تصویر امضا", "", "تصاویر (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "تصویر نامعتبر", "فایل انتخاب‌شده قابل خواندن نیست.")
            return
        image = image.convertToFormat(QImage.Format_ARGB32)
        image = image.scaled(1200, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        data_array = QByteArray()
        buffer = QBuffer(data_array)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        self._set_signature(party, bytes(data_array), "image")
        self._save_signature(party)

    def clear_signature(self, party):
        if party == "sender":
            self.sender_signature_data = None
            self.sender_signature_method = None
        else:
            self.receiver_signature_data = None
            self.receiver_signature_method = None
        self._show_empty_signature(party)
        QMessageBox.information(
            self, "توجه", "فقط امضای جدید از فرم پاک شد. سوابق امضاهای ذخیره‌شده حذف نمی‌شوند."
        )

    def _ensure_saved_record(self):
        if self.selected_id is not None:
            return True
        QMessageBox.information(
            self, "ابتدا مرسوله را ذخیره کنید",
            "ابتدا اطلاعات مرسوله را ذخیره کنید؛ سپس می‌توانید امضاها را به آن متصل کنید."
        )
        return False

    def _save_signature(self, party):
        if self.selected_id is None:
            return
        if party == "sender":
            data = self.sender_signature_data
            method = self.sender_signature_method
            signer_name = self.sender_combo.currentText()
        else:
            data = self.receiver_signature_data
            method = self.receiver_signature_method
            signer_name = self.receiver_combo.currentText()
        if not data or not method:
            return
        if not signer_name or signer_name.startswith("—"):
            QMessageBox.warning(self, "نام مشخص نیست", "ابتدا نام فرستنده یا گیرنده را انتخاب کنید.")
            return
        connection = get_connection()
        try:
            connection.execute("""INSERT INTO PostalSignatures
                (PostalID,PartyType,SignerName,SignatureMethod,SignatureData)
                VALUES (?,?,?,?,?)""",
                (self.selected_id, party, signer_name, method, sqlite_blob(data)))
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا در ذخیره امضا", str(error))
            return
        finally:
            connection.close()
        QMessageBox.information(self, "Yasna", "امضای " + ("فرستنده" if party == "sender" else "گیرنده") + " ذخیره شد.")

    def save_record(self):
        code = self.tracking_edit.text().strip()
        values = (
            self.number_edit.text().strip(), self.date_edit.text().strip(), code,
            self.sender_combo.currentData(), self.receiver_combo.currentData(),
            self.subject_combo.currentData(), self.signator_combo.currentData(),
            self.description_edit.toPlainText().strip(),
            self.receiver_combo.currentText() if self.receiver_combo.currentData() else ""
        )
        if not values[0] and not code:
            QMessageBox.warning(self, "اطلاعات ناقص", "شماره نامه یا کد رهگیری را وارد کنید.")
            return
        connection = get_connection()
        try:
            if code:
                duplicate = connection.execute(
                    "SELECT PostalID FROM PostalLetters WHERE TrackingCode=? AND PostalID<>? LIMIT 1",
                    (code, self.selected_id or -1)
                ).fetchone()
                if duplicate:
                    QMessageBox.warning(self, "بارکد تکراری", "این کد رهگیری قبلاً ثبت شده است.")
                    return
            if self.selected_id is None:
                cursor = connection.execute("""INSERT INTO PostalLetters
                    (LetterNumber,PostalDate,TrackingCode,SenderID,ReceiverID,SubjectID,
                    SignatorID,Description,ReceiverName) VALUES (?,?,?,?,?,?,?,?,?)""", values)
                self.selected_id = cursor.lastrowid
            else:
                connection.execute("""UPDATE PostalLetters SET LetterNumber=?,PostalDate=?,
                    TrackingCode=?,SenderID=?,ReceiverID=?,SubjectID=?,SignatorID=?,
                    Description=?,ReceiverName=? WHERE PostalID=?""", values + (self.selected_id,))
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا در ذخیره", str(error))
            return
        finally:
            connection.close()
        self.load_records()
        QMessageBox.information(self, "Yasna", "مرسوله ذخیره شد. اکنون می‌توانید امضاها را ثبت کنید.")

    def mark_sent(self):
        if not self._ensure_saved_record():
            return
        if not self.sender_signature_data:
            QMessageBox.warning(self, "امضای فرستنده", "برای ثبت ارسال، ابتدا امضای فرستنده را ثبت کنید.")
            return
        connection = get_connection()
        try:
            saved_sender = connection.execute("""SELECT SignerName FROM PostalSignatures
                WHERE PostalID=? AND PartyType='sender' ORDER BY SignatureID DESC LIMIT 1""",
                (self.selected_id,)).fetchone()
        finally:
            connection.close()
        if not saved_sender or saved_sender[0] != self.sender_combo.currentText():
            QMessageBox.warning(self, "عدم تطابق فرستنده", "امضای ثبت‌شده متعلق به فرستنده انتخاب‌شده نیست. لطفاً امضای فرستنده فعلی را دوباره ثبت کنید.")
            return
        connection = get_connection()
        try:
            connection.execute("""UPDATE PostalLetters SET PostalStatus='ارسال‌شده',
                SentAt=CURRENT_TIMESTAMP WHERE PostalID=?""", (self.selected_id,))
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا", str(error))
            return
        finally:
            connection.close()
        self.load_records()
        QMessageBox.information(self, "Yasna", "وضعیت مرسوله به ارسال‌شده تغییر کرد.")

    def mark_delivered(self):
        if not self._ensure_saved_record():
            return
        if not self.receiver_signature_data:
            QMessageBox.warning(self, "امضای گیرنده", "برای ثبت تحویل، ابتدا امضای گیرنده را ثبت کنید.")
            return
        connection = get_connection()
        try:
            saved_receiver = connection.execute("""SELECT SignerName FROM PostalSignatures
                WHERE PostalID=? AND PartyType='receiver' ORDER BY SignatureID DESC LIMIT 1""",
                (self.selected_id,)).fetchone()
        finally:
            connection.close()
        if not saved_receiver or saved_receiver[0] != self.receiver_combo.currentText():
            QMessageBox.warning(self, "عدم تطابق گیرنده", "امضای ثبت‌شده متعلق به گیرنده انتخاب‌شده نیست. لطفاً امضای گیرنده فعلی را دوباره ثبت کنید.")
            return
        connection = get_connection()
        try:
            connection.execute("""UPDATE PostalLetters SET PostalStatus='تحویل‌شده',
                DeliveredAt=CURRENT_TIMESTAMP WHERE PostalID=?""", (self.selected_id,))
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا", str(error))
            return
        finally:
            connection.close()
        self.load_records()
        QMessageBox.information(self, "Yasna", "تحویل مرسوله ثبت شد.")

    def delete_record(self):
        if self.selected_id is None:
            return
        answer = QMessageBox.question(
            self, "تأیید حذف", "این مرسوله و سوابق امضاهای مرتبط با آن حذف شوند؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        connection = get_connection()
        try:
            connection.execute("DELETE FROM PostalLetters WHERE PostalID=?", (self.selected_id,))
            connection.commit()
        except Exception as error:
            connection.rollback()
            QMessageBox.critical(self, "خطا", str(error))
        finally:
            connection.close()
        self.reset_record()
        self.load_records()

    def reset_record(self):
        self.selected_id = None
        self.number_edit.clear()
        self.date_edit.setText(today_jalali())
        self.tracking_edit.clear()
        self.description_edit.clear()
        for widget in (self.sender_combo, self.receiver_combo, self.subject_combo, self.signator_combo):
            widget.setCurrentIndex(0)
        self.sender_signature_data = None
        self.receiver_signature_data = None
        self.sender_signature_method = None
        self.receiver_signature_method = None
        self._show_empty_signature("sender")
        self._show_empty_signature("receiver")
        self.table.clearSelection()
        self.tracking_edit.setFocus()


def sqlite_blob(data):
    """Return a buffer-compatible value for SQLite BLOB storage."""
    return memoryview(data)
