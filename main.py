
# -*- coding: utf-8 -*-
import sys
import os
import math
import sqlite3

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QStackedWidget, QMessageBox, QGraphicsDropShadowEffect,
    QScrollArea, QFileDialog, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer, QTime, QPointF, QUrl
from PyQt5.QtGui import (
    QFont, QPainter, QPen, QBrush, QColor, QPolygonF, QPixmap
)

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    MEDIA_AVAILABLE = True
except Exception:
    QMediaPlayer = None
    QMediaContent = None
    MEDIA_AVAILABLE = False

try:
    from PyQt5.QtSvg import QSvgWidget
    SVG_AVAILABLE = True
except Exception:
    QSvgWidget = None
    SVG_AVAILABLE = False

from database.database import initialize_database, get_connection
from forms.persons import PersonsForm
from forms.letters import LettersForm, today_jalali
from forms.postal import PostalForm, DirectoryTab
from forms.reminders import RemindersForm
from forms.reports import ReportsForm
from forms.settings import SettingsUsersForm

from forms.login import LoginDialog
from security import (
    has_permission, can_edit, apply_read_only,
    protect_form_methods, show_denied, guard_class_methods
)

# Protect Qt-connected write actions at the class level.
guard_class_methods(
    PersonsForm, "persons", ["save_person", "delete_person", "remove_template"]
)
guard_class_methods(
    LettersForm, "letters",
    ["save_letter", "delete_letter", "add_attachments", "remove_attachment"]
)
guard_class_methods(
    DirectoryTab, "postal", ["save_row", "delete_row"]
)
guard_class_methods(
    PostalForm, "postal",
    ["save_record", "mark_sent", "mark_delivered", "delete_record",
     "capture_mouse_signature", "upload_signature", "clear_signature"]
)
guard_class_methods(
    RemindersForm, "reminders",
    ["save_reminder", "mark_done", "delete_reminder"]
)

# بانک ۳۶۵ سخن روز، حدیث و شعر فارسی
try:
    from data.daily_quotes import get_daily_quote, QUOTES
except ImportError:
    def get_daily_quote():
        return (
            "هر روز فرصتی تازه برای بهتر ساختن زندگی است.",
            "حکمت"
        )


NAVY = "#142D4E"
NAVY_LIGHT = "#1D4165"
GOLD = "#D8B66A"
CREAM = "#F7F4EC"
WHITE = "#FFFFFF"
TEXT = "#24364B"
MUTED = "#788596"


