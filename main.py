
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

        # منوی اصلی در سمت چپ، مطابق تصویر مرجع
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(238)
        sidebar.setStyleSheet("""
            QFrame#sidebar {
                background:#142D4E;
                border-right:1px solid #D8B66A;
            }
        """)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(13, 22, 13, 18)
        side.setSpacing(7)

        brand = QLabel("YASNA")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet(
            "color:#E8CC8B;font-family:Georgia;font-size:29px;"
            "font-weight:bold;letter-spacing:3px;padding:8px;"
        )
        side.addWidget(brand)

        brand_fa = QLabel("سامانه جامع مکاتبات اداری")
        brand_fa.setAlignment(Qt.AlignCenter)
        brand_fa.setStyleSheet(
            "color:#F1E8D6;font-size:11px;padding-bottom:14px;"
        )
        side.addWidget(brand_fa)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color:#52677D;")
        side.addWidget(separator)
        side.addSpacing(9)

        menus = [
            ("⌂     داشبورد", "dashboard"),
            ("✉     نامه‌های اداری", "letters"),
            ("▣     مرسوله‌های پستی", "postal"),
            ("♙     اشخاص و مخاطبان", "persons"),
            ("◷     یادآوری‌ها", "reminders"),
            ("▤     گزارش‌گیری", "reports"),
            ("⚙     تنظیمات و کاربران", "settings")
        ]
        for caption, key in menus:
            button = QPushButton(caption)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(45)
            button.setStyleSheet("""
                QPushButton {
                    color:#F5F1E8;
                    background:transparent;
                    border:1px solid transparent;
                    border-radius:7px;
                    text-align:right;
                    padding-right:14px;
                    font-family:Tahoma;
                    font-size:12px;
                }
                QPushButton:hover {
                    background:#294866;
                    border:1px solid #9E895D;
                    color:#F0D18A;
                }
            """)
            button.clicked.connect(
                lambda checked=False, k=key: self.menu_clicked(k)
            )
            self.menu_buttons[key] = button
            side.addWidget(button)

        side.addStretch(1)
        user_label = QLabel(
            "{}\n{}".format(
                self.current_user.get("FullName", ""),
                self.current_user.get("Role", "")
            )
        )
        user_label.setAlignment(Qt.AlignCenter)
        user_label.setStyleSheet(
            "color:#E8D7AF;font-size:10px;padding:11px;"
            "border-top:1px solid #52677D;"
        )
        side.addWidget(user_label)

        logout_button = QPushButton("خروج از سامانه")
        logout_button.setMinimumHeight(37)
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setStyleSheet("""
            QPushButton {
                color:white;background:#294866;
                border:1px solid #A88D52;border-radius:7px;padding:7px;
            }
            QPushButton:hover { background:#934848; }
        """)
        logout_button.clicked.connect(self.logout)
        side.addWidget(logout_button)

        version = QLabel("YASNA DESKTOP  •  1.0")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color:#9EADBC;font-size:8px;padding-top:8px;")
        side.addWidget(version)

        # محتوای اصلی
        content = QWidget()
        content.setLayoutDirection(Qt.RightToLeft)
        content.setStyleSheet(
            "background-color:#F2EDE1;"
        )
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(20, 16, 20, 18)
        main_layout.setSpacing(13)

        # سربرگ فاخر: پرچم، نام یسنا و نمای تهران
        header = QFrame()
        header.setObjectName("referenceHeader")
        header.setMinimumHeight(148)
        header.setMaximumHeight(158)
        header.setStyleSheet("""
            QFrame#referenceHeader {
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #243F58, stop:0.52 #3E596D, stop:1 #8B7858);
                border:2px solid #C5A45E;
                border-radius:8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setDirection(QHBoxLayout.LeftToRight)
        header_layout.setContentsMargins(17, 10, 17, 10)
        header_layout.setSpacing(12)

        flag_box = QLabel("🇮🇷")
        flag_box.setAlignment(Qt.AlignCenter)
        flag_box.setFixedWidth(105)
        flag_box.setStyleSheet(
            "font-size:65px;background:transparent;border:0;"
        )
        header_layout.addWidget(flag_box, 0)

        heading_box = QVBoxLayout()
        heading_box.setAlignment(Qt.AlignCenter)
        heading_box.setSpacing(6)
        heading_en = QLabel("YASNA")
        heading_en.setAlignment(Qt.AlignCenter)
        heading_en.setStyleSheet(
            "color:#F3D58E;font-family:Georgia;font-size:30px;"
            "font-weight:bold;letter-spacing:5px;"
        )
        heading_fa = QLabel("نرم افزار جامع مکاتبات و مدیریت اداری")
        heading_fa.setAlignment(Qt.AlignCenter)
        heading_fa.setStyleSheet(
            "color:#FFF9ED;font-size:16px;font-weight:bold;"
        )
        heading_slogan = QLabel("سازمان شما، افتخار ماست")
        heading_slogan.setAlignment(Qt.AlignCenter)
        heading_slogan.setStyleSheet(
            "color:#EAD7AD;font-size:11px;"
        )
        heading_box.addWidget(heading_en)
        heading_box.addWidget(heading_fa)
        heading_box.addWidget(heading_slogan)
        header_layout.addLayout(heading_box, 1)

        panorama_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "tehran_panorama.svg"
        )
        if SVG_AVAILABLE and os.path.isfile(panorama_path):
            panorama = QSvgWidget(panorama_path)
            panorama.setFixedSize(405, 116)
            header_layout.addWidget(panorama, 0, Qt.AlignVCenter)
        else:
            panorama = QLabel("تهران  •  برج میلاد  •  رشته‌کوه البرز")
            panorama.setAlignment(Qt.AlignCenter)
            panorama.setStyleSheet("color:#F5E7C9;font-size:14px;")
            header_layout.addWidget(panorama, 0)

        main_layout.addWidget(header)

        # ساعت عقربه‌ای در سمت چپ و پیام خوشامد در سمت راست
        top_row = QHBoxLayout()
        top_row.setDirection(QHBoxLayout.LeftToRight)
        top_row.setSpacing(13)

        clock_box = QFrame()
        clock_box.setFixedWidth(242)
        clock_box.setMinimumHeight(206)
        clock_box.setStyleSheet("""
            QFrame {
                background:#FBF9F3;
                border:1px solid #CDB77F;
                border-radius:8px;
            }
        """)
        clock_layout = QVBoxLayout(clock_box)
        clock_layout.setContentsMargins(8, 8, 8, 8)
        clock_layout.setAlignment(Qt.AlignCenter)
        clock_title = QLabel("ساعت")
        clock_title.setAlignment(Qt.AlignCenter)
        clock_title.setStyleSheet(
            "color:#142D4E;font-size:14px;font-weight:bold;"
        )
        clock_layout.addWidget(clock_title)
        clock_layout.addWidget(AnalogClock(), 0, Qt.AlignCenter)
        self.date_label = QLabel("")
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet(
            "color:#8C6C31;font-size:11px;font-weight:bold;"
        )
        clock_layout.addWidget(self.date_label)

        welcome_box = QFrame()
        welcome_box.setMinimumHeight(206)
        welcome_box.setStyleSheet("""
            QFrame {
                background:#FBF9F3;
                border:2px solid #CDB77F;
                border-radius:8px;
            }
        """)
        welcome_layout = QVBoxLayout(welcome_box)
        welcome_layout.setContentsMargins(22, 17, 22, 15)
        welcome_layout.setSpacing(9)

        welcome_title = QLabel("به یسنا خوش آمدید")
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_title.setStyleSheet(
            "color:#142D4E;font-size:21px;font-weight:bold;"
        )
        welcome_text = QLabel(
            "نرم‌افزار جامع مکاتبات و مدیریت اداری\n"
            "همه امور سازمانی شما، یکپارچه و منظم"
        )
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet(
            "color:#5B6470;font-size:13px;line-height:1.5;"
        )
        self.digital_clock = QLabel("")
        self.digital_clock.setAlignment(Qt.AlignCenter)
        self.digital_clock.setStyleSheet(
            "color:#A9853F;font-size:25px;font-weight:bold;"
        )
        welcome_layout.addWidget(welcome_title)
        welcome_layout.addWidget(welcome_text)
        welcome_layout.addStretch(1)
        welcome_layout.addWidget(self.digital_clock)

        # کنترل موسیقی برای حفظ امکان قبلی، در نوار کوچک پایین خوشامد
        music_row = QHBoxLayout()
        self.btn_choose_music = QPushButton("انتخاب آهنگ")
        self.btn_music_toggle = QPushButton("پخش / توقف")
        for music_button in (self.btn_choose_music, self.btn_music_toggle):
            music_button.setCursor(Qt.PointingHandCursor)
            music_button.setStyleSheet("""
                QPushButton {
                    background:#E6D7B5;color:#263D52;
                    border:1px solid #B99A58;border-radius:5px;
                    padding:5px 10px;font-size:10px;
                }
                QPushButton:hover { background:#D8B66A; }
            """)
            music_row.addWidget(music_button)
        self.btn_choose_music.clicked.connect(self.choose_music)
        self.btn_music_toggle.clicked.connect(self.toggle_music)
        self.music_auto_checkbox = QCheckBox("پخش خودکار")
        self.music_auto_checkbox.setChecked(True)
        self.music_auto_checkbox.setStyleSheet("color:#5C513E;font-size:10px;")
        self.music_auto_checkbox.toggled.connect(self.save_music_autoplay)
        music_row.addWidget(self.music_auto_checkbox)
        music_row.addStretch(1)
        welcome_layout.addLayout(music_row)

        top_row.addWidget(clock_box, 0)
        top_row.addWidget(welcome_box, 1)
        main_layout.addLayout(top_row)

        # پنج کارت آماری
        stats_heading = QLabel("گزارش سریع اطلاعات سامانه")
        stats_heading.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        stats_heading.setStyleSheet(
            "color:#142D4E;font-size:15px;font-weight:bold;padding:3px 5px;"
        )
        main_layout.addWidget(stats_heading)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(10)
        stats_grid.setVerticalSpacing(8)
        self.stat_labels = {}

        stat_items = [
            ("letters", "نامه‌های اداری", "✉"),
            ("postal", "مرسوله‌های پستی", "▣"),
            ("persons", "اشخاص", "♙"),
            ("contacts", "مخاطبان", "♧"),
            ("reminders", "یادآوری‌های فعال", "◷")
        ]
        for index, (key, caption_text, symbol) in enumerate(stat_items):
            card = QFrame()
            card.setMinimumHeight(112)
            card.setStyleSheet("""
                QFrame {
                    background:#FBF9F3;
                    border:1px solid #D8C99F;
                    border-bottom:4px solid #C4A35C;
                    border-radius:7px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(7, 6, 7, 7)
            card_layout.setSpacing(3)
            symbol_label = QLabel(symbol)
            symbol_label.setAlignment(Qt.AlignCenter)
            symbol_label.setStyleSheet(
                "color:#B18A43;font-size:22px;border:0;"
            )
            number = QLabel("۰")
            number.setAlignment(Qt.AlignCenter)
            number.setStyleSheet(
                "color:#142D4E;font-size:25px;font-weight:bold;border:0;"
            )
            caption = QLabel(caption_text)
            caption.setWordWrap(True)
            caption.setAlignment(Qt.AlignCenter)
            caption.setStyleSheet(
                "color:#596574;font-size:10px;border:0;"
            )
            card_layout.addWidget(symbol_label)
            card_layout.addWidget(number)
            card_layout.addWidget(caption)
            self.stat_labels[key] = number
            stats_grid.addWidget(card, 0, index)
            stats_grid.setColumnStretch(index, 1)
        main_layout.addLayout(stats_grid)

        # یادآوری‌های امروز و سخن بزرگان
        bottom_row = QHBoxLayout()
        bottom_row.setDirection(QHBoxLayout.LeftToRight)
        bottom_row.setSpacing(13)

        reminders_box = QFrame()
        reminders_box.setMinimumHeight(190)
        reminders_box.setStyleSheet("""
            QFrame {
                background:#FBF9F3;
                border:1px solid #CDB77F;
                border-radius:8px;
            }
        """)
        reminders_layout = QVBoxLayout(reminders_box)
        reminders_layout.setContentsMargins(15, 12, 15, 12)
        reminders_layout.setSpacing(8)
        reminders_heading = QLabel("◷   یادآوری‌های امروز")
        reminders_heading.setStyleSheet(
            "color:#142D4E;font-size:15px;font-weight:bold;"
        )
        self.today_reminders = QLabel("در حال دریافت اطلاعات...")
        self.today_reminders.setWordWrap(True)
        self.today_reminders.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.today_reminders.setStyleSheet(
            "color:#4B5968;font-size:11px;padding:5px;"
        )
        reminders_layout.addWidget(reminders_heading)
        reminders_layout.addWidget(self.today_reminders, 1)

        quote_box = QFrame()
        quote_box.setMinimumHeight(190)
        quote_box.setStyleSheet("""
            QFrame {
                background:#F4EAD4;
                border:2px solid #C5A45E;
                border-radius:8px;
            }
        """)
        quote_layout = QVBoxLayout(quote_box)
        quote_layout.setContentsMargins(16, 12, 16, 12)
        quote_layout.setSpacing(6)
        quote_heading = QLabel("✦   سخن بزرگان")
        quote_heading.setAlignment(Qt.AlignCenter)
        quote_heading.setStyleSheet(
            "color:#8A682F;font-size:15px;font-weight:bold;"
        )
        self.quote_text = QLabel("")
        self.quote_text.setWordWrap(True)
        self.quote_text.setAlignment(Qt.AlignCenter)
        self.quote_text.setStyleSheet(
            "color:#263B50;font-size:14px;font-weight:bold;padding:7px;"
        )
        self.quote_meaning = QLabel("")
        self.quote_meaning.setWordWrap(True)
        self.quote_meaning.setAlignment(Qt.AlignCenter)
        self.quote_meaning.setStyleSheet(
            "color:#5C6470;font-size:10px;"
        )
        self.quote_source = QLabel("")
        self.quote_source.setWordWrap(True)
        self.quote_source.setAlignment(Qt.AlignCenter)
        self.quote_source.setStyleSheet(
            "color:#98783E;font-size:10px;font-weight:bold;"
        )
        quote_layout.addWidget(quote_heading)
        quote_layout.addStretch(1)
        quote_layout.addWidget(self.quote_text)
        quote_layout.addWidget(self.quote_meaning)
        quote_layout.addWidget(self.quote_source)
        quote_layout.addStretch(1)

        bottom_row.addWidget(reminders_box, 1)
        bottom_row.addWidget(quote_box, 1)
        main_layout.addLayout(bottom_row)
        main_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(
            "QScrollArea{background:#F2EDE1;border:0;}"
        )
        scroll_area.setWidget(content)

        # ترتیب افزودن کنترل‌ها تعیین می‌کند منو واقعاً در چپ قرار بگیرد.
        root.addWidget(sidebar, 0)
        root.addWidget(scroll_area, 1)

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
