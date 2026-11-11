
import os
import shutil
import tempfile
from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView,
    QComboBox, QListWidget, QListWidgetItem,
    QDialog, QGridLayout, QFileDialog,
    QFontComboBox, QSpinBox, QColorDialog
)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCharFormat, QColor, QFont

from database.database import get_connection


# ==========================================
# تبدیل تاریخ میلادی به شمسی
# ==========================================

def gregorian_to_jalali(gy, gm, gd):

    g_days_in_month = [
        31, 28, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    ]

    gy -= 1600
    gm -= 1
    gd -= 1

    g_day_no = (
        365 * gy
        + (gy + 3) // 4
        - (gy + 99) // 100
        + (gy + 399) // 400
    )

    for i in range(gm):
        g_day_no += g_days_in_month[i]

    if gm > 1 and (
        (gy + 1600) % 4 == 0
        and (
            (gy + 1600) % 100 != 0
            or (gy + 1600) % 400 == 0
        )
    ):
        g_day_no += 1

    g_day_no += gd
    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    j_month_days = [
        31, 31, 31, 31, 31, 31,
        30, 30, 30, 30, 30, 29
    ]

    jm = 1

    for days in j_month_days:
        if j_day_no < days:
            break
        j_day_no -= days
        jm += 1

    jd = j_day_no + 1

    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):

    jy -= 979

    j_day_no = (
        365 * jy
        + (jy // 33) * 8
        + ((jy % 33) + 3) // 4
    )

    j_month_days = [
        31, 31, 31, 31, 31, 31,
        30, 30, 30, 30, 30, 30
    ]

    for i in range(jm - 1):
        j_day_no += j_month_days[i]

    j_day_no += jd - 1
    g_day_no = j_day_no + 79

    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097

    leap = True

    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524

        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365

    g_days_in_month = [
        31, 29 if leap else 28,
        31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    ]

    gm = 1

    for days in g_days_in_month:
        if g_day_no < days:
            break
        g_day_no -= days
        gm += 1

    gd = g_day_no + 1

    return gy, gm, gd


def today_jalali():

    today = date.today()

    jy, jm, jd = gregorian_to_jalali(
        today.year, today.month, today.day
    )

    return "{:04d}/{:02d}/{:02d}".format(jy, jm, jd)


def jalali_month_days(year, month):

    if month <= 6:
        return 31

    if month <= 11:
        return 30

    current = jalali_to_gregorian(year, 12, 1)
    next_year = jalali_to_gregorian(year + 1, 1, 1)

    from datetime import date as gdate

    return (
        gdate(*next_year) - gdate(*current)
    ).days


# ==========================================
# پنجره تقویم شمسی
# ==========================================

class JalaliCalendarDialog(QDialog):

    month_names = [
        "فروردین", "اردیبهشت", "خرداد",
        "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر",
        "دی", "بهمن", "اسفند"
    ]

    weekdays = [
        "شنبه", "یکشنبه", "دوشنبه",
        "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"
    ]

    def __init__(self, parent=None, initial_date=None):

        super().__init__(parent)

        self.setWindowTitle("انتخاب تاریخ")
        self.setFixedSize(440, 370)
        self.setLayoutDirection(Qt.RightToLeft)

        if initial_date:
            try:
                parts = initial_date.split("/")
                self.year = int(parts[0])
                self.month = int(parts[1])
                self.day = int(parts[2])
            except Exception:
                self.set_today()
        else:
            self.set_today()

        self.selected_date = None
        self.main_layout = QVBoxLayout(self)
        self.navigation_layout = QHBoxLayout()

        self.btn_previous = QPushButton("ماه قبل")
        self.btn_next = QPushButton("ماه بعد")

        self.lbl_month = QLabel()
        self.lbl_month.setAlignment(Qt.AlignCenter)

        self.navigation_layout.addWidget(self.btn_previous)
        self.navigation_layout.addWidget(self.lbl_month)
        self.navigation_layout.addWidget(self.btn_next)

        self.main_layout.addLayout(self.navigation_layout)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(2)
        self.grid.setVerticalSpacing(3)
        self.grid.setContentsMargins(8, 8, 8, 8)

        self.main_layout.addLayout(self.grid)

        self.btn_previous.clicked.connect(self.previous_month)
        self.btn_next.clicked.connect(self.next_month)

        self.draw_calendar()

    def set_today(self):

        value = today_jalali().split("/")
        self.year = int(value[0])
        self.month = int(value[1])
        self.day = int(value[2])

    def previous_month(self):

        self.month -= 1

        if self.month < 1:
            self.month = 12
            self.year -= 1

        self.draw_calendar()

    def next_month(self):

        self.month += 1

        if self.month > 12:
            self.month = 1
            self.year += 1

        self.draw_calendar()

    def draw_calendar(self):

        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.lbl_month.setText(
            "{} {}".format(
                self.month_names[self.month - 1],
                self.year
            )
        )

        for col, name in enumerate(self.weekdays):

            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumWidth(56)

            color = "#C0392B" if col == 6 else "#183B56"

            label.setStyleSheet(
                "font-family:Tahoma;"
                "font-size:8pt;"
                "font-weight:bold;"
                "padding:0px;"
                "color:{};".format(color)
            )

            self.grid.addWidget(label, 0, col)

        gy, gm, gd = jalali_to_gregorian(
            self.year, self.month, 1
        )

        first_date = date(gy, gm, gd)
        start_column = (first_date.weekday() + 2) % 7

        days_count = jalali_month_days(
            self.year, self.month
        )

        today_parts = today_jalali().split("/")
        today_year = int(today_parts[0])
        today_month = int(today_parts[1])
        today_day = int(today_parts[2])

        for day_number in range(1, days_count + 1):

            position = start_column + day_number - 1
            row = position // 7 + 1
            col = position % 7

            btn = QPushButton(str(day_number))
            btn.setFixedSize(42, 36)

            is_today = (
                self.year == today_year
                and self.month == today_month
                and day_number == today_day
            )

            if is_today:
                btn.setStyleSheet("""
                    font-family:Tahoma;
                    font-size:10pt;
                    font-weight:bold;
                    color:#183B56;
                    background:#D4AF37;
                    border:1px solid #B89525;
                    border-radius:4px;
                """)
            elif col == 6:
                btn.setStyleSheet("""
                    font-family:Tahoma;
                    font-size:10pt;
                    color:#C0392B;
                    background:white;
                    border:1px solid #D5DDE5;
                    border-radius:4px;
                """)
            else:
                btn.setStyleSheet("""
                    font-family:Tahoma;
                    font-size:10pt;
                    color:#183B56;
                    background:white;
                    border:1px solid #D5DDE5;
                    border-radius:4px;
                """)

            btn.clicked.connect(
                lambda checked=False, d=day_number:
                self.choose_date(d)
            )

            self.grid.addWidget(
                btn, row, col, Qt.AlignCenter
            )

    def choose_date(self, day_number):

        self.selected_date = "{:04d}/{:02d}/{:02d}".format(
            self.year, self.month, day_number
        )

        self.accept()


# ==========================================
# پنجره انتخاب چندگیرنده
# ==========================================

class ReceiverDialog(QDialog):

    def __init__(self, parent=None, selected_ids=None):

        super().__init__(parent)

        self.setWindowTitle("انتخاب گیرندگان نامه")
        self.setMinimumSize(430, 520)
        self.setLayoutDirection(Qt.RightToLeft)

        self.selected_ids = []

        if selected_ids:
            self.selected_ids = list(selected_ids)

        self.people = []

        self.setStyleSheet("""
            QDialog {
                background: #F3F6F9;
                font-family: Tahoma;
                color: #183B56;
            }

            QLineEdit {
                background: white;
                border: 1px solid #CBD5DF;
                border-radius: 6px;
                padding: 8px;
                min-height: 28px;
            }

            QListWidget {
                background: white;
                border: 1px solid #CBD5DF;
                border-radius: 7px;
                padding: 5px;
            }

            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
            }

            QListWidget::item:selected {
                background: #DCE8F0;
                color: #183B56;
            }

            QPushButton {
                background: #183B56;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                min-height: 28px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #285577;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("گیرندگان نامه را انتخاب کنید")
        title.setStyleSheet(
            "font-size:12pt;font-weight:bold;padding:5px;"
        )
        layout.addWidget(title)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "جستجوی نام گیرنده..."
        )
        layout.addWidget(self.txt_search)

        self.lst_people = QListWidget()
        self.lst_people.setSelectionMode(
            QAbstractItemView.MultiSelection
        )
        layout.addWidget(self.lst_people, 1)

        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet(
            "color:#687D8D;font-weight:bold;"
        )
        layout.addWidget(self.lbl_count)

        buttons = QHBoxLayout()

        self.btn_select_all = QPushButton("انتخاب همه")
        self.btn_clear = QPushButton("لغو انتخاب‌ها")
        self.btn_ok = QPushButton("تأیید")
        self.btn_cancel = QPushButton("انصراف")

        buttons.addWidget(self.btn_select_all)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch()
        buttons.addWidget(self.btn_ok)
        buttons.addWidget(self.btn_cancel)

        layout.addLayout(buttons)

        self.txt_search.textChanged.connect(self.filter_people)
        self.lst_people.itemClicked.connect(self.update_selection_order)

        self.btn_select_all.clicked.connect(self.select_all_visible)
        self.btn_clear.clicked.connect(self.clear_selection)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self.load_people()

    def load_people(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT PersonID, PersonName
            FROM Persons
            ORDER BY PersonName
        """)

        self.people = cursor.fetchall()
        conn.close()

        available_ids = [
            int(row[0]) for row in self.people
        ]

        self.selected_ids = [
            person_id
            for person_id in self.selected_ids
            if person_id in available_ids
        ]

        self.lst_people.clear()

        for person_id, person_name in self.people:

            item = QListWidgetItem(person_name)
            item.setData(Qt.UserRole, int(person_id))

            self.lst_people.addItem(item)

            if int(person_id) in self.selected_ids:
                item.setSelected(True)

        self.update_count()

    def update_selection_order(self, item):

        person_id = int(item.data(Qt.UserRole))

        if item.isSelected():

            if person_id not in self.selected_ids:
                self.selected_ids.append(person_id)

        else:

            if person_id in self.selected_ids:
                self.selected_ids.remove(person_id)

        self.update_count()

    def filter_people(self, text):

        text = text.strip().lower()

        for index in range(self.lst_people.count()):

            item = self.lst_people.item(index)

            item.setHidden(
                text not in item.text().lower()
            )

    def select_all_visible(self):

        for index in range(self.lst_people.count()):

            item = self.lst_people.item(index)

            if not item.isHidden():

                person_id = int(item.data(Qt.UserRole))

                if not item.isSelected():
                    item.setSelected(True)

                if person_id not in self.selected_ids:
                    self.selected_ids.append(person_id)

        self.update_count()

    def clear_selection(self):

        for index in range(self.lst_people.count()):
            self.lst_people.item(index).setSelected(False)

        self.selected_ids = []
        self.update_count()

    def update_count(self):

        self.lbl_count.setText(
            "تعداد گیرندگان انتخاب‌شده: {}".format(
                len(self.selected_ids)
            )
        )

    def get_selected_ids(self):

        return list(self.selected_ids)

    def get_selected_names(self):

        names = []

        for person_id in self.selected_ids:

            for record_id, name in self.people:

                if int(record_id) == person_id:
                    names.append(name)
                    break

        return names


# ==========================================
# فرم مدیریت نامه‌های اداری
# ==========================================

class LettersForm(QWidget):

    def __init__(self):

        super().__init__()

        self.current_letter_id = None
        self.template_path = None
        self.template_is_personal = False
        self.selected_receiver_ids = []

        self.setWindowTitle("مدیریت نامه‌های اداری")
        self.resize(1250, 900)
        self.setMinimumSize(1050, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        self.setStyleSheet("""
            QWidget {
                background-color: #F3F6F9;
                color: #183B56;
                font-family: Tahoma;
                font-size: 9pt;
            }

            QLineEdit, QComboBox, QSpinBox, QFontComboBox {
                background: white;
                border: 1px solid #CBD5DF;
                border-radius: 6px;
                padding: 5px 8px;
                min-height: 25px;
            }

            QTextEdit {
                background: white;
                border: 1px solid #B8C7D4;
                border-radius: 7px;
                padding: 10px;
                font-size: 12pt;
                selection-background-color: #D4AF37;
                selection-color: #183B56;
            }

            QListWidget {
                background: white;
                border: 1px solid #CBD5DF;
                border-radius: 6px;
                padding: 4px;
            }

            QListWidget::item {
                padding: 5px;
                border-radius: 4px;
            }

            QListWidget::item:selected {
                background: #DCE8F0;
                color: #183B56;
            }

            QPushButton {
                background-color: #183B56;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                min-height: 27px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #285577;
            }

            QPushButton:pressed {
                background-color: #102B40;
            }

            QPushButton:checked {
                background-color: #D4AF37;
                color: #183B56;
            }

            QTableWidget {
                background: white;
                alternate-background-color: #F2F6F9;
                gridline-color: #E1E7EC;
                border: 1px solid #D5DDE5;
                border-radius: 6px;
                selection-background-color: #D4AF37;
                selection-color: #183B56;
            }

            QHeaderView::section {
                background: #183B56;
                color: white;
                padding: 7px;
                border: none;
                font-weight: bold;
            }

            QLabel {
                color: #183B56;
            }
        """)

        self.init_ui()
        self.load_combos()
        self.load_letters()
        self.clear_form()

    # ======================================
    # تازه‌سازی گیرندگان
    # ======================================

    def showEvent(self, event):

        super().showEvent(event)
        self.update_receiver_display()

    def refresh_receivers(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT PersonID, PersonName
            FROM Persons
            ORDER BY PersonName
        """)

        records = cursor.fetchall()
        conn.close()

        available_ids = [
            int(row[0]) for row in records
        ]

        self.selected_receiver_ids = [
            person_id
            for person_id in self.selected_receiver_ids
            if person_id in available_ids
        ]

        return records

    def update_receiver_display(self):

        records = self.refresh_receivers()

        name_map = {
            int(row[0]): row[1]
            for row in records
        }

        names = [
            name_map[person_id]
            for person_id in self.selected_receiver_ids
            if person_id in name_map
        ]

        self.txt_receivers.setText("، ".join(names))

        self.lbl_receiver_count.setText(
            "تعداد: {}".format(len(names))
        )

    def open_receiver_dialog(self):

        dialog = ReceiverDialog(
            self,
            self.selected_receiver_ids
        )

        if dialog.exec_() == QDialog.Accepted:

            self.selected_receiver_ids = (
                dialog.get_selected_ids()
            )

            self.update_receiver_display()
            self.update_template_for_receivers()

    # ======================================
    # طراحی رابط کاربری
    # ======================================

    def init_ui(self):

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        title = QLabel("مدیریت نامه‌های اداری")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 15pt;
            font-weight: bold;
            color: #183B56;
            padding: 5px;
        """)

        main_layout.addWidget(title)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        search_layout.addWidget(QLabel("جستجوی نامه:"))

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "شماره نامه، متن نامه یا نام گیرنده..."
        )

        search_layout.addWidget(self.txt_search)
        main_layout.addLayout(search_layout)

        self.txt_search.textChanged.connect(self.load_letters)

        info_layout = QGridLayout()
        info_layout.setHorizontalSpacing(12)
        info_layout.setVerticalSpacing(7)

        self.txt_number = QLineEdit()

        self.txt_date = QLineEdit()
        self.txt_date.setReadOnly(True)

        self.btn_calendar = QPushButton("تقویم")
        self.btn_calendar.setMaximumWidth(75)

        date_layout = QHBoxLayout()
        date_layout.setSpacing(5)
        date_layout.addWidget(self.txt_date)
        date_layout.addWidget(self.btn_calendar)

        date_widget = QWidget()
        date_widget.setLayout(date_layout)

        self.btn_calendar.clicked.connect(self.open_calendar)

        self.cbo_subject = QComboBox()
        self.cbo_signator = QComboBox()

        info_layout.addWidget(QLabel("شماره نامه:"), 0, 0)
        info_layout.addWidget(self.txt_number, 0, 1)
        info_layout.addWidget(QLabel("تاریخ نامه:"), 0, 2)
        info_layout.addWidget(date_widget, 0, 3)
        info_layout.addWidget(QLabel("موضوع:"), 1, 0)
        info_layout.addWidget(self.cbo_subject, 1, 1)
        info_layout.addWidget(QLabel("امضاکننده:"), 1, 2)
        info_layout.addWidget(self.cbo_signator, 1, 3)

        info_layout.setColumnStretch(1, 2)
        info_layout.setColumnStretch(3, 2)

        main_layout.addLayout(info_layout)

        # گیرندگان

        receiver_layout = QHBoxLayout()
        receiver_layout.setSpacing(8)

        receiver_layout.addWidget(QLabel("گیرندگان:"))

        self.txt_receivers = QLineEdit()
        self.txt_receivers.setReadOnly(True)
        self.txt_receivers.setPlaceholderText(
            "هنوز گیرنده‌ای انتخاب نشده است"
        )

        self.btn_receivers = QPushButton("انتخاب گیرندگان")
        self.btn_receivers.setMaximumWidth(130)

        self.lbl_receiver_count = QLabel("تعداد: ۰")
        self.lbl_receiver_count.setMinimumWidth(65)

        receiver_layout.addWidget(self.txt_receivers, 1)
        receiver_layout.addWidget(self.btn_receivers)
        receiver_layout.addWidget(self.lbl_receiver_count)

        main_layout.addLayout(receiver_layout)

        self.btn_receivers.clicked.connect(
            self.open_receiver_dialog
        )

        # نوار ابزار ویرایشگر

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(5)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Tahoma", 12))
        self.font_combo.setMaximumWidth(155)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(12)
        self.font_size.setMaximumWidth(65)

        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setMaximumWidth(38)
        self.btn_bold.setToolTip("ضخیم")

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setMaximumWidth(38)
        self.btn_italic.setToolTip("مورب")

        self.btn_underline = QPushButton("U")
        self.btn_underline.setCheckable(True)
        self.btn_underline.setMaximumWidth(38)
        self.btn_underline.setToolTip("زیرخط")

        self.btn_color = QPushButton("رنگ")
        self.btn_color.setMaximumWidth(55)

        self.btn_right = QPushButton("راست‌چین")
        self.btn_center = QPushButton("وسط‌چین")
        self.btn_left = QPushButton("چپ‌چین")

        toolbar_layout.addWidget(self.font_combo)
        toolbar_layout.addWidget(self.font_size)
        toolbar_layout.addWidget(self.btn_bold)
        toolbar_layout.addWidget(self.btn_italic)
        toolbar_layout.addWidget(self.btn_underline)
        toolbar_layout.addWidget(self.btn_color)
        toolbar_layout.addWidget(self.btn_right)
        toolbar_layout.addWidget(self.btn_center)
        toolbar_layout.addWidget(self.btn_left)
        toolbar_layout.addStretch()

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)

        self.txt_body = QTextEdit()
        self.txt_body.setAcceptRichText(True)
        self.txt_body.setLayoutDirection(Qt.RightToLeft)
        self.txt_body.setFont(QFont("Tahoma", 12))
        self.txt_body.setMinimumHeight(280)
        self.txt_body.setPlaceholderText(
            "متن نامه را اینجا وارد کنید..."
        )

        self.font_combo.currentFontChanged.connect(self.change_font)
        self.font_size.valueChanged.connect(self.change_font_size)
        self.btn_bold.clicked.connect(self.toggle_bold)
        self.btn_italic.clicked.connect(self.toggle_italic)
        self.btn_underline.clicked.connect(self.toggle_underline)
        self.btn_color.clicked.connect(self.change_text_color)

        self.btn_right.clicked.connect(
            lambda: self.txt_body.setAlignment(Qt.AlignRight)
        )

        self.btn_center.clicked.connect(
            lambda: self.txt_body.setAlignment(Qt.AlignHCenter)
        )

        self.btn_left.clicked.connect(
            lambda: self.txt_body.setAlignment(Qt.AlignLeft)
        )

        editor_layout = QVBoxLayout()
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(5)

        editor_title = QLabel("متن نامه")
        editor_title.setStyleSheet(
            "font-size:10pt;font-weight:bold;color:#183B56;"
        )

        editor_layout.addWidget(editor_title)
        editor_layout.addWidget(toolbar_widget)
        editor_layout.addWidget(self.txt_body)

        editor_widget = QWidget()
        editor_widget.setLayout(editor_layout)

        main_layout.addWidget(editor_widget, 5)

        # پیوست‌ها

        attachment_layout = QHBoxLayout()
        attachment_layout.setSpacing(8)

        attachment_label = QLabel("پیوست‌ها:")
        attachment_label.setMinimumWidth(65)

        self.lst_attachments = QListWidget()
        self.lst_attachments.setMaximumHeight(55)

        self.btn_add_attachment = QPushButton("افزودن پیوست")
        self.btn_remove_attachment = QPushButton("حذف پیوست")

        self.btn_add_attachment.setMaximumWidth(115)
        self.btn_remove_attachment.setMaximumWidth(105)

        attachment_layout.addWidget(attachment_label)
        attachment_layout.addWidget(self.lst_attachments)
        attachment_layout.addWidget(self.btn_add_attachment)
        attachment_layout.addWidget(self.btn_remove_attachment)

        main_layout.addLayout(attachment_layout)

        attachment_status_layout = QHBoxLayout()

        self.lbl_attachment_status = QLabel(
            "وضعیت پیوست: ندارد"
        )

        self.lbl_attachment_status.setStyleSheet(
            "font-weight:bold;color:#183B56;"
        )

        attachment_status_layout.addWidget(
            self.lbl_attachment_status
        )
        attachment_status_layout.addStretch()

        main_layout.addLayout(attachment_status_layout)

        self.btn_add_attachment.clicked.connect(self.add_attachments)
        self.btn_remove_attachment.clicked.connect(self.remove_attachment)
        self.lst_attachments.itemDoubleClicked.connect(self.open_attachment)

        # دکمه‌های اصلی

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.btn_new = QPushButton("نامه جدید")
        self.btn_save = QPushButton("ذخیره نامه")
        self.btn_delete = QPushButton("حذف نامه")
        self.btn_clear = QPushButton("پاک کردن فرم")

        self.btn_save.setStyleSheet(
            "background-color:#D4AF37;color:#183B56;"
        )

        buttons_layout.addWidget(self.btn_new)
        buttons_layout.addWidget(self.btn_save)
        buttons_layout.addWidget(self.btn_delete)
        buttons_layout.addWidget(self.btn_clear)

        main_layout.addLayout(buttons_layout)

        self.btn_new.clicked.connect(self.clear_form)
        self.btn_save.clicked.connect(self.save_letter)
        self.btn_delete.clicked.connect(self.delete_letter)
        self.btn_clear.clicked.connect(self.clear_form)

        # خروجی Word

        word_layout = QHBoxLayout()
        word_layout.setSpacing(8)

        self.btn_select_template = QPushButton("انتخاب قالب Word")
        self.btn_create_word = QPushButton("ساخت فایل Word")

        self.btn_select_template.clicked.connect(
            self.select_word_template
        )

        self.btn_create_word.clicked.connect(
            self.create_word_file
        )

        word_layout.addWidget(self.btn_select_template)
        word_layout.addWidget(self.btn_create_word)

        self.lbl_template = QLabel("قالب Word انتخاب نشده است")
        self.lbl_template.setStyleSheet(
            "color:#687D8D;font-size:8pt;"
        )

        word_layout.addWidget(self.lbl_template, 1)
        main_layout.addLayout(word_layout)

        # جدول نامه‌ها

        self.table = QTableWidget()
        self.table.setColumnCount(6)

        self.table.setHorizontalHeaderLabels([
            "شناسه", "شماره نامه", "تاریخ",
            "موضوع", "امضاکننده", "گیرندگان"
        ])

        self.table.setColumnHidden(0, True)

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMaximumHeight(175)

        self.table.itemSelectionChanged.connect(self.select_letter)

        main_layout.addWidget(self.table, 2)

    # ======================================
    # توابع ویرایشگر متن
    # ======================================

    def change_font(self, font):

        self.txt_body.setFocus()
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        self.txt_body.mergeCurrentCharFormat(fmt)

    def change_font_size(self, size):

        self.txt_body.setFocus()
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self.txt_body.mergeCurrentCharFormat(fmt)

    def toggle_bold(self):

        fmt = QTextCharFormat()

        if self.btn_bold.isChecked():
            fmt.setFontWeight(QFont.Bold)
        else:
            fmt.setFontWeight(QFont.Normal)

        self.txt_body.mergeCurrentCharFormat(fmt)
        self.txt_body.setFocus()

    def toggle_italic(self):

        fmt = QTextCharFormat()
        fmt.setFontItalic(self.btn_italic.isChecked())
        self.txt_body.mergeCurrentCharFormat(fmt)
        self.txt_body.setFocus()

    def toggle_underline(self):

        fmt = QTextCharFormat()
        fmt.setFontUnderline(self.btn_underline.isChecked())
        self.txt_body.mergeCurrentCharFormat(fmt)
        self.txt_body.setFocus()

    def change_text_color(self):

        color = QColorDialog.getColor(
            QColor("#183B56"), self, "انتخاب رنگ متن"
        )

        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.txt_body.mergeCurrentCharFormat(fmt)
            self.txt_body.setFocus()

    # ======================================
    # تقویم
    # ======================================

    def open_calendar(self):

        dialog = JalaliCalendarDialog(self, self.txt_date.text())

        if dialog.exec_() == QDialog.Accepted:
            if dialog.selected_date:
                self.txt_date.setText(dialog.selected_date)

    # ======================================
    # انتخاب قالب Word
    # ======================================

    def select_word_template(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "انتخاب قالب Word",
            "",
            "Word Files (*.docx *.doc)"
        )

        if not file_path:
            return

        self.template_path = os.path.abspath(file_path)
        self.template_is_personal = False

        self.lbl_template.setText(
            "قالب دستی: " + os.path.basename(file_path)
        )

        QMessageBox.information(
            self, "قالب Word",
            "قالب Word با موفقیت انتخاب شد."
        )

    # ======================================
    # انتخاب خودکار قالب اختصاصی گیرنده
    # ======================================

    def update_template_for_receivers(self):

        # قالب اختصاصی اولین گیرنده انتخاب‌شده ملاک است

        if self.selected_receiver_ids:

            first_person_id = self.selected_receiver_ids[0]

            conn = get_connection()
            cursor = conn.cursor()

            try:

                cursor.execute("""
                    SELECT TemplatePath
                    FROM Persons
                    WHERE PersonID = ?
                """, (first_person_id,))

                record = cursor.fetchone()

            finally:
                conn.close()

            personal_path = ""

            if record and record[0]:
                personal_path = str(record[0]).strip()

            if personal_path:

                self.template_path = personal_path
                self.template_is_personal = True

                if os.path.isfile(personal_path):

                    self.lbl_template.setText(
                        "قالب اختصاصی: "
                        + os.path.basename(personal_path)
                    )

                else:

                    self.lbl_template.setText(
                        "قالب اختصاصی پیدا نشد: "
                        + os.path.basename(personal_path)
                    )

                return

        # اگر قالب قبلی اختصاصی بوده و گیرنده اول جدید قالب ندارد،
        # قالب اختصاصی قبلی پاک می‌شود.
        # قالب دستی انتخاب‌شده توسط کاربر حفظ می‌شود.

        if self.template_is_personal:

            self.template_path = None
            self.template_is_personal = False

            self.lbl_template.setText(
                "قالب Word انتخاب نشده است"
            )

    # ======================================
    # جایگزینی Bookmark در Word
    # ======================================

    def replace_word_bookmark(self, document, bookmark_name, value):

        if not document.Bookmarks.Exists(bookmark_name):
            raise Exception(
                "Bookmark زیر در قالب Word وجود ندارد: "
                + bookmark_name
            )

        bookmark_range = document.Bookmarks(bookmark_name).Range
        bookmark_range.Text = str(value)

        document.Bookmarks.Add(bookmark_name, bookmark_range)

    # ======================================
    # دریافت تعداد پیوست‌های نامه
    # ======================================

    def get_attachment_count(self):

        if self.current_letter_id is None:
            return 0

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM Attachments
            WHERE LetterID = ?
        """, (self.current_letter_id,))

        result = cursor.fetchone()
        conn.close()

        return int(result[0]) if result else 0

    def get_attachment_text(self):

        count = self.get_attachment_count()

        if count == 0:
            return "ندارد"

        persian_digits = str.maketrans(
            "0123456789",
            "۰۱۲۳۴۵۶۷۸۹"
        )

        return "دارد - تعداد: {}".format(
            str(count).translate(persian_digits)
        )

    # ======================================
    # ساخت فایل Word
    # ======================================

    def create_word_file(self):

        if not self.template_path:

            QMessageBox.warning(
                self, "قالب Word",
                "ابتدا قالب Word را انتخاب کنید."
            )
            return

        if not os.path.isfile(self.template_path):

            QMessageBox.warning(
                self, "قالب Word",
                "فایل قالب پیدا نشد."
            )
            return

        letter_number = self.txt_number.text().strip()
        letter_date = self.txt_date.text().strip()

        if not letter_number:
            QMessageBox.warning(self, "توجه", "شماره نامه را وارد کنید.")
            return

        if not letter_date:
            QMessageBox.warning(self, "توجه", "تاریخ نامه را انتخاب کنید.")
            return

        self.update_receiver_display()

        # دریافت نام گیرندگان به ترتیب انتخاب
        # نام هر گیرنده در یک خط جداگانه درج می‌شود

        receiver_names = []

        if self.selected_receiver_ids:

            conn = get_connection()
            cursor = conn.cursor()

            try:

                for person_id in self.selected_receiver_ids:

                    cursor.execute("""
                        SELECT PersonName
                        FROM Persons
                        WHERE PersonID = ?
                    """, (person_id,))

                    record = cursor.fetchone()

                    if record and record[0]:
                        receiver_names.append(record[0])

            finally:
                conn.close()

        receiver_text = "\r".join(receiver_names)

        signator_text = self.cbo_signator.currentText()

        body_html = self.txt_body.toHtml()
        body_plain = self.txt_body.toPlainText().strip()

        attachment_text = self.get_attachment_text()

        default_name = "Letter_{}.docx".format(letter_number)

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره فایل Word",
            default_name,
            "Word Document (*.docx)"
        )

        if not output_path:
            return

        if not output_path.lower().endswith(".docx"):
            output_path += ".docx"

        word = None
        document = None
        temp_html_path = None

        try:

            import win32com.client

            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = True
            word.DisplayAlerts = 0

            document = word.Documents.Open(
                os.path.abspath(self.template_path)
            )

            required_bookmarks = [
                "LetterNumber",
                "LetterDate",
                "Receiver",
                "Signator",
                "LetterBody",
                "Attachment"
            ]

            missing_bookmarks = []

            for name in required_bookmarks:
                if not document.Bookmarks.Exists(name):
                    missing_bookmarks.append(name)

            if missing_bookmarks:
                raise Exception(
                    "این Bookmarkها در فایل Word پیدا نشدند:\n"
                    + "\n".join(missing_bookmarks)
                )

            self.replace_word_bookmark(
                document, "LetterNumber", letter_number
            )

            self.replace_word_bookmark(
                document, "LetterDate", letter_date
            )

            self.replace_word_bookmark(
                document, "Receiver", receiver_text
            )

            self.replace_word_bookmark(
                document, "Signator", signator_text
            )

            self.replace_word_bookmark(
                document, "Attachment", attachment_text
            )

            body_range = document.Bookmarks("LetterBody").Range
            body_start = body_range.Start
            body_range.Text = ""

            if body_plain:

                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".html"
                )

                temp_html_path = temp_file.name
                temp_file.close()

                with open(
                    temp_html_path,
                    "w",
                    encoding="utf-8-sig",
                    newline=""
                ) as file:
                    file.write(body_html)

                insert_range = document.Range(body_start, body_start)
                insert_range.InsertFile(temp_html_path)

                body_end = insert_range.End

                document.Bookmarks.Add(
                    "LetterBody",
                    document.Range(body_start, body_end)
                )

            else:

                document.Bookmarks.Add(
                    "LetterBody",
                    document.Range(body_start, body_start)
                )

            document.SaveAs(
                os.path.abspath(output_path),
                FileFormat=16
            )

            if temp_html_path and os.path.isfile(temp_html_path):
                try:
                    os.remove(temp_html_path)
                except Exception:
                    pass

                temp_html_path = None

            QMessageBox.information(
                self,
                "موفق",
                "فایل Word با موفقیت ساخته شد:\n\n"
                + output_path
                + "\n\nوضعیت پیوست: "
                + attachment_text
            )

        except ImportError:

            QMessageBox.critical(
                self,
                "خطای کتابخانه",
                "کتابخانه pywin32 نصب نیست.\n\n"
                "دستور زیر را اجرا کن:\n"
                "py -m pip install pywin32"
            )

        except Exception as e:

            if document is not None:
                try:
                    document.Close(SaveChanges=False)
                except Exception:
                    pass

            if word is not None:
                try:
                    word.Quit()
                except Exception:
                    pass

            QMessageBox.critical(
                self, "خطا در ساخت فایل Word", str(e)
            )

        finally:

            if temp_html_path and os.path.isfile(temp_html_path):
                try:
                    os.remove(temp_html_path)
                except Exception:
                    pass

    # ======================================
    # بارگذاری کمبوباکس‌ها
    # ======================================

    def load_combos(self):

        conn = get_connection()
        cursor = conn.cursor()

        self.cbo_subject.clear()
        self.cbo_signator.clear()

        cursor.execute("""
            SELECT SubjectID, SubjectName
            FROM Subjects
            ORDER BY SubjectName
        """)

        for record in cursor.fetchall():
            self.cbo_subject.addItem(record[1], record[0])

        cursor.execute("""
            SELECT SignatorID, SignatorName
            FROM Signators
            ORDER BY SignatorName
        """)

        for record in cursor.fetchall():
            self.cbo_signator.addItem(record[1], record[0])

        conn.close()

    # ======================================
    # بارگذاری فهرست نامه‌ها
    # ======================================

    def load_letters(self):

        search_text = self.txt_search.text().strip()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                L.LetterID,
                L.LetterNumber,
                L.LetterDate,
                COALESCE(S.SubjectName, ''),
                COALESCE(SG.SignatorName, ''),
                COALESCE(
                    (
                        SELECT GROUP_CONCAT(P.PersonName, '، ')
                        FROM LetterPersons LP
                        JOIN Persons P
                            ON P.PersonID = LP.PersonID
                        WHERE LP.LetterID = L.LetterID
                    ),
                    ''
                )
            FROM Letters L
            LEFT JOIN Subjects S
                ON S.SubjectID = L.SubjectID
            LEFT JOIN Signators SG
                ON SG.SignatorID = L.SignatorID
            WHERE
                L.LetterNumber LIKE ?
                OR L.LetterBody LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM LetterPersons LP
                    JOIN Persons P
                        ON P.PersonID = LP.PersonID
                    WHERE LP.LetterID = L.LetterID
                    AND P.PersonName LIKE ?
                )
            ORDER BY L.LetterID DESC
        """, (
            "%" + search_text + "%",
            "%" + search_text + "%",
            "%" + search_text + "%"
        ))

        records = cursor.fetchall()
        conn.close()

        self.table.setRowCount(0)

        for row_number, record in enumerate(records):

            self.table.insertRow(row_number)

            for column, value in enumerate(record):

                item = QTableWidgetItem(
                    str(value) if value is not None else ""
                )

                self.table.setItem(row_number, column, item)

    # ======================================
    # انتخاب نامه از جدول
    # ======================================

    def select_letter(self):

        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows:
            return

        row = selected_rows[0].row()

        self.current_letter_id = int(
            self.table.item(row, 0).text()
        )

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                LetterNumber,
                LetterDate,
                SubjectID,
                SignatorID,
                LetterBody
            FROM Letters
            WHERE LetterID = ?
        """, (self.current_letter_id,))

        record = cursor.fetchone()

        if record is None:
            conn.close()
            return

        self.txt_number.setText(record[0] or "")
        self.txt_date.setText(record[1] or "")

        self.set_combo_value(self.cbo_subject, record[2])
        self.set_combo_value(self.cbo_signator, record[3])

        self.txt_body.setHtml(record[4] or "")

        cursor.execute("""
            SELECT PersonID
            FROM LetterPersons
            WHERE LetterID = ?
            ORDER BY LetterPersonID
        """, (self.current_letter_id,))

        receiver_ids = [
            int(item[0]) for item in cursor.fetchall()
        ]

        conn.close()

        self.selected_receiver_ids = receiver_ids
        self.update_receiver_display()
        self.update_template_for_receivers()

        self.load_attachments()

    def set_combo_value(self, combo, value):

        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(-1)

    # ======================================
    # ذخیره نامه
    # ======================================

    def save_letter(self):

        letter_number = self.txt_number.text().strip()
        letter_date = self.txt_date.text().strip()
        letter_body = self.txt_body.toHtml()

        if not letter_number:
            QMessageBox.warning(self, "توجه", "شماره نامه را وارد کنید.")
            return

        if not letter_date:
            QMessageBox.warning(self, "توجه", "تاریخ نامه را انتخاب کنید.")
            return

        subject_id = self.cbo_subject.currentData()
        signator_id = self.cbo_signator.currentData()

        available_records = self.refresh_receivers()

        available_ids = set(
            int(row[0]) for row in available_records
        )

        receiver_ids = [
            person_id
            for person_id in self.selected_receiver_ids
            if person_id in available_ids
        ]

        conn = get_connection()
        cursor = conn.cursor()

        try:

            if self.current_letter_id is None:

                cursor.execute("""
                    INSERT INTO Letters
                    (
                        LetterNumber,
                        LetterDate,
                        SubjectID,
                        SignatorID,
                        LetterBody
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    letter_number,
                    letter_date,
                    subject_id,
                    signator_id,
                    letter_body
                ))

                self.current_letter_id = cursor.lastrowid

            else:

                cursor.execute("""
                    UPDATE Letters
                    SET
                        LetterNumber = ?,
                        LetterDate = ?,
                        SubjectID = ?,
                        SignatorID = ?,
                        LetterBody = ?
                    WHERE LetterID = ?
                """, (
                    letter_number,
                    letter_date,
                    subject_id,
                    signator_id,
                    letter_body,
                    self.current_letter_id
                ))

                cursor.execute("""
                    DELETE FROM LetterPersons
                    WHERE LetterID = ?
                """, (self.current_letter_id,))

            for person_id in receiver_ids:

                cursor.execute("""
                    INSERT INTO LetterPersons
                    (LetterID, PersonID)
                    VALUES (?, ?)
                """, (
                    self.current_letter_id,
                    person_id
                ))

            conn.commit()
            conn.close()

            self.selected_receiver_ids = receiver_ids
            self.update_receiver_display()

            self.load_letters()
            self.load_attachments()

            QMessageBox.information(
                self, "موفق", "نامه با موفقیت ذخیره شد."
            )

        except Exception as e:

            conn.rollback()
            conn.close()

            QMessageBox.critical(
                self, "خطا در ذخیره نامه", str(e)
            )

    # ======================================
    # حذف نامه
    # ======================================

    def delete_letter(self):

        if self.current_letter_id is None:
            QMessageBox.warning(
                self, "توجه", "ابتدا یک نامه انتخاب کنید."
            )
            return

        answer = QMessageBox.question(
            self,
            "حذف نامه",
            "آیا از حذف این نامه و پیوست‌های آن مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        conn = get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT FilePath
                FROM Attachments
                WHERE LetterID = ?
            """, (self.current_letter_id,))

            attachment_paths = [
                row[0] for row in cursor.fetchall()
            ]

            cursor.execute("""
                DELETE FROM Attachments
                WHERE LetterID = ?
            """, (self.current_letter_id,))

            cursor.execute("""
                DELETE FROM LetterPersons
                WHERE LetterID = ?
            """, (self.current_letter_id,))

            cursor.execute("""
                DELETE FROM Letters
                WHERE LetterID = ?
            """, (self.current_letter_id,))

            conn.commit()
            conn.close()

            for path in attachment_paths:
                if path and os.path.isfile(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

            self.clear_form()
            self.load_letters()

            QMessageBox.information(
                self, "موفق", "نامه با موفقیت حذف شد."
            )

        except Exception as e:

            conn.rollback()
            conn.close()

            QMessageBox.critical(
                self, "خطا در حذف نامه", str(e)
            )

    # ======================================
    # پاک کردن فرم
    # ======================================

    def clear_form(self):

        self.current_letter_id = None
        self.selected_receiver_ids = []

        self.txt_number.clear()
        self.txt_date.setText(today_jalali())
        self.txt_body.clear()

        self.cbo_subject.setCurrentIndex(-1)
        self.cbo_signator.setCurrentIndex(-1)

        self.update_receiver_display()

        self.lst_attachments.clear()
        self.update_attachment_status()

        self.btn_bold.setChecked(False)
        self.btn_italic.setChecked(False)
        self.btn_underline.setChecked(False)

        self.font_combo.setCurrentFont(QFont("Tahoma", 12))
        self.font_size.setValue(12)

        self.txt_body.setAlignment(Qt.AlignRight)

        self.template_path = None
        self.template_is_personal = False

        self.lbl_template.setText(
            "قالب Word انتخاب نشده است"
        )

        self.table.clearSelection()

    # ======================================
    # افزودن پیوست
    # ======================================

    def add_attachments(self):

        if self.current_letter_id is None:
            QMessageBox.warning(
                self, "توجه", "ابتدا نامه را ذخیره کنید."
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "انتخاب فایل‌های پیوست", "", "All Files (*.*)"
        )

        if not files:
            return

        base_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        letters_folder = os.path.join(
            base_path, "attachments", str(self.current_letter_id)
        )

        conn = None

        try:

            os.makedirs(letters_folder, exist_ok=True)

            conn = get_connection()
            cursor = conn.cursor()

            for source_path in files:

                file_name = os.path.basename(source_path)

                destination = os.path.join(
                    letters_folder, file_name
                )

                name, ext = os.path.splitext(file_name)
                counter = 1

                while os.path.exists(destination):

                    file_name = "{}_{}{}".format(
                        name, counter, ext
                    )

                    destination = os.path.join(
                        letters_folder, file_name
                    )

                    counter += 1

                shutil.copy2(source_path, destination)

                cursor.execute("""
                    INSERT INTO Attachments
                    (
                        LetterID,
                        FileName,
                        FilePath
                    )
                    VALUES (?, ?, ?)
                """, (
                    self.current_letter_id,
                    file_name,
                    destination
                ))

            conn.commit()
            conn.close()
            conn = None

            self.load_attachments()

            QMessageBox.information(
                self, "موفق", "پیوست‌ها با موفقیت اضافه شدند."
            )

        except Exception as e:

            if conn is not None:
                conn.rollback()
                conn.close()

            QMessageBox.critical(
                self, "خطا در افزودن پیوست", str(e)
            )

    # ======================================
    # بارگذاری پیوست‌ها
    # ======================================

    def load_attachments(self):

        self.lst_attachments.clear()

        if self.current_letter_id is None:
            self.update_attachment_status()
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT AttachmentID, FileName, FilePath
            FROM Attachments
            WHERE LetterID = ?
            ORDER BY AttachmentID DESC
        """, (self.current_letter_id,))

        records = cursor.fetchall()
        conn.close()

        for record in records:

            item = QListWidgetItem(record[1])
            item.setData(Qt.UserRole, record[0])
            item.setData(Qt.UserRole + 1, record[2])

            self.lst_attachments.addItem(item)

        self.update_attachment_status()

    def update_attachment_status(self):

        count = self.lst_attachments.count()

        persian_count = str(count).translate(
            str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
        )

        if count == 0:
            text = "وضعیت پیوست: ندارد"
        else:
            text = "وضعیت پیوست: دارد - تعداد: {}".format(
                persian_count
            )

        self.lbl_attachment_status.setText(text)

    # ======================================
    # باز کردن پیوست
    # ======================================

    def open_attachment(self, item):

        file_path = item.data(Qt.UserRole + 1)

        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(
                self, "خطا", "فایل پیوست پیدا نشد."
            )
            return

        try:
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(
                self, "خطا در باز کردن فایل", str(e)
            )

    # ======================================
    # حذف پیوست
    # ======================================

    def remove_attachment(self):

        item = self.lst_attachments.currentItem()

        if item is None:
            QMessageBox.warning(
                self, "توجه", "ابتدا یک پیوست انتخاب کنید."
            )
            return

        answer = QMessageBox.question(
            self,
            "حذف پیوست",
            "آیا از حذف این پیوست مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        attachment_id = item.data(Qt.UserRole)
        file_path = item.data(Qt.UserRole + 1)

        conn = get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                DELETE FROM Attachments
                WHERE AttachmentID = ?
            """, (attachment_id,))

            conn.commit()
            conn.close()

            if file_path and os.path.isfile(file_path):
                os.remove(file_path)

            self.load_attachments()

        except Exception as e:

            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass

            QMessageBox.critical(
                self, "خطا در حذف پیوست", str(e)
            )
