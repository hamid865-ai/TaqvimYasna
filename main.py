
# -*- coding: utf-8 -*-
import sys
import os
import math
import sqlite3

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QStackedWidget, QMessageBox, QGraphicsDropShadowEffect,
    QScrollArea, QFileDialog, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, QTime, QPointF, QUrl
from PyQt5.QtGui import (
    QFont, QPainter, QPen, QBrush, QColor, QPolygonF
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
    from data.daily_quotes import get_daily_quote
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

        self.dashboard = QWidget()
        self.create_dashboard()
        self.stack.addWidget(self.dashboard)

    def create_dashboard(self):
        root = QHBoxLayout(self.dashboard)
        root.setDirection(QHBoxLayout.LeftToRight)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # نوار کناری ثابت در سمت راست
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)
        sidebar.setStyleSheet(
            "QFrame#sidebar { background-color:%s; }" % NAVY
        )
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 24, 16, 18)
        side_layout.setSpacing(9)

        logo = QLabel("✦  YASNA")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "color:%s;font-size:27px;font-weight:bold;padding:12px;" % GOLD
        )
        side_layout.addWidget(logo)

        subtitle = QLabel("سیستم مدیریت مکاتبات اداری")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color:#DCE5ED;font-size:11px;padding-bottom:14px;")
        side_layout.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#38536D;")
        side_layout.addWidget(line)
        side_layout.addSpacing(10)

        menus = [
            ("⌂   داشبورد", "dashboard"),
            ("✉   نامه‌های اداری", "letters"),
            ("▣   نامه‌های پستی", "postal"),
            ("♙   اشخاص و مخاطبان", "persons"),
            ("◷   یادآوری‌ها", "reminders"),
            ("▤   گزارش‌گیری", "reports"),
            ("⚙   تنظیمات و کاربران", "settings")
        ]

        for title, key in menus:
            button = QPushButton(title)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(46)
            button.setStyleSheet("""
                QPushButton {
                    color:#F4F6F8;
                    background:transparent;
                    border:0;
                    border-radius:9px;
                    text-align:right;
                    padding-right:15px;
                    font-size:13px;
                }
                QPushButton:hover {
                    background:#294B6C;
                    color:#D8B66A;
                }
            """)
            button.clicked.connect(
                lambda checked=False, k=key: self.menu_clicked(k)
            )
            self.menu_buttons[key] = button
            side_layout.addWidget(button)

        side_layout.addStretch()

        user_label = QLabel(
            "{}\n{}".format(
                self.current_user.get("FullName", ""),
                self.current_user.get("Role", "")
            )
        )
        user_label.setAlignment(Qt.AlignCenter)
        user_label.setStyleSheet(
            "color:#E8D7AF;font-size:10px;padding:10px;"
            "border-top:1px solid #38536D;"
        )
        side_layout.addWidget(user_label)

        logout_button = QPushButton("خروج از حساب")
        logout_button.setMinimumHeight(38)
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setStyleSheet("""
            QPushButton {
                color:white;background:#294B6C;border:1px solid #526B82;
                border-radius:8px;padding:6px;
            }
            QPushButton:hover { background:#9B4545; }
        """)
        logout_button.clicked.connect(self.logout)
        side_layout.addWidget(logout_button)

        version = QLabel("Yasna Desktop  |  Version 1.0")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color:#9EAFBF;font-size:9px;padding-top:5px;")
        side_layout.addWidget(version)

        # محتوای اصلی داخل ناحیه اسکرول؛ بدون تحمیل عرض اضافی
        content = QWidget()
        content.setLayoutDirection(Qt.RightToLeft)
        content.setStyleSheet("background-color:%s;" % CREAM)
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(22, 20, 22, 22)
        main_layout.setSpacing(16)

        # سربرگ اصلی: عنوان، تصویر تهران و کنترل موسیقی
        header = QFrame()
        header.setObjectName("dashboardHeader")
        header.setMinimumHeight(142)
        header.setStyleSheet("""
            QFrame#dashboardHeader {
                background-color:#183B56;
                border:1px solid #294F6C;
                border-radius:15px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(9)
        title = QLabel("سامانه مدیریت مکاتبات یسنا")
        title.setWordWrap(True)
        title.setStyleSheet(
            "color:white;font-size:20px;font-weight:bold;"
        )
        self.date_label = QLabel("")
        self.date_label.setStyleSheet(
            "color:#E8D7AF;font-size:12px;"
        )
        title_box.addWidget(title)
        title_box.addWidget(self.date_label)
        title_box.addStretch()
        header_layout.addLayout(title_box, 2)
        header_layout.addStretch(1)

        panorama_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "tehran_panorama.svg"
        )
        if SVG_AVAILABLE and os.path.isfile(panorama_path):
            panorama = QSvgWidget(panorama_path)
            panorama.setFixedSize(390, 102)
            header_layout.addWidget(panorama, 0, Qt.AlignVCenter)
        else:
            panorama = QLabel("تهران  |  برج میلاد  |  البرز  🇮🇷")
            panorama.setAlignment(Qt.AlignCenter)
            panorama.setStyleSheet(
                "color:#E8D7AF;font-size:15px;font-weight:bold;"
            )
            header_layout.addWidget(panorama, 0, Qt.AlignVCenter)

        music_controls = QVBoxLayout()
        music_controls.setSpacing(6)
        self.btn_choose_music = QPushButton("انتخاب آهنگ")
        self.btn_choose_music.setCursor(Qt.PointingHandCursor)
        self.btn_choose_music.setStyleSheet("""
            QPushButton {
                background:#D8B66A;color:#142D4E;border:0;
                border-radius:7px;padding:7px 11px;font-weight:bold;
            }
            QPushButton:hover { background:#E8CC8B; }
        """)
        self.btn_choose_music.clicked.connect(self.choose_music)

        self.btn_music_toggle = QPushButton("پخش / توقف")
        self.btn_music_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_music_toggle.setStyleSheet("""
            QPushButton {
                background:#294B6C;color:white;border:1px solid #D8B66A;
                border-radius:7px;padding:7px 11px;
            }
            QPushButton:hover { background:#365D80; }
        """)
        self.btn_music_toggle.clicked.connect(self.toggle_music)

        self.music_auto_checkbox = QCheckBox("پخش خودکار")
        self.music_auto_checkbox.setChecked(True)
        self.music_auto_checkbox.setStyleSheet("color:white;font-size:10px;")
        self.music_auto_checkbox.toggled.connect(self.save_music_autoplay)

        music_controls.addWidget(self.btn_choose_music)
        music_controls.addWidget(self.btn_music_toggle)
        music_controls.addWidget(self.music_auto_checkbox)
        header_layout.addLayout(music_controls, 0)
        main_layout.addWidget(header)

        # خوشامدگویی و ساعت
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        clock_box = QFrame()
        clock_box.setMinimumWidth(245)
        clock_box.setMinimumHeight(210)
        clock_box.setStyleSheet(
            "QFrame{background:white;border-radius:14px;}"
        )
        clock_layout = QVBoxLayout(clock_box)
        clock_layout.setContentsMargins(12, 10, 12, 10)
        clock_layout.setAlignment(Qt.AlignCenter)

        clock_title = QLabel("ساعت")
        clock_title.setAlignment(Qt.AlignCenter)
        clock_title.setStyleSheet(
            "color:%s;font-size:14px;font-weight:bold;" % NAVY
        )
        clock_layout.addWidget(clock_title)
        clock_layout.addWidget(AnalogClock(), 0, Qt.AlignCenter)

        welcome_box = QFrame()
        welcome_box.setMinimumHeight(210)
        welcome_box.setStyleSheet(
            "QFrame{background:white;border-radius:14px;}"
        )
        welcome_layout = QVBoxLayout(welcome_box)
        welcome_layout.setContentsMargins(24, 22, 24, 20)
        welcome_layout.setSpacing(12)

        welcome = QLabel("خوش آمدید")
        welcome.setStyleSheet(
            "color:%s;font-size:25px;font-weight:bold;" % NAVY
        )
        welcome_text = QLabel(
            "به فضای کاری یسنا خوش آمدید.\n"
            "مدیریت نامه‌ها، مخاطبان و یادآوری‌ها در یک نگاه."
        )
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet(
            "color:%s;font-size:13px;line-height:1.5;" % MUTED
        )
        self.digital_clock = QLabel("")
        self.digital_clock.setStyleSheet(
            "color:%s;font-size:25px;font-weight:bold;" % GOLD
        )
        welcome_layout.addWidget(welcome)
        welcome_layout.addWidget(welcome_text)
        welcome_layout.addStretch()
        welcome_layout.addWidget(self.digital_clock)
        top_row.addWidget(clock_box, 0)
        top_row.addWidget(welcome_box, 1)
        main_layout.addLayout(top_row)

        # کارت‌های آماری هم‌اندازه
        stats_title = QLabel("نمای کلی اطلاعات")
        stats_title.setStyleSheet(
            "color:%s;font-size:17px;font-weight:bold;padding:2px 3px;" % NAVY
        )
        main_layout.addWidget(stats_title)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(12)
        stats_grid.setVerticalSpacing(12)
        self.stat_labels = {}

        stat_items = [
            ("letters", "نامه‌های اداری", "✉"),
            ("postal", "نامه‌های پستی", "▣"),
            ("persons", "اشخاص", "♙"),
            ("contacts", "فرستندگان و گیرندگان", "♧"),
            ("reminders", "یادآوری‌های فعال", "◷")
        ]

        for index, (key, caption_text, symbol) in enumerate(stat_items):
            card = QFrame()
            card.setMinimumHeight(125)
            card.setStyleSheet("""
                QFrame {
                    background:white;
                    border:1px solid #E6E1D6;
                    border-bottom:4px solid #D8B66A;
                    border-radius:12px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 9, 10, 10)
            card_layout.setSpacing(5)

            symbol_label = QLabel(symbol)
            symbol_label.setAlignment(Qt.AlignCenter)
            symbol_label.setStyleSheet(
                "color:%s;font-size:21px;" % GOLD
            )
            number = QLabel("۰")
            number.setAlignment(Qt.AlignCenter)
            number.setStyleSheet(
                "color:%s;font-size:26px;font-weight:bold;" % NAVY
            )
            caption = QLabel(caption_text)
            caption.setWordWrap(True)
            caption.setAlignment(Qt.AlignCenter)
            caption.setStyleSheet(
                "color:%s;font-size:11px;" % MUTED
            )

            card_layout.addWidget(symbol_label)
            card_layout.addWidget(number)
            card_layout.addWidget(caption)
            self.stat_labels[key] = number
            stats_grid.addWidget(card, 0, index)
            stats_grid.setColumnStretch(index, 1)

        main_layout.addLayout(stats_grid)

        # یادآوری‌ها و سخن روز
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        quote_box = QFrame()
        quote_box.setMinimumHeight(205)
        quote_box.setStyleSheet("""
            QFrame {
                background:#183B56;
                border:2px solid #D8B66A;
                border-radius:14px;
            }
        """)
        quote_layout = QVBoxLayout(quote_box)
        quote_layout.setContentsMargins(18, 14, 18, 14)
        quote_layout.setSpacing(8)

        quote_heading = QLabel("✦  سخن روز")
        quote_heading.setAlignment(Qt.AlignCenter)
        quote_heading.setStyleSheet(
            "color:%s;font-size:16px;font-weight:bold;" % GOLD
        )
        self.quote_text = QLabel("")
        self.quote_text.setWordWrap(True)
        self.quote_text.setAlignment(Qt.AlignCenter)
        self.quote_text.setStyleSheet(
            "color:white;font-size:15px;padding:8px;"
        )
        self.quote_meaning = QLabel("")
        self.quote_meaning.setWordWrap(True)
        self.quote_meaning.setAlignment(Qt.AlignCenter)
        self.quote_meaning.setStyleSheet(
            "color:#F3EAD5;font-size:11px;padding:4px;"
        )
        self.quote_source = QLabel("")
        self.quote_source.setWordWrap(True)
        self.quote_source.setAlignment(Qt.AlignCenter)
        self.quote_source.setStyleSheet(
            "color:#E8D7AF;font-size:10px;"
        )
        quote_layout.addWidget(quote_heading)
        quote_layout.addStretch(1)
        quote_layout.addWidget(self.quote_text)
        quote_layout.addWidget(self.quote_meaning)
        quote_layout.addWidget(self.quote_source)
        quote_layout.addStretch(1)

        reminders_box = QFrame()
        reminders_box.setMinimumHeight(205)
        reminders_box.setStyleSheet(
            "QFrame{background:white;border:1px solid #E6E1D6;"
            "border-radius:14px;}"
        )
        reminders_layout = QVBoxLayout(reminders_box)
        reminders_layout.setContentsMargins(18, 14, 18, 14)
        reminders_layout.setSpacing(10)

        reminders_heading = QLabel("یادآوری‌های امروز")
        reminders_heading.setStyleSheet(
            "color:%s;font-size:16px;font-weight:bold;" % NAVY
        )
        self.today_reminders = QLabel("در حال دریافت اطلاعات...")
        self.today_reminders.setWordWrap(True)
        self.today_reminders.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.today_reminders.setStyleSheet(
            "color:%s;font-size:12px;padding:6px;" % TEXT
        )
        reminders_layout.addWidget(reminders_heading)
        reminders_layout.addWidget(self.today_reminders, 1)

        bottom_row.addWidget(quote_box, 1)
        bottom_row.addWidget(reminders_box, 1)
        main_layout.addLayout(bottom_row)

        # فضای انتهایی برای جلوگیری از فشرده‌شدن کارت‌ها
        main_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(
            "QScrollArea{background:%s;border:0;}" % CREAM
        )
        scroll_area.setWidget(content)

        # محتوای اصلی در چپ و نوار کناری در راست
        root.addWidget(scroll_area, 1)
        root.addWidget(sidebar, 0)

        self.update_clock()
        self.show_daily_quote()

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
        self.quote_text.setText("«%s»" % quote)
        self.quote_meaning.setText(meaning)
        self.quote_source.setText(source)

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
            self.date_label.setText(
                "امروز: " + today_jalali()
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
                       COALESCE(Description, '')
                FROM Reminders
                WHERE ReminderDate=?
                  AND COALESCE(IsDone, 0)=0
                ORDER BY ReminderTime, ReminderID
            """, (today_jalali(),))

            rows = cursor.fetchall()

            if not rows:
                self.today_reminders.setText(
                    "برای امروز یادآوری ثبت نشده است."
                )
                return

            lines = []
            for title, reminder_time, description in rows[:5]:
                time_text = reminder_time if reminder_time else "--:--"
                lines.append(
                    "◈  %s   |   %s" % (title, time_text)
                )

            if len(rows) > 5:
                lines.append(
                    "و %s یادآوری دیگر..." %
                    self.to_persian_digits(len(rows) - 5)
                )

            self.today_reminders.setText("\n\n".join(lines))

        except Exception as error:
            self.today_reminders.setText(
                "خطا در خواندن یادآوری‌ها."
            )
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
