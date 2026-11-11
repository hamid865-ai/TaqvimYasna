
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
    QFontComboBox, QSpinBox, QColorDialog,
    QDateEdit, QGroupBox, QCheckBox
)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCharFormat, QColor, QFont

from database.database import get_connection


# =========================================================
# توابع تاریخ شمسی
# =========================================================

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

    return jy, jm, j_day_no + 1


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

    return gy, gm, g_day_no + 1


def today_jalali():
    today = date.today()
    jy, jm, jd = gregorian_to_jalali(
        today.year, today.month, today.day
    )
    return "{:04d}/{:02d}/{:02d}".format(jy, jm, jd)




def get_next_letter_number(year=None, cursor=None, reserve=False):
    """Return the next compact Shamsi-year number; reserve inside a transaction."""
    if year is None:
        year = int(today_jalali().split("/")[0])

    own_connection = cursor is None
    connection = None
    if own_connection:
        connection = get_connection()
        cursor = connection.cursor()

    try:
        # Ensure the yearly sequence table exists even when the user is
        # running with an older local database module or database file.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LetterNumberSequences (
                ShamsiYear INTEGER PRIMARY KEY,
                LastNumber INTEGER NOT NULL DEFAULT 0
            )
        """)

        row = cursor.execute(
            "SELECT LastNumber FROM LetterNumberSequences WHERE ShamsiYear=?",
            (year,)
        ).fetchone()
        last_number = int(row[0]) if row else 0

        # Include older letters created before the sequence table existed.
        cursor.execute(
            "SELECT LetterNumber FROM Letters WHERE LetterNumber LIKE ?",
            (str(year) + "%",)
        )
        for record in cursor.fetchall():
            value = str(record[0] or "")
            suffix = value[4:]
            if value.startswith(str(year)) and suffix.isdigit():
                last_number = max(last_number, int(suffix))

        next_number = last_number + 1
        result = "{}{}".format(year, next_number)

        if reserve:
            cursor.execute(
                "INSERT OR REPLACE INTO LetterNumberSequences "
                "(ShamsiYear, LastNumber) VALUES (?, ?)",
                (year, next_number)
            )

        return result
    finally:
        if own_connection:
            connection.close()


def jalali_month_days(year, month):
    if month <= 6:
        return 31

    if month <= 11:
        return 30

    current = jalali_to_gregorian(year, 12, 1)
    next_year = jalali_to_gregorian(year + 1, 1, 1)

    from datetime import date as gdate

    return (gdate(*next_year) - gdate(*current)).days


# =========================================================
# تقویم شمسی
# =========================================================

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

        self.selected_date = None

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

        layout = QVBoxLayout(self)
        navigation = QHBoxLayout()

        self.btn_previous = QPushButton("ماه قبل")
        self.btn_next = QPushButton("ماه بعد")
        self.lbl_month = QLabel()
        self.lbl_month.setAlignment(Qt.AlignCenter)

        navigation.addWidget(self.btn_previous)
        navigation.addWidget(self.lbl_month)
        navigation.addWidget(self.btn_next)

        layout.addLayout(navigation)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(2)
        self.grid.setVerticalSpacing(3)
        self.grid.setContentsMargins(8, 8, 8, 8)

        layout.addLayout(self.grid)

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
                "font-family:Tahoma;font-size:8pt;"
                "font-weight:bold;padding:0px;color:{};".format(color)
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
        ty, tm, td = map(int, today_parts)

        for day_number in range(1, days_count + 1):
            position = start_column + day_number - 1
            row = position // 7 + 1
            col = position % 7

            btn = QPushButton(str(day_number))
            btn.setFixedSize(42, 36)

            is_today = (
                self.year == ty
                and self.month == tm
                and day_number == td
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

            self.grid.addWidget(btn, row, col, Qt.AlignCenter)

    def choose_date(self, day_number):
        self.selected_date = "{:04d}/{:02d}/{:02d}".format(
            self.year, self.month, day_number
        )
        self.accept()


# =========================================================
# انتخاب چند گیرنده
# =========================================================

class ReceiverDialog(QDialog):

    def __init__(self, parent=None, selected_ids=None):
        super().__init__(parent)

        self.setWindowTitle("انتخاب گیرندگان نامه")
        self.setMinimumSize(430, 520)
        self.setLayoutDirection(Qt.RightToLeft)

        self.selected_ids = list(selected_ids or [])
        self.people = []

        layout = QVBoxLayout(self)

        title = QLabel("گیرندگان نامه را انتخاب کنید")
        title.setStyleSheet(
            "font-size:12pt;font-weight:bold;padding:5px;"
        )
        layout.addWidget(title)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجوی نام گیرنده...")
        layout.addWidget(self.txt_search)

        self.lst_people = QListWidget()
        self.lst_people.setSelectionMode(
            QAbstractItemView.MultiSelection
        )
        layout.addWidget(self.lst_people, 1)

        self.lbl_count = QLabel()
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
        self.lst_people.itemClicked.connect(
            self.update_selection_order
        )

        self.btn_select_all.clicked.connect(
            self.select_all_visible
        )
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

        available_ids = [int(row[0]) for row in self.people]

        self.selected_ids = [
            pid for pid in self.selected_ids
            if pid in available_ids
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
            item.setHidden(text not in item.text().lower())

    def select_all_visible(self):
        for index in range(self.lst_people.count()):
            item = self.lst_people.item(index)

            if not item.isHidden():
                person_id = int(item.data(Qt.UserRole))
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


# =========================================================
# فرم مدیریت نامه‌ها
# =========================================================

class AdvancedSearchDialog(QDialog):
    """پنجره مستقل فیلترهای پیشرفته نامه‌ها."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("جستجوی پیشرفته نامه‌ها")
        self.setMinimumWidth(720)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("جستجوی پیشرفته نامه‌ها")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size:13pt;font-weight:bold;color:#183B56;padding:5px;"
        )
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.txt_filter_number = QLineEdit()
        self.txt_filter_number.setPlaceholderText("شماره نامه")
        self.txt_filter_receiver = QLineEdit()
        self.txt_filter_receiver.setPlaceholderText("نام گیرنده")
        self.txt_filter_body = QLineEdit()
        self.txt_filter_body.setPlaceholderText("عبارت داخل متن نامه")
        self.cbo_filter_subject = QComboBox()

        self.txt_date_from = QLineEdit()
        self.txt_date_from.setReadOnly(True)
        self.txt_date_from.setPlaceholderText("از تاریخ")
        self.txt_date_to = QLineEdit()
        self.txt_date_to.setReadOnly(True)
        self.txt_date_to.setPlaceholderText("تا تاریخ")

        self.btn_date_from = QPushButton("تقویم")
        self.btn_date_to = QPushButton("تقویم")

        from_layout = QHBoxLayout()
        from_layout.addWidget(self.txt_date_from, 1)
        from_layout.addWidget(self.btn_date_from)
        from_widget = QWidget()
        from_widget.setLayout(from_layout)

        to_layout = QHBoxLayout()
        to_layout.addWidget(self.txt_date_to, 1)
        to_layout.addWidget(self.btn_date_to)
        to_widget = QWidget()
        to_widget.setLayout(to_layout)

        grid.addWidget(QLabel("شماره نامه:"), 0, 0)
        grid.addWidget(self.txt_filter_number, 0, 1)
        grid.addWidget(QLabel("موضوع:"), 0, 2)
        grid.addWidget(self.cbo_filter_subject, 0, 3)
        grid.addWidget(QLabel("از تاریخ:"), 1, 0)
        grid.addWidget(from_widget, 1, 1)
        grid.addWidget(QLabel("تا تاریخ:"), 1, 2)
        grid.addWidget(to_widget, 1, 3)
        grid.addWidget(QLabel("گیرنده:"), 2, 0)
        grid.addWidget(self.txt_filter_receiver, 2, 1)
        grid.addWidget(QLabel("متن نامه:"), 2, 2)
        grid.addWidget(self.txt_filter_body, 2, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self.btn_apply_filter = QPushButton("اعمال فیلترها")
        self.btn_clear_filter = QPushButton("پاک کردن فیلترها")
        self.btn_cancel = QPushButton("بستن")
        buttons.addWidget(self.btn_apply_filter)
        buttons.addWidget(self.btn_clear_filter)
        buttons.addStretch()
        buttons.addWidget(self.btn_cancel)
        layout.addLayout(buttons)

        self.btn_cancel.clicked.connect(self.reject)


class LettersForm(QWidget):

    def __init__(self, parent=None, on_back=None, on_exit=None):
        super().__init__(parent)

        self.on_back = on_back
        self.on_exit = on_exit

        self.current_letter_id = None
        self.template_path = None
        self.template_is_personal = False
        self.selected_receiver_ids = []

        self.word_application = None
        self.word_document = None

        self.setWindowTitle("مدیریت نامه‌های اداری")
        self.setMinimumSize(1050, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        self.setStyleSheet("""
            QWidget {
                background-color:#F3F6F9;
                color:#183B56;
                font-family:Tahoma;
                font-size:9pt;
            }

            QLineEdit,QComboBox,QSpinBox,QFontComboBox {
                background:white;
                border:1px solid #CBD5DF;
                border-radius:6px;
                padding:5px 8px;
                min-height:25px;
            }

            QTextEdit {
                background:white;
                border:1px solid #B8C7D4;
                border-radius:7px;
                padding:10px;
                font-size:12pt;
                selection-background-color:#D4AF37;
                selection-color:#183B56;
            }

            QListWidget {
                background:white;
                border:1px solid #CBD5DF;
                border-radius:6px;
                padding:4px;
            }

            QListWidget::item {
                padding:5px;
                border-radius:4px;
            }

            QListWidget::item:selected {
                background:#DCE8F0;
                color:#183B56;
            }

            QPushButton {
                background-color:#183B56;
                color:white;
                border:none;
                border-radius:6px;
                padding:6px 12px;
                min-height:27px;
                font-weight:bold;
            }

            QPushButton:hover {
                background-color:#285577;
            }

            QTableWidget {
                background:white;
                alternate-background-color:#F2F6F9;
                gridline-color:#E1E7EC;
                border:1px solid #D5DDE5;
                border-radius:6px;
                selection-background-color:#D4AF37;
                selection-color:#183B56;
            }

            QHeaderView::section {
                background:#183B56;
                color:white;
                padding:7px;
                border:none;
                font-weight:bold;
            }

            QGroupBox {
                font-weight:bold;
                border:1px solid #CBD5DF;
                border-radius:7px;
                margin-top:8px;
                padding-top:8px;
            }

            QGroupBox::title {
                subcontrol-origin:margin;
                right:10px;
                padding:0 5px;
            }
        """)

        self.init_ui()
        self.load_combos()
        self.load_letters()
        self.clear_form()

    # -----------------------------------------------------
    # رابط کاربری
    # -----------------------------------------------------

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(7)

        # عنوان و دکمه‌های ناوبری

        top_layout = QHBoxLayout()

        self.btn_back = QPushButton("بازگشت به داشبورد")
        self.btn_exit = QPushButton("خروج از برنامه")

        title = QLabel("مدیریت نامه‌های اداری")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size:15pt;font-weight:bold;color:#183B56;padding:5px;"
        )

        top_layout.addWidget(self.btn_back)
        top_layout.addWidget(title, 1)
        top_layout.addWidget(self.btn_exit)

        main_layout.addLayout(top_layout)

        self.btn_back.clicked.connect(self.go_back)
        self.btn_exit.clicked.connect(self.exit_application)

        # جستجوی سریع و دکمه پنجره جستجوی پیشرفته

        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("جستجوی سریع:"))

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "شماره نامه، متن نامه یا نام گیرنده..."
        )

        self.btn_advanced_search = QPushButton("جستجوی پیشرفته")
        self.btn_advanced_search.setMinimumWidth(145)

        quick_layout.addWidget(self.txt_search, 1)
        quick_layout.addWidget(self.btn_advanced_search)
        main_layout.addLayout(quick_layout)

        self.txt_search.textChanged.connect(self.load_letters)

        # تمام فیلترهای پیشرفته فقط داخل پنجره جداگانه قرار دارند
        self.advanced_dialog = AdvancedSearchDialog(self)

        # نگه داشتن نام فیلدهای قبلی برای سازگاری با منطق جستجو
        self.txt_filter_number = self.advanced_dialog.txt_filter_number
        self.txt_filter_receiver = self.advanced_dialog.txt_filter_receiver
        self.txt_filter_body = self.advanced_dialog.txt_filter_body
        self.cbo_filter_subject = self.advanced_dialog.cbo_filter_subject
        self.txt_date_from = self.advanced_dialog.txt_date_from
        self.txt_date_to = self.advanced_dialog.txt_date_to
        self.btn_date_from = self.advanced_dialog.btn_date_from
        self.btn_date_to = self.advanced_dialog.btn_date_to
        self.btn_apply_filter = self.advanced_dialog.btn_apply_filter
        self.btn_clear_filter = self.advanced_dialog.btn_clear_filter

        self.btn_date_from.clicked.connect(
            lambda: self.open_filter_calendar(self.txt_date_from)
        )
        self.btn_date_to.clicked.connect(
            lambda: self.open_filter_calendar(self.txt_date_to)
        )
        self.btn_apply_filter.clicked.connect(self.advanced_dialog.accept)
        self.btn_clear_filter.clicked.connect(self.clear_filters)
        self.btn_advanced_search.clicked.connect(self.open_advanced_search)

        # اطلاعات نامه

        info_layout = QGridLayout()
        info_layout.setHorizontalSpacing(12)
        info_layout.setVerticalSpacing(7)

        self.txt_number = QLineEdit()
        self.txt_number.setReadOnly(True)
        self.chk_manual_number = QCheckBox("شماره‌گذاری دستی")
        self.chk_manual_number.toggled.connect(
            self.on_manual_number_toggled
        )
        number_layout = QHBoxLayout()
        number_layout.addWidget(self.txt_number, 1)
        number_layout.addWidget(self.chk_manual_number)
        number_widget = QWidget()
        number_widget.setLayout(number_layout)

        self.txt_date = QLineEdit()
        self.txt_date.setReadOnly(True)

        self.btn_calendar = QPushButton("تقویم")
        self.btn_calendar.setMaximumWidth(75)

        date_layout = QHBoxLayout()
        date_layout.addWidget(self.txt_date)
        date_layout.addWidget(self.btn_calendar)

        date_widget = QWidget()
        date_widget.setLayout(date_layout)

        self.cbo_subject = QComboBox()
        self.cbo_signator = QComboBox()

        info_layout.addWidget(QLabel("شماره نامه:"), 0, 0)
        info_layout.addWidget(number_widget, 0, 1)
        info_layout.addWidget(QLabel("تاریخ نامه:"), 0, 2)
        info_layout.addWidget(date_widget, 0, 3)
        info_layout.addWidget(QLabel("موضوع:"), 1, 0)
        info_layout.addWidget(self.cbo_subject, 1, 1)
        info_layout.addWidget(QLabel("امضاکننده:"), 1, 2)
        info_layout.addWidget(self.cbo_signator, 1, 3)

        info_layout.setColumnStretch(1, 2)
        info_layout.setColumnStretch(3, 2)

        main_layout.addLayout(info_layout)

        self.btn_calendar.clicked.connect(self.open_calendar)

        # گیرندگان

        receiver_layout = QHBoxLayout()
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

        # نوار ابزار متن

        toolbar_layout = QHBoxLayout()

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

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setMaximumWidth(38)

        self.btn_underline = QPushButton("U")
        self.btn_underline.setCheckable(True)
        self.btn_underline.setMaximumWidth(38)

        self.btn_color = QPushButton("رنگ")
        self.btn_color.setMaximumWidth(55)

        self.btn_right = QPushButton("راست‌چین")
        self.btn_center = QPushButton("وسط‌چین")
        self.btn_left = QPushButton("چپ‌چین")

        for widget in (
            self.font_combo, self.font_size,
            self.btn_bold, self.btn_italic,
            self.btn_underline, self.btn_color,
            self.btn_right, self.btn_center, self.btn_left
        ):
            toolbar_layout.addWidget(widget)

        toolbar_layout.addStretch()

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)

        self.txt_body = QTextEdit()
        self.txt_body.setAcceptRichText(True)
        self.txt_body.setLayoutDirection(Qt.RightToLeft)
        self.txt_body.setFont(QFont("Tahoma", 12))
        self.txt_body.setMinimumHeight(200)
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
        editor_layout.addWidget(QLabel("متن نامه"))
        editor_layout.addWidget(toolbar_widget)
        editor_layout.addWidget(self.txt_body)

        editor_widget = QWidget()
        editor_widget.setLayout(editor_layout)

        main_layout.addWidget(editor_widget, 4)

        # پیوست‌ها

        attachment_layout = QHBoxLayout()

        self.lst_attachments = QListWidget()
        self.lst_attachments.setMaximumHeight(55)

        self.btn_add_attachment = QPushButton("افزودن پیوست")
        self.btn_remove_attachment = QPushButton("حذف پیوست")

        attachment_layout.addWidget(QLabel("پیوست‌ها:"))
        attachment_layout.addWidget(self.lst_attachments, 1)
        attachment_layout.addWidget(self.btn_add_attachment)
        attachment_layout.addWidget(self.btn_remove_attachment)

        main_layout.addLayout(attachment_layout)

        self.lbl_attachment_status = QLabel("وضعیت پیوست: ندارد")
        main_layout.addWidget(self.lbl_attachment_status)

        self.btn_add_attachment.clicked.connect(self.add_attachments)
        self.btn_remove_attachment.clicked.connect(self.remove_attachment)
        self.lst_attachments.itemDoubleClicked.connect(
            self.open_attachment
        )

        # دکمه‌های ذخیره و مدیریت

        buttons_layout = QHBoxLayout()

        self.btn_new = QPushButton("نامه جدید")
        self.btn_save = QPushButton("ذخیره نامه")
        self.btn_delete = QPushButton("حذف نامه")
        self.btn_clear = QPushButton("پاک کردن فرم")

        self.btn_save.setStyleSheet(
            "background-color:#D4AF37;color:#183B56;"
        )

        for button in (
            self.btn_new, self.btn_save,
            self.btn_delete, self.btn_clear
        ):
            buttons_layout.addWidget(button)

        main_layout.addLayout(buttons_layout)

        self.btn_new.clicked.connect(self.clear_form)
        self.btn_save.clicked.connect(self.save_letter)
        self.btn_delete.clicked.connect(self.delete_letter)
        self.btn_clear.clicked.connect(self.clear_form)

        # خروجی Word و PDF و چاپ

        output_layout = QHBoxLayout()

        self.btn_select_template = QPushButton("انتخاب قالب Word")
        self.btn_create_word = QPushButton("ساخت Word و PDF")
        self.btn_print_word = QPushButton("چاپ مستقیم نامه")

        output_layout.addWidget(self.btn_select_template)
        output_layout.addWidget(self.btn_create_word)
        output_layout.addWidget(self.btn_print_word)

        self.lbl_template = QLabel("قالب Word انتخاب نشده است")
        output_layout.addWidget(self.lbl_template, 1)

        main_layout.addLayout(output_layout)

        self.btn_select_template.clicked.connect(
            self.select_word_template
        )
        self.btn_create_word.clicked.connect(
            self.create_word_file
        )
        self.btn_print_word.clicked.connect(
            self.print_word_file
        )

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
        self.table.setMaximumHeight(180)

        self.table.itemSelectionChanged.connect(self.select_letter)
        self.table.itemDoubleClicked.connect(self.open_selected_letter)

        main_layout.addWidget(self.table, 2)

    # -----------------------------------------------------
    # بازگشت و خروج
    # -----------------------------------------------------

    def go_back(self):
        if callable(self.on_back):
            self.on_back()
        else:
            self.hide()

    def exit_application(self):
        if callable(self.on_exit):
            self.on_exit()
        else:
            answer = QMessageBox.question(
                self,
                "خروج از برنامه",
                "آیا از خروج از برنامه مطمئن هستید؟",
                QMessageBox.Yes | QMessageBox.No
            )

            if answer == QMessageBox.Yes:
                self.window().close()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_receiver_display()
        self.load_letters()

    # -----------------------------------------------------
    # فیلترهای پیشرفته
    # -----------------------------------------------------

    def open_filter_calendar(self, target):
        dialog = JalaliCalendarDialog(self, target.text())

        if dialog.exec_() == QDialog.Accepted:
            if dialog.selected_date:
                target.setText(dialog.selected_date)
                self.load_letters()

    def open_advanced_search(self):
        self.advanced_dialog.exec_()
        self.load_letters()

    def clear_filters(self):
        # پاک‌کردن فیلترهای پیشرفته نباید جستجوی سریع را تغییر دهد.
        self.txt_filter_number.clear()
        self.txt_filter_receiver.clear()
        self.txt_filter_body.clear()
        self.txt_date_from.clear()
        self.txt_date_to.clear()
        self.cbo_filter_subject.setCurrentIndex(0)
        self.load_letters()

    def load_letters(self):
        if not hasattr(self, "table"):
            return

        quick_search = self.txt_search.text().strip()

        number = self.txt_filter_number.text().strip()
        receiver = self.txt_filter_receiver.text().strip()
        body = self.txt_filter_body.text().strip()

        date_from = self.txt_date_from.text().strip()
        date_to = self.txt_date_to.text().strip()

        subject_id = self.cbo_filter_subject.currentData()

        conditions = []
        params = []

        if quick_search:
            conditions.append("""
                (
                    L.LetterNumber LIKE ?
                    OR L.LetterBody LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM LetterPersons LP
                        JOIN Persons P ON P.PersonID = LP.PersonID
                        WHERE LP.LetterID = L.LetterID
                        AND P.PersonName LIKE ?
                    )
                )
            """)

            pattern = "%" + quick_search + "%"
            params.extend([pattern, pattern, pattern])

        if number:
            conditions.append("L.LetterNumber LIKE ?")
            params.append("%" + number + "%")

        if date_from:
            conditions.append("L.LetterDate >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("L.LetterDate <= ?")
            params.append(date_to)

        if receiver:
            conditions.append("""
                EXISTS (
                    SELECT 1
                    FROM LetterPersons LP
                    JOIN Persons P ON P.PersonID = LP.PersonID
                    WHERE LP.LetterID = L.LetterID
                    AND P.PersonName LIKE ?
                )
            """)
            params.append("%" + receiver + "%")

        if subject_id is not None:
            conditions.append("L.SubjectID = ?")
            params.append(subject_id)

        if body:
            conditions.append("L.LetterBody LIKE ?")
            params.append("%" + body + "%")

        where_sql = ""

        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        conn = get_connection()
        cursor = conn.cursor()

        try:
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
                            JOIN Persons P ON P.PersonID = LP.PersonID
                            WHERE LP.LetterID = L.LetterID
                        ),
                        ''
                    )
                FROM Letters L
                LEFT JOIN Subjects S
                    ON S.SubjectID = L.SubjectID
                LEFT JOIN Signators SG
                    ON SG.SignatorID = L.SignatorID
                {}
                ORDER BY L.LetterID DESC
            """.format(where_sql), params)

            records = cursor.fetchall()

        finally:
            conn.close()

        self.table.setRowCount(0)

        for row_number, record in enumerate(records):
            self.table.insertRow(row_number)

            for column, value in enumerate(record):
                item = QTableWidgetItem(
                    str(value) if value is not None else ""
                )
                self.table.setItem(row_number, column, item)

    # -----------------------------------------------------
    # تقویم اصلی
    # -----------------------------------------------------

    def open_calendar(self):
        dialog = JalaliCalendarDialog(self, self.txt_date.text())

        if dialog.exec_() == QDialog.Accepted:
            if dialog.selected_date:
                self.txt_date.setText(dialog.selected_date)

    # -----------------------------------------------------
    # گیرندگان
    # -----------------------------------------------------

    def refresh_receivers(self):
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT PersonID, PersonName
                FROM Persons
                ORDER BY PersonName
            """)
            records = cursor.fetchall()
        finally:
            conn.close()

        available_ids = [int(row[0]) for row in records]

        self.selected_receiver_ids = [
            pid for pid in self.selected_receiver_ids
            if pid in available_ids
        ]

        return records

    def update_receiver_display(self):
        records = self.refresh_receivers()

        name_map = {
            int(row[0]): row[1]
            for row in records
        }

        names = [
            name_map[pid]
            for pid in self.selected_receiver_ids
            if pid in name_map
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
            self.selected_receiver_ids = dialog.get_selected_ids()
            self.update_receiver_display()
            self.update_template_for_receivers()

    # -----------------------------------------------------
    # ویرایشگر متن
    # -----------------------------------------------------

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
        fmt.setFontWeight(
            QFont.Bold if self.btn_bold.isChecked()
            else QFont.Normal
        )
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
            QColor("#183B56"),
            self,
            "انتخاب رنگ متن"
        )

        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.txt_body.mergeCurrentCharFormat(fmt)
            self.txt_body.setFocus()

    # -----------------------------------------------------
    # قالب Word
    # -----------------------------------------------------

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
            self,
            "قالب Word",
            "قالب Word با موفقیت انتخاب شد."
        )

    def update_template_for_receivers(self):
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

        if self.template_is_personal:
            self.template_path = None
            self.template_is_personal = False

            self.lbl_template.setText(
                "قالب Word انتخاب نشده است"
            )

    # -----------------------------------------------------
    # توابع Bookmark ورد
    # -----------------------------------------------------

    def replace_word_bookmark(self, document, bookmark_name, value):
        if not document.Bookmarks.Exists(bookmark_name):
            raise Exception(
                "Bookmark زیر در قالب Word وجود ندارد: "
                + bookmark_name
            )

        bookmark_range = document.Bookmarks(bookmark_name).Range
        bookmark_range.Text = str(value)

        document.Bookmarks.Add(
            bookmark_name,
            bookmark_range
        )

    # -----------------------------------------------------
    # پیوست‌ها
    # -----------------------------------------------------

    def get_attachment_count(self):
        if self.current_letter_id is None:
            return 0

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM Attachments
                WHERE LetterID = ?
            """, (self.current_letter_id,))

            result = cursor.fetchone()
        finally:
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


    def get_default_letters_path(self):
        """Read the default output directory configured in application settings."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT SettingValue FROM AppSettings WHERE SettingKey = ?",
                ("letters_default_path",)
            ).fetchone()
        finally:
            conn.close()
        path = row[0].strip() if row and row[0] else ""
        if not path:
            path = os.path.join(
                os.path.expanduser("~"), "Documents", "Yasna", "Letters"
            )
        os.makedirs(path, exist_ok=True)
        return path

    def add_attachments(self):
        if self.current_letter_id is None:
            QMessageBox.warning(
                self,
                "توجه",
                "ابتدا نامه را ذخیره کنید."
            )
            return

        try:
            start_folder = self.get_default_letters_path()
        except Exception:
            start_folder = ""

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "انتخاب فایل‌های پیوست",
            start_folder,
            "All Files (*.*)"
        )

        if not files:
            return

        base_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        try:
            configured_path = self.get_default_letters_path()
        except Exception:
            configured_path = os.path.join(base_path, "attachments")

        letters_folder = os.path.join(
            configured_path,
            "Attachments",
            str(self.current_letter_id)
        )

        conn = None

        try:
            os.makedirs(letters_folder, exist_ok=True)

            conn = get_connection()
            cursor = conn.cursor()

            for source_path in files:
                file_name = os.path.basename(source_path)

                destination = os.path.join(
                    letters_folder,
                    file_name
                )

                name, ext = os.path.splitext(file_name)
                counter = 1

                while os.path.exists(destination):
                    file_name = "{}_{}{}".format(
                        name, counter, ext
                    )

                    destination = os.path.join(
                        letters_folder,
                        file_name
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
                self,
                "موفق",
                "پیوست‌ها با موفقیت اضافه شدند."
            )

        except Exception as e:
            if conn is not None:
                conn.rollback()
                conn.close()

            QMessageBox.critical(
                self,
                "خطا در افزودن پیوست",
                str(e)
            )

    def load_attachments(self):
        self.lst_attachments.clear()

        if self.current_letter_id is None:
            self.update_attachment_status()
            return

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT AttachmentID, FileName, FilePath
                FROM Attachments
                WHERE LetterID = ?
                ORDER BY AttachmentID DESC
            """, (self.current_letter_id,))

            records = cursor.fetchall()
        finally:
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

    def open_attachment(self, item):
        file_path = item.data(Qt.UserRole + 1)

        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                "خطا",
                "فایل پیوست پیدا نشد."
            )
            return

        try:
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "خطا در باز کردن فایل",
                str(e)
            )

    def remove_attachment(self):
        item = self.lst_attachments.currentItem()

        if item is None:
            QMessageBox.warning(
                self,
                "توجه",
                "ابتدا یک پیوست انتخاب کنید."
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
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(
                self,
                "خطا در حذف پیوست",
                str(e)
            )
            return
        finally:
            conn.close()

        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        self.load_attachments()

    # -----------------------------------------------------
    # ساخت Word و PDF
    # -----------------------------------------------------

    def create_word_file(self):
        if not self.template_path:
            QMessageBox.warning(
                self,
                "قالب Word",
                "ابتدا قالب Word را انتخاب کنید."
            )
            return

        if not os.path.isfile(self.template_path):
            QMessageBox.warning(
                self,
                "قالب Word",
                "فایل قالب پیدا نشد."
            )
            return

        letter_number = self.txt_number.text().strip()
        letter_date = self.txt_date.text().strip()

        if not letter_number:
            QMessageBox.warning(
                self, "توجه", "شماره نامه را وارد کنید."
            )
            return

        if not letter_date:
            QMessageBox.warning(
                self, "توجه", "تاریخ نامه را انتخاب کنید."
            )
            return

        if self.current_letter_id is None:
            QMessageBox.warning(
                self,
                "توجه",
                "قبل از ساخت فایل Word، نامه را ذخیره کنید."
            )
            return

        self.update_receiver_display()

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

        default_name = os.path.join(
            self.get_default_letters_path(),
            "Letter_{}.docx".format(letter_number)
        )

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

        pdf_path = os.path.splitext(output_path)[0] + ".pdf"

        word = None
        document = None
        temp_html_path = None

        try:
            import win32com.client

            word = win32com.client.DispatchEx(
                "Word.Application"
            )

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

            missing_bookmarks = [
                name for name in required_bookmarks
                if not document.Bookmarks.Exists(name)
            ]

            if missing_bookmarks:
                raise Exception(
                    "این Bookmarkها در قالب Word وجود ندارند:\n"
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
                    delete=False,
                    suffix=".html"
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

                insert_range = document.Range(
                    body_start,
                    body_start
                )

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

            # ساخت PDF با همان سند نهایی Word
            document.ExportAsFixedFormat(
                os.path.abspath(pdf_path),
                17
            )

            if temp_html_path and os.path.isfile(temp_html_path):
                try:
                    os.remove(temp_html_path)
                except Exception:
                    pass

                temp_html_path = None

            # نگهداری سند Word برای چاپ مستقیم
            self.word_application = word
            self.word_document = document

            message = (
                "فایل Word و PDF با موفقیت ساخته شدند.\n\n"
                "Word:\n" + output_path
                + "\n\nPDF:\n" + pdf_path
                + "\n\nوضعیت پیوست: " + attachment_text
            )

            QMessageBox.information(
                self,
                "ساخت موفق فایل‌ها",
                message
            )

            # بازکردن PDF
            try:
                os.startfile(pdf_path)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "باز کردن PDF",
                    "فایل PDF ساخته شد، اما بازکردن آن ناموفق بود:\n"
                    + str(e)
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

            self.word_application = None
            self.word_document = None

            QMessageBox.critical(
                self,
                "خطا در ساخت Word و PDF",
                str(e)
            )

        finally:
            if temp_html_path and os.path.isfile(temp_html_path):
                try:
                    os.remove(temp_html_path)
                except Exception:
                    pass

    # -----------------------------------------------------
    # چاپ مستقیم
    # -----------------------------------------------------

    def print_word_file(self):
        if self.word_document is not None:
            try:
                self.word_document.PrintOut()
                QMessageBox.information(
                    self,
                    "چاپ",
                    "فرمان چاپ به چاپگر پیش‌فرض ارسال شد."
                )
                return
            except Exception:
                self.word_document = None
                self.word_application = None

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "انتخاب فایل Word برای چاپ",
            "",
            "Word Files (*.docx *.doc)"
        )

        if not file_path:
            return

        word = None
        document = None

        try:
            import win32com.client

            word = win32com.client.DispatchEx(
                "Word.Application"
            )

            word.Visible = False
            word.DisplayAlerts = 0

            document = word.Documents.Open(
                os.path.abspath(file_path)
            )

            document.PrintOut()
            document.Close(SaveChanges=False)
            document = None

            word.Quit()
            word = None

            QMessageBox.information(
                self,
                "چاپ",
                "فرمان چاپ به چاپگر پیش‌فرض ارسال شد."
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
                self,
                "خطا در چاپ",
                str(e)
            )

    # -----------------------------------------------------
    # کمبوباکس‌ها
    # -----------------------------------------------------

    def load_combos(self):
        conn = get_connection()
        cursor = conn.cursor()

        try:
            self.cbo_subject.clear()
            self.cbo_signator.clear()
            self.cbo_filter_subject.clear()

            self.cbo_filter_subject.addItem(
                "همه موضوع‌ها",
                None
            )

            cursor.execute("""
                SELECT SubjectID, SubjectName
                FROM Subjects
                ORDER BY SubjectName
            """)

            subjects = cursor.fetchall()

            for record in subjects:
                self.cbo_subject.addItem(
                    record[1], record[0]
                )

                self.cbo_filter_subject.addItem(
                    record[1], record[0]
                )

            cursor.execute("""
                SELECT SignatorID, SignatorName
                FROM Signators
                ORDER BY SignatorName
            """)

            for record in cursor.fetchall():
                self.cbo_signator.addItem(
                    record[1], record[0]
                )

        finally:
            conn.close()

    # -----------------------------------------------------
    # انتخاب نامه
    # -----------------------------------------------------

    def select_letter(self):
        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows:
            return

        self.load_letter_by_row(selected_rows[0].row())

    def open_selected_letter(self, item):
        self.load_letter_by_row(item.row())

    def load_letter_by_row(self, row):
        if row < 0 or self.table.item(row, 0) is None:
            return

        self.current_letter_id = int(
            self.table.item(row, 0).text()
        )

        conn = get_connection()
        cursor = conn.cursor()

        try:
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
                return

            self.txt_number.setText(record[0] or "")
            self.txt_number.setReadOnly(True)
            self.chk_manual_number.blockSignals(True)
            self.chk_manual_number.setChecked(False)
            self.chk_manual_number.setEnabled(False)
            self.chk_manual_number.blockSignals(False)
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
                int(item[0])
                for item in cursor.fetchall()
            ]

        finally:
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

    # -----------------------------------------------------
    # شماره‌گذاری دستی و خودکار
    # -----------------------------------------------------

    def on_manual_number_toggled(self, checked):
        if self.current_letter_id is not None:
            self.chk_manual_number.setChecked(False)
            self.chk_manual_number.setEnabled(False)
            self.txt_number.setReadOnly(True)
            return

        self.txt_number.setReadOnly(not checked)
        if checked:
            self.txt_number.setFocus()
            self.txt_number.selectAll()
        else:
            self.txt_number.setText(get_next_letter_number())

    # -----------------------------------------------------
    # ذخیره نامه
    # -----------------------------------------------------

    def save_letter(self):
        letter_number = self.txt_number.text().strip()
        letter_date = self.txt_date.text().strip()
        letter_body = self.txt_body.toHtml()

        if not letter_date:
            QMessageBox.warning(
                self, "توجه", "تاریخ نامه را انتخاب کنید."
            )
            return

        subject_id = self.cbo_subject.currentData()
        signator_id = self.cbo_signator.currentData()

        available_records = self.refresh_receivers()

        available_ids = set(
            int(row[0]) for row in available_records
        )

        receiver_ids = [
            pid for pid in self.selected_receiver_ids
            if pid in available_ids
        ]

        conn = get_connection()
        cursor = conn.cursor()

        try:
            if self.current_letter_id is None:
                # شماره‌گذاری و درج در یک تراکنش برای جلوگیری از تکرار.
                cursor.execute("BEGIN IMMEDIATE")

                if self.chk_manual_number.isChecked():
                    letter_number = self.txt_number.text().strip()
                    if not letter_number:
                        raise ValueError(
                            "حالت شماره‌گذاری دستی فعال است؛ شماره نامه را وارد کنید."
                        )
                else:
                    current_year = int(today_jalali().split("/")[0])
                    letter_number = get_next_letter_number(
                        current_year, cursor=cursor, reserve=True
                    )

                duplicate = cursor.execute(
                    "SELECT LetterID FROM Letters WHERE LetterNumber=? LIMIT 1",
                    (letter_number,)
                ).fetchone()
                if duplicate:
                    raise ValueError(
                        "این شماره نامه قبلاً ثبت شده است. شماره دیگری وارد کنید."
                    )

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
                        LetterDate = ?,
                        SubjectID = ?,
                        SignatorID = ?,
                        LetterBody = ?
                    WHERE LetterID = ?
                """, (
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

            self.txt_number.setText(letter_number)
            self.txt_number.setReadOnly(True)
            self.chk_manual_number.blockSignals(True)
            self.chk_manual_number.setChecked(False)
            self.chk_manual_number.setEnabled(False)
            self.chk_manual_number.blockSignals(False)
            self.selected_receiver_ids = receiver_ids
            self.update_receiver_display()

            self.load_letters()
            self.load_attachments()

            QMessageBox.information(
                self,
                "موفق",
                "نامه با موفقیت ذخیره شد."
            )

        except Exception as e:
            conn.rollback()

            QMessageBox.critical(
                self,
                "خطا در ذخیره نامه",
                str(e)
            )

        finally:
            conn.close()

    # -----------------------------------------------------
    # حذف نامه
    # -----------------------------------------------------

    def delete_letter(self):
        if self.current_letter_id is None:
            QMessageBox.warning(
                self,
                "توجه",
                "ابتدا یک نامه انتخاب کنید."
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

        attachment_paths = []

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

        except Exception as e:
            conn.rollback()

            QMessageBox.critical(
                self,
                "خطا در حذف نامه",
                str(e)
            )
            return

        finally:
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
            self,
            "موفق",
            "نامه با موفقیت حذف شد."
        )

    # -----------------------------------------------------
    # پاک کردن فرم
    # -----------------------------------------------------

    def clear_form(self):
        self.current_letter_id = None
        self.selected_receiver_ids = []

        self.chk_manual_number.setEnabled(True)
        self.chk_manual_number.blockSignals(True)
        self.chk_manual_number.setChecked(False)
        self.chk_manual_number.blockSignals(False)
        self.txt_number.setReadOnly(True)
        self.txt_number.setText(get_next_letter_number())
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

    # -----------------------------------------------------
    # پایان فرم
    # -----------------------------------------------------