class AnalogClock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self.setMaximumSize(230, 230)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

    def paintEvent(self, event):
        side = min(self.width(), self.height())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(side / 220.0, side / 220.0)

        # صفحه ساعت
        painter.setPen(QPen(QColor(GOLD), 5))
        painter.setBrush(QBrush(QColor(WHITE)))
        painter.drawEllipse(QPointF(0, 0), 100, 100)

        # درجه‌ها و اعداد
        for i in range(60):
            painter.save()
            painter.rotate(i * 6)

            if i % 5 == 0:
                painter.setPen(QPen(QColor(NAVY), 3))
                painter.drawLine(0, -88, 0, -76)
            else:
                painter.setPen(QPen(QColor("#B9C2CC"), 1))
                painter.drawLine(0, -88, 0, -83)

            painter.restore()

        # عقربه‌ها
        now = QTime.currentTime()
        hour = now.hour() % 12
        minute = now.minute()
        second = now.second()

        painter.save()
        painter.rotate((hour + minute / 60.0) * 30)
        painter.setPen(QPen(QColor(NAVY), 7, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(0, 8, 0, -48)
        painter.restore()

        painter.save()
        painter.rotate(minute * 6 + second * 0.1)
        painter.setPen(QPen(QColor(GOLD), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(0, 10, 0, -70)
        painter.restore()

        painter.save()
        painter.rotate(second * 6)
        painter.setPen(QPen(QColor("#C94C4C"), 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(0, 15, 0, -78)
        painter.restore()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(NAVY))
        painter.drawEllipse(QPointF(0, 0), 6, 6)

        painter.end()



class DashboardCanvas(QWidget):
    """تصویر مرجع داشبورد با لایه‌های زنده و قابل تغییر."""
    BASE_WIDTH = 1648
    BASE_HEIGHT = 893

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap(image_path)
        if not self._pixmap.isNull():
            # نوار عنوان پنجره از تصویر مرجع جدا می‌شود.
            self._pixmap = self._pixmap.copy(
                0, 34, self._pixmap.width(), self._pixmap.height() - 34
            )
        self._placements = []
        self.setMinimumSize(1100, 700)

    def place(self, widget, x, y, width, height):
        widget.setParent(self)
        self._placements.append((widget, x, y, width, height))
        self._set_widget_geometry(widget, x, y, width, height)
        widget.show()
        return widget

    def _set_widget_geometry(self, widget, x, y, width, height):
        sx = float(self.width()) / self.BASE_WIDTH
        sy = float(self.height()) / self.BASE_HEIGHT
        widget.setGeometry(
            int(x * sx), int(y * sy),
            max(1, int(width * sx)), max(1, int(height * sy))
        )

    def resizeEvent(self, event):
        QWidget.resizeEvent(self, event)
        for widget, x, y, width, height in self._placements:
            self._set_widget_geometry(widget, x, y, width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._pixmap.isNull():
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#E9DDC5"))
        painter.end()


class YasnaWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.current_user = user or {}
        self.menu_buttons = {}
        self._allow_close = False
        self.replacement_window = None
        self.music_player = None
        self.music_path = ""
        self.music_available = MEDIA_AVAILABLE

        self.setWindowTitle("Yasna | سیستم مدیریت مکاتبات اداری")
        self.setMinimumSize(1100, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        self.persons_window = None
        self.letters_window = None
        self.postal_window = None
        self.reminders_window = None
        self.reports_window = None
        self.settings_window = None

        self.create_ui()
        self.setup_music()
        self.apply_menu_permissions()
        self.refresh_dashboard()

        # ساعت دیجیتال هر ثانیه به‌روز می‌شود.
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        # بررسی یادآوری‌های سررسیدشده به‌صورت دوره‌ای.
        self.reminder_alarm_timer = QTimer(self)
        self.reminder_alarm_timer.timeout.connect(
            self.check_reminder_alarms
        )
        self.reminder_alarm_timer.start(15000)
        self.check_reminder_alarms()

        self.dashboard_timer = QTimer(self)
        self.dashboard_timer.timeout.connect(self.refresh_dashboard)
        self.dashboard_timer.start(60000)

        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.verify_active_session)
        self.session_timer.start(60000)

    def create_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.create_dashboard()
        self.stack.addWidget(self.dashboard)

    def create_dashboard(self):
        # داشبورد مستقل از تصویر؛ تمام اجزا با Layout ساخته می‌شوند.
        self.dashboard = QWidget()
        self.dashboard.setObjectName("dashboardRoot")
        self.dashboard.setStyleSheet("""
            QWidget#dashboardRoot { background:#F3F5F8; color:#24364B; }
            QLabel { color:#24364B; }
            QFrame#sidebar { background:#142D4E; border-radius:14px; }
            QLabel#brand { color:#F2D99F; font-size:25px; font-weight: bold; }
            QLabel#brandSub { color:#D5DFE9; font-size:10px; }
            QPushButton#navButton {
                background:transparent; color:#EAF0F6; border:0;
                border-radius:9px; padding:12px 14px; text-align:right;
                font-size:13px; font-weight:600;
            }
            QPushButton#navButton:hover { background:#24496D; color:#F2D99F; }
            QPushButton#navButton:pressed { background:#315A7E; }
            QPushButton#logoutButton {
                background:#7B3540; color:white; border:1px solid #A65A61;
                border-radius:9px; padding:11px; font-weight:bold;
            }
            QPushButton#logoutButton:hover { background:#98434D; }
            QFrame#panel {
                background:white; border:1px solid #E2E7ED; border-radius:13px;
            }
            QLabel#sectionTitle { color:#142D4E; font-size:15px; font-weight:bold; }
            QLabel#muted { color:#788596; font-size:10px; }
            QLabel#statValue { color:#142D4E; font-size:25px; font-weight:bold; }
            QLabel#statTitle { color:#788596; font-size:11px; font-weight:bold; }
            QLabel#quoteText { color:#24364B; font-size:15px; font-weight:bold; }
            QPushButton#musicButton {
                background:#1D4165; color:#F2D99F; border:1px solid #D8B66A;
                border-radius:7px; padding:7px 12px;
            }
            QPushButton#musicButton:hover { background:#315A7E; }
            QTableWidget {
                background:white; alternate-background-color:#F5F7FA;
                color:#24364B; border:0; gridline-color:#E8EDF2;
                font-size:11px; selection-background-color:#E7EEF5;
            }
            QHeaderView::section {
                background:#1D4165; color:#F7E7BE; border:0;
                padding:8px; font-weight:bold;
            }
        """)

        root = QHBoxLayout(self.dashboard)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # نوار کناری و منوهای واقعی برنامه
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(13, 20, 13, 16)
        side.setSpacing(8)

        brand = QLabel("YASNA")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        side.addWidget(brand)
        brand_sub = QLabel("سیستم مدیریت مکاتبات اداری")
        brand_sub.setObjectName("brandSub")
        brand_sub.setAlignment(Qt.AlignCenter)
        side.addWidget(brand_sub)
        side.addSpacing(22)

        self.menu_buttons = {}
        menu_items = [
            ("dashboard", "⌂   داشبورد"),
            ("letters", "✉   نامه‌های اداری"),
            ("postal", "▣   مرسوله‌های پستی"),
            ("persons", "♙   اشخاص و مخاطبان"),
            ("reminders", "◷   یادآوری‌ها"),
            ("reports", "▤   گزارش‌گیری"),
            ("settings", "⚙   تنظیمات و کاربران"),
        ]
        for key, caption in menu_items:
            button = QPushButton(caption)
            button.setObjectName("navButton")
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(43)
            button.clicked.connect(
                lambda checked=False, k=key: self.menu_clicked(k)
            )
            side.addWidget(button)
            self.menu_buttons[key] = button

        side.addStretch(1)
        self.btn_choose_music = QPushButton("♫   انتخاب موسیقی")
        self.btn_choose_music.setObjectName("musicButton")
        self.btn_choose_music.clicked.connect(self.choose_music)
        side.addWidget(self.btn_choose_music)

        self.btn_music_toggle = QPushButton("▶   پخش موسیقی")
        self.btn_music_toggle.setObjectName("musicButton")
        self.btn_music_toggle.clicked.connect(self.toggle_music)
        side.addWidget(self.btn_music_toggle)

        self.music_auto_checkbox = QCheckBox("پخش خودکار هنگام ورود")
        self.music_auto_checkbox.setStyleSheet("color:#EAF0F6; padding:5px;")
        self.music_auto_checkbox.setChecked(True)
        self.music_auto_checkbox.toggled.connect(self.save_music_autoplay)
        side.addWidget(self.music_auto_checkbox)

        logout_button = QPushButton("خروج از حساب")
        logout_button.setObjectName("logoutButton")
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.clicked.connect(self.logout)
        side.addWidget(logout_button)
        root.addWidget(sidebar)

        # محتوای اصلی
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(13)
        root.addWidget(content, 1)

        header = QHBoxLayout()
        heading_box = QVBoxLayout()
        title = QLabel("داشبورد مدیریتی")
        title.setStyleSheet("font-size:23px; font-weight:bold; color:#142D4E;")
        subtitle = QLabel("نمای کلی فعالیت‌ها و دسترسی سریع به بخش‌های یسنا")
        subtitle.setObjectName("muted")
        heading_box.addWidget(title)
        heading_box.addWidget(subtitle)
        header.addLayout(heading_box)
        header.addStretch(1)
        self.date_label = QLabel("")
        self.date_label.setStyleSheet(
            "background:#FFFFFF; color:#1D4165; border:1px solid #E2E7ED;"
            "border-radius:9px; padding:10px 14px; font-weight:bold;"
        )
        header.addWidget(self.date_label)
        content_layout.addLayout(header)

        # سخن روز
        quote_panel = QFrame()
        quote_panel.setObjectName("panel")
        quote_layout = QVBoxLayout(quote_panel)
        quote_layout.setContentsMargins(18, 12, 18, 12)
        self.quote_top_source = QLabel("")
        self.quote_top_source.setStyleSheet("color:#A17B38; font-weight:bold;")
        self.quote_top_text = QLabel("")
        self.quote_top_text.setObjectName("quoteText")
        self.quote_top_text.setWordWrap(True)
        quote_layout.addWidget(self.quote_top_source)
        quote_layout.addWidget(self.quote_top_text)
        content_layout.addWidget(quote_panel)

        # کارت‌های آماری
        stats_grid = QGridLayout()
        stats_grid.setSpacing(10)
        self.stat_labels = {}
        stat_info = [
            ("letters", "نامه‌های ثبت‌شده", "✉"),
            ("postal", "مرسوله‌های پستی", "▣"),
            ("persons", "اشخاص", "♙"),
            ("contacts", "فرستنده و گیرنده", "↔"),
            ("reminders", "یادآوری‌های باز", "◷"),
        ]
        for index, (key, caption, symbol) in enumerate(stat_info):
            card = QFrame()
            card.setObjectName("panel")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            top_line = QHBoxLayout()
            icon_label = QLabel(symbol)
            icon_label.setStyleSheet("color:#B28B45; font-size:20px;")
            name_label = QLabel(caption)
            name_label.setObjectName("statTitle")
            top_line.addWidget(icon_label)
            top_line.addWidget(name_label)
            top_line.addStretch(1)
            card_layout.addLayout(top_line)
            number = QLabel("۰")
            number.setObjectName("statValue")
            card_layout.addWidget(number)
            self.stat_labels[key] = number
            stats_grid.addWidget(card, 0, index)
        content_layout.addLayout(stats_grid)

        # ساعت و جدول یادآوری‌ها
        middle = QHBoxLayout()
        middle.setSpacing(12)

        clock_panel = QFrame()
        clock_panel.setObjectName("panel")
        clock_panel.setMinimumWidth(225)
        clock_layout = QVBoxLayout(clock_panel)
        clock_layout.setContentsMargins(12, 14, 12, 14)
        clock_title = QLabel("ساعت و زمان")
        clock_title.setObjectName("sectionTitle")
        clock_title.setAlignment(Qt.AlignCenter)
        clock_layout.addWidget(clock_title)
        self.analog_clock = AnalogClock()
        clock_layout.addWidget(self.analog_clock, 0, Qt.AlignCenter)
        self.digital_clock = QLabel("")
        self.digital_clock.setAlignment(Qt.AlignCenter)
        self.digital_clock.setStyleSheet(
            "font-size:22px; font-weight:bold; color:#A17B38;"
        )
        clock_layout.addWidget(self.digital_clock)
        clock_layout.addStretch(1)
        middle.addWidget(clock_panel)

        reminders_panel = QFrame()
        reminders_panel.setObjectName("panel")
        reminders_layout = QVBoxLayout(reminders_panel)
        reminders_layout.setContentsMargins(12, 12, 12, 12)
        reminders_header = QHBoxLayout()
        self.today_reminders_title = QLabel("یادآوری‌های امروز")
        self.today_reminders_title.setObjectName("sectionTitle")
        reminders_header.addWidget(self.today_reminders_title)
        reminders_header.addStretch(1)
        reminders_layout.addLayout(reminders_header)

        self.today_reminders = QTableWidget(0, 3)
        self.today_reminders.setHorizontalHeaderLabels(["ساعت", "عنوان یادآوری", "وضعیت"])
        self.today_reminders.setLayoutDirection(Qt.RightToLeft)
        self.today_reminders.verticalHeader().setVisible(False)
        self.today_reminders.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.today_reminders.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.today_reminders.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.today_reminders.setEditTriggers(QTableWidget.NoEditTriggers)
        self.today_reminders.setSelectionBehavior(QTableWidget.SelectRows)
        self.today_reminders.setSelectionMode(QTableWidget.NoSelection)
        self.today_reminders.setAlternatingRowColors(True)
        self.today_reminders.setShowGrid(False)
        self.today_reminders.setMinimumHeight(245)
        reminders_layout.addWidget(self.today_reminders)
        middle.addWidget(reminders_panel, 1)
        content_layout.addLayout(middle, 1)

        # سخن بزرگان
        wisdom_panel = QFrame()
        wisdom_panel.setObjectName("panel")
        wisdom_layout = QVBoxLayout(wisdom_panel)
        wisdom_layout.setContentsMargins(18, 11, 18, 11)
        wisdom_heading = QLabel("سخن بزرگان")
        wisdom_heading.setObjectName("sectionTitle")
        self.quote_text = QLabel("")
        self.quote_text.setObjectName("quoteText")
        self.quote_text.setWordWrap(True)
        self.quote_text.setAlignment(Qt.AlignCenter)
        self.quote_meaning = QLabel("")
        self.quote_meaning.setObjectName("muted")
        self.quote_meaning.setWordWrap(True)
        self.quote_meaning.setAlignment(Qt.AlignCenter)
        self.quote_source = QLabel("")
        self.quote_source.setStyleSheet("color:#A17B38; font-weight:bold;")
        self.quote_source.setAlignment(Qt.AlignLeft)
        wisdom_layout.addWidget(wisdom_heading)
        wisdom_layout.addWidget(self.quote_text)
        wisdom_layout.addWidget(self.quote_meaning)
        wisdom_layout.addWidget(self.quote_source)
        content_layout.addWidget(wisdom_panel)

        self.show_daily_quote()
        self.update_clock()

    def update_clock(self):
        now = QTime.currentTime()
        self.digital_clock.setText(now.toString("HH:mm:ss"))

    def show_daily_quote(self):
        item = get_daily_quote()
        if len(item) >= 3:
            quote, source, meaning = item[0], item[1], item[2]
        else:
            quote, source = item
            meaning = ""

        # قاب بالایی و پایینی دو متن متفاوت از بانک روزانه نشان می‌دهند.
        top_quote, top_source = quote, source
        try:
            from datetime import date
            index = date.today().timetuple().tm_yday % len(QUOTES)
            next_item = QUOTES[index]
            top_quote, top_source = next_item[0], next_item[1]
        except Exception:
            pass

        self.quote_text.setText("«%s»" % quote)
        self.quote_meaning.setText(meaning)
        self.quote_source.setText(source)
        self.quote_top_text.setText("«%s»" % top_quote)
        self.quote_top_source.setText(top_source)

    def read_app_setting(self, key, default=""):
        connection = None
        try:
            connection = get_connection()
            row = connection.execute(
                "SELECT SettingValue FROM AppSettings WHERE SettingKey=?",
                (key,)
            ).fetchone()
            return row[0] if row else default
        except Exception:
            return default
        finally:
            if connection:
                connection.close()

    def write_app_setting(self, key, value):
        connection = None
        try:
            connection = get_connection()
            connection.execute(
                "INSERT OR REPLACE INTO AppSettings (SettingKey, SettingValue) "
                "VALUES (?, ?)",
                (key, str(value))
            )
            connection.commit()
        except Exception as error:
            print("Music setting error:", error)
        finally:
            if connection:
                connection.close()

    def setup_music(self):
        if not self.music_available:
            self.btn_music_toggle.setEnabled(False)
            self.btn_choose_music.setEnabled(False)
            self.music_auto_checkbox.setEnabled(False)
            self.btn_music_toggle.setToolTip(
                "ماژول چندرسانه‌ای PyQt5 در این نصب در دسترس نیست."
            )
            return

        self.music_path = self.read_app_setting("music_path", "")
        autoplay = self.read_app_setting("music_autoplay", "1") == "1"
        self.music_auto_checkbox.blockSignals(True)
        self.music_auto_checkbox.setChecked(autoplay)
        self.music_auto_checkbox.blockSignals(False)

        self.music_player = QMediaPlayer(self)
        self.music_player.setVolume(35)
        self.music_player.mediaStatusChanged.connect(
            self.handle_music_status
        )
        if self.music_path and os.path.isfile(self.music_path):
            self.music_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(self.music_path))
            )
            if autoplay:
                self.music_player.play()

    def handle_music_status(self, status):
        if not self.music_player:
            return

        if status == QMediaPlayer.EndOfMedia:
            self.music_player.setPosition(0)
            self.music_player.play()

    def choose_music(self):
        path, selected_filter = QFileDialog.getOpenFileName(
            self,
            "انتخاب موسیقی آغاز یسنا",
            os.path.expanduser("~"),
            "Audio Files (*.mp3 *.wav *.wma *.ogg);;All Files (*.*)"
        )
        if not path:
            return

        self.music_path = os.path.abspath(path)
        self.write_app_setting("music_path", self.music_path)

        if self.music_player is not None:
            self.music_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(self.music_path))
            )
            self.music_player.play()
            self.btn_music_toggle.setText("توقف موسیقی")

    def toggle_music(self):
        if not self.music_available:
            QMessageBox.warning(
                self, "پخش موسیقی",
                "قابلیت چندرسانه‌ای PyQt5 در این نصب فعال نیست."
            )
            return

        if not self.music_path or not os.path.isfile(self.music_path):
            self.choose_music()
            return

        if self.music_player is None:
            self.setup_music()

        if self.music_player.state() == QMediaPlayer.PlayingState:
            self.music_player.pause()
            self.btn_music_toggle.setText("ادامه موسیقی")
        else:
            self.music_player.play()
            self.btn_music_toggle.setText("توقف موسیقی")

    def save_music_autoplay(self, checked):
        self.write_app_setting("music_autoplay", "1" if checked else "0")

    def refresh_dashboard(self):
        self.update_clock()

        try:
            weekday_names = {
                "Saturday": "شنبه", "Sunday": "یکشنبه",
                "Monday": "دوشنبه", "Tuesday": "سه‌شنبه",
                "Wednesday": "چهارشنبه", "Thursday": "پنجشنبه",
                "Friday": "جمعه"
            }
            weekday = __import__("datetime").datetime.now().strftime("%A")
            self.date_label.setText(
                weekday_names.get(weekday, "") + "  |  " + today_jalali()
            )
        except Exception:
            self.date_label.setText("تاریخ شمسی")

        self.load_statistics()
        self.load_today_reminders()

    def check_reminder_alarms(self):
        """نمایش هشدار برای یادآوری‌های سررسیدشده که هنوز اعلام نشده‌اند."""
        connection = None

        try:
            current_date = today_jalali()
            current_time = QTime.currentTime().toString("HH:mm")

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT ReminderID, ReminderTitle, ReminderDate,
                       COALESCE(ReminderTime, ''), COALESCE(Description, '')
                FROM Reminders
                WHERE COALESCE(IsDone, 0) = 0
                  AND COALESCE(NotifiedAt, '') = ''
                  AND (
                        ReminderDate < ?
                        OR (
                            ReminderDate = ?
                            AND COALESCE(NULLIF(ReminderTime, ''), '23:59') <= ?
                        )
                  )
                ORDER BY ReminderDate, ReminderTime, ReminderID
            """, (current_date, current_date, current_time))

            due_rows = cursor.fetchall()

            if not due_rows:
                return

            notified_at = __import__("datetime").datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            cursor.executemany(
                "UPDATE Reminders SET NotifiedAt = ? WHERE ReminderID = ?",
                [(notified_at, row[0]) for row in due_rows]
            )
            connection.commit()

            messages = []
            for reminder_id, title, reminder_date, reminder_time, description in due_rows:
                line = "{}  |  {}  |  {}".format(
                    title,
                    reminder_date,
                    reminder_time or "--:--"
                )
                if description:
                    line += "\n" + description
                messages.append(line)

            QApplication.beep()
            QMessageBox.information(
                self,
                "یادآوری یسنا",
                "زمان یادآوری موارد زیر فرا رسیده است:\n\n" +
                "\n\n".join(messages)
            )

            self.refresh_dashboard()

        except Exception as error:
            print("Reminder alarm error:", error)

        finally:
            if connection:
                connection.close()

    def load_statistics(self):
        queries = {
            "letters": "SELECT COUNT(*) FROM Letters",
            "postal": "SELECT COUNT(*) FROM PostalLetters",
            "persons": "SELECT COUNT(*) FROM Persons",
            "contacts": (
                "SELECT "
                "(SELECT COUNT(*) FROM PostalSenders) + "
                "(SELECT COUNT(*) FROM PostalReceivers)"
            ),
            "reminders": (
                "SELECT COUNT(*) FROM Reminders "
                "WHERE COALESCE(IsDone, 0)=0"
            )
        }

        connection = None
        try:
            connection = get_connection()
            cursor = connection.cursor()

            for key, query in queries.items():
                cursor.execute(query)
                result = cursor.fetchone()
                value = result[0] if result else 0
                self.stat_labels[key].setText(
                    self.to_persian_digits(value)
                )

        except Exception as error:
            print("Dashboard statistics error:", error)

        finally:
            if connection:
                connection.close()

    def load_today_reminders(self):
        connection = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT ReminderTitle,
                       COALESCE(ReminderTime, ''),
                       COALESCE(IsDone, 0)
                FROM Reminders
                WHERE ReminderDate=?
                ORDER BY ReminderTime, ReminderID
            """, (today_jalali(),))
            rows = cursor.fetchall()

            self.today_reminders.setRowCount(0)
            self.today_reminders_title.setText(
                "📅  یادآوری‌های امروز  |  {} مورد".format(
                    self.to_persian_digits(len(rows))
                )
            )
            if not rows:
                self.today_reminders.setRowCount(1)
                item = QTableWidgetItem("برای امروز یادآوری ثبت نشده است.")
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QColor("#788596"))
                self.today_reminders.setItem(0, 1, item)
                self.today_reminders.setSpan(0, 0, 1, 3)
                self.today_reminders.setRowHeight(0, 42)
                return

            self.today_reminders.clearSpans()
            for row_index, (title, reminder_time, is_done) in enumerate(rows[:6]):
                self.today_reminders.insertRow(row_index)
                done = bool(is_done)
                values = [
                    "◷  " + (reminder_time or "--:--"),
                    title or "بدون عنوان",
                    "✓ انجام‌شده" if done else "● در انتظار"
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(
                        Qt.AlignCenter if col != 1
                        else Qt.AlignRight | Qt.AlignVCenter
                    )
                    if done:
                        item.setForeground(QColor("#718096"))
                    elif col == 2:
                        item.setForeground(QColor("#A87920"))
                    self.today_reminders.setItem(row_index, col, item)
                self.today_reminders.setRowHeight(row_index, 27)

            if len(rows) > 6:
                self.today_reminders_title.setText(
                    "📅  یادآوری‌های امروز  |  {} مورد (۶ مورد اول)".format(
                        self.to_persian_digits(len(rows))
                    )
                )
        except Exception as error:
            self.today_reminders.setRowCount(1)
            item = QTableWidgetItem("خطا در خواندن یادآوری‌ها")
            item.setTextAlignment(Qt.AlignCenter)
            self.today_reminders.setItem(0, 1, item)
            print("Dashboard reminders error:", error)
        finally:
            if connection:
                connection.close()

    @staticmethod
    def to_persian_digits(value):
        digits = "۰۱۲۳۴۵۶۷۸۹"
        return str(value).translate(
            str.maketrans("0123456789", digits)
        )

    def apply_menu_permissions(self):
        for key, button in self.menu_buttons.items():
            allowed = (
                key == "dashboard"
                or has_permission(self.current_user, key)
            )
            if key == "settings":
                allowed = self.current_user.get("Role") == "مدیر سیستم"
            button.setVisible(allowed)

    def menu_clicked(self, key):
        if key != "dashboard" and not has_permission(self.current_user, key):
            show_denied(self, "برای ورود به این بخش دسترسی ندارید.")
            return
        if key == "settings" and self.current_user.get("Role") != "مدیر سیستم":
            show_denied(self, "مدیریت کاربران فقط در اختیار مدیر سیستم است.")
            return

        if key == "dashboard":
            self.show_dashboard()

        elif key == "persons":
            self.open_persons()

        elif key == "letters":
            self.open_letters()

        elif key == "postal":
            self.open_postal()

        elif key == "reminders":
            self.open_reminders()

        elif key == "reports":
            self.open_reports()

        elif key == "settings":
            self.open_settings()

    def add_form_to_stack(self, form):
        if self.stack.indexOf(form) == -1:
            self.stack.addWidget(form)
        self.stack.setCurrentWidget(form)

    def open_persons(self):
        if not has_permission(self.current_user, "persons"):
            show_denied(self)
            return
        if self.persons_window is None:
            self.persons_window = PersonsForm()
            self.persons_window.current_user = self.current_user
            apply_read_only(self.persons_window, self.current_user, "persons")
            protect_form_methods(
                self.persons_window, self.current_user, "persons",
                ["save_person", "delete_person", "remove_template"]
            )

        self.persons_window.show()
        self.persons_window.raise_()
        self.persons_window.activateWindow()

    def open_letters(self):
        if not has_permission(self.current_user, "letters"):
            show_denied(self)
            return
        if self.letters_window is None:
            self.letters_window = LettersForm(
                parent=self,
                on_back=self.show_dashboard,
                on_exit=self.close
            )
            self.stack.addWidget(self.letters_window)
            self.letters_window.current_user = self.current_user
            apply_read_only(self.letters_window, self.current_user, "letters")
            protect_form_methods(
                self.letters_window, self.current_user, "letters",
                ["save_letter", "delete_letter", "add_attachments", "remove_attachment"]
            )

        self.stack.setCurrentWidget(self.letters_window)

    def open_postal(self):
        if not has_permission(self.current_user, "postal"):
            show_denied(self)
            return
        if self.postal_window is None:
            self.postal_window = PostalForm(
                parent=self,
                on_back=self.show_dashboard
            )
            self.stack.addWidget(self.postal_window)
            self.postal_window.current_user = self.current_user
            for child in self.postal_window.findChildren(QWidget):
                child.current_user = self.current_user
            apply_read_only(self.postal_window, self.current_user, "postal")
            protect_form_methods(
                self.postal_window, self.current_user, "postal",
                ["save_record", "mark_sent", "mark_delivered", "delete_record",
                 "capture_mouse_signature", "upload_signature", "clear_signature"]
            )

        self.stack.setCurrentWidget(self.postal_window)

    def open_reminders(self):
        if not has_permission(self.current_user, "reminders"):
            show_denied(self)
            return
        if self.reminders_window is None:
            self.reminders_window = RemindersForm(
                parent=self,
                on_back=self.show_dashboard
            )
            self.stack.addWidget(self.reminders_window)
            self.reminders_window.current_user = self.current_user
            apply_read_only(self.reminders_window, self.current_user, "reminders")
            protect_form_methods(
                self.reminders_window, self.current_user, "reminders",
                ["save_reminder", "mark_done", "delete_reminder"]
            )

        self.stack.setCurrentWidget(self.reminders_window)

    def open_reports(self):
        if not has_permission(self.current_user, "reports"):
            show_denied(self)
            return
        if self.reports_window is None:
            self.reports_window = ReportsForm(
                parent=self,
                on_back=self.show_dashboard
            )
            self.stack.addWidget(self.reports_window)

        self.stack.setCurrentWidget(self.reports_window)


    def open_settings(self):
        if self.current_user.get("Role") != "مدیر سیستم":
            show_denied(self, "تنظیمات و مدیریت کاربران فقط در اختیار مدیر سیستم است.")
            return
        if self.settings_window is None:
            self.settings_window = SettingsUsersForm(
                parent=self,
                on_back=self.show_dashboard
            )
            self.stack.addWidget(self.settings_window)
        else:
            self.settings_window.load_settings()
            self.settings_window.load_users()
        self.stack.setCurrentWidget(self.settings_window)

    def logout(self):
        answer = QMessageBox.question(
            self, "خروج از حساب",
            "از حساب کاربری خارج شوید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return

        if self.music_player is not None:
            self.music_player.stop()

        if self.persons_window is not None:
            self.persons_window.close()

        self.hide()
        login = LoginDialog(self)
        if login.exec_() == LoginDialog.Accepted and login.user:
            self.replacement_window = YasnaWindow(login.user)
            self.replacement_window.showMaximized()
            for timer_name in (
                "clock_timer", "reminder_alarm_timer",
                "dashboard_timer", "session_timer"
            ):
                timer = getattr(self, timer_name, None)
                if timer:
                    timer.stop()
            self._allow_close = True
            self.close()
        else:
            self.showMaximized()

    def verify_active_session(self):
        user_id = self.current_user.get("UserID")
        if user_id is None:
            return
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT IsActive FROM AppUsers WHERE UserID=?",
                (user_id,)
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            QMessageBox.warning(
                self, "حساب غیرفعال شد",
                "حساب کاربری شما غیرفعال شده است. برنامه بسته می‌شود."
            )
            QApplication.quit()

    def apply_theme(self, theme):
        if theme == "dark":
            self.setStyleSheet("""
                QWidget { background-color:#202B38; color:#F2F4F7; }
                QLineEdit, QTextEdit, QComboBox, QTableWidget {
                    background-color:#2C3948; color:#F2F4F7;
                    border:1px solid #526273;
                }
            """)
        else:
            self.setStyleSheet("")

    def show_dashboard(self):
        self.stack.setCurrentWidget(self.dashboard)
        self.refresh_dashboard()

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "خروج از برنامه",
            "آیا مطمئن هستید که می‌خواهید از یسنا خارج شوید؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer == QMessageBox.Yes:
            if self.music_player is not None:
                self.music_player.stop()
            if self.persons_window is not None:
                self.persons_window.close()
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    initialize_database()

    app = QApplication(sys.argv)
    app.setFont(QFont("Tahoma", 10))

    login = LoginDialog()
    if login.exec_() == LoginDialog.Accepted and login.user:
        window = YasnaWindow(login.user)
        window.showMaximized()
        sys.exit(app.exec_())
    sys.exit(0)
