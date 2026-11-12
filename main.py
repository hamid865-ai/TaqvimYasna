
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
        image_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "Untitled.jpg"
        )
        self.dashboard = DashboardCanvas(image_path)

        # لایه‌های زنده دقیقاً روی بخش‌های متناظر تصویر مرجع قرار می‌گیرند.
        self.menu_buttons = {}
        menu_areas = [
            ("dashboard", 8, 244, 184, 66),
            ("letters", 8, 319, 184, 65),
            ("postal", 8, 385, 184, 64),
            ("persons", 8, 450, 184, 65),
            ("reminders", 8, 516, 184, 64),
            ("reports", 8, 581, 184, 64),
            ("settings", 8, 646, 184, 64),
        ]
        for key, x, y, width, height in menu_areas:
            button = QPushButton("", self.dashboard)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip({
                "dashboard": "داشبورد",
                "letters": "نامه‌های اداری",
                "postal": "مرسوله‌های پستی",
                "persons": "اشخاص و مخاطبان",
                "reminders": "یادآوری‌ها",
                "reports": "گزارش‌گیری",
                "settings": "تنظیمات و کاربران"
            }[key])
            button.setStyleSheet("""
                QPushButton {
                    background:transparent;
                    border:1px solid transparent;
                    border-radius:8px;
                }
                QPushButton:hover {
                    background:rgba(226,190,111,35);
                    border:1px solid rgba(232,202,139,190);
                }
                QPushButton:pressed {
                    background:rgba(226,190,111,65);
                }
            """)
            button.clicked.connect(
                lambda checked=False, k=key: self.menu_clicked(k)
            )
            self.dashboard.place(button, x, y, width, height)
            self.menu_buttons[key] = button

        # خروج از سامانه روی دکمه خروج داخل تصویر مرجع
        logout_button = QPushButton("", self.dashboard)
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setToolTip("خروج از سامانه")
        logout_button.setStyleSheet("""
            QPushButton { background:transparent;border:1px solid transparent;border-radius:8px; }
            QPushButton:hover { background:rgba(220,90,75,35);border:1px solid rgba(220,90,75,170); }
        """)
        logout_button.clicked.connect(self.logout)
        self.dashboard.place(logout_button, 8, 752, 184, 66)

        # سخن روز در قاب بالایی؛ متن و گوینده از بانک سخنان خوانده می‌شوند.
        self.quote_top_source = QLabel("", self.dashboard)
        self.quote_top_source.setAlignment(Qt.AlignCenter)
        self.quote_top_source.setStyleSheet(
            "background:rgba(250,240,220,238);color:#142D4E;font-size:15px;"
            "font-weight:bold;border:0;"
        )
        self.dashboard.place(self.quote_top_source, 590, 244, 700, 35)

        self.quote_top_text = QLabel("", self.dashboard)
        self.quote_top_text.setWordWrap(True)
        self.quote_top_text.setAlignment(Qt.AlignCenter)
        self.quote_top_text.setStyleSheet(
            "background:rgba(250,240,220,238);color:#172B40;font-size:19px;"
            "font-weight:bold;border:0;padding:2px;"
        )
        self.dashboard.place(self.quote_top_text, 600, 278, 690, 70)

        # تاریخ شمسی و ساعت دیجیتال زیر ساعت عقربه‌ای تصویر.
        self.date_label = QLabel("", self.dashboard)
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet(
            "background:rgba(246,235,213,225);color:#142D4E;"
            "font-size:12px;font-weight:bold;border:0;"
        )
        self.dashboard.place(self.date_label, 225, 510, 310, 30)

        self.digital_clock = QLabel("", self.dashboard)
        self.digital_clock.setAlignment(Qt.AlignCenter)
        self.digital_clock.setStyleSheet(
            "background:rgba(246,235,213,225);color:#9B7330;"
            "font-size:13px;font-weight:bold;border:0;"
        )
        self.dashboard.place(self.digital_clock, 270, 540, 220, 25)

        # اعداد پنج کارت آماری؛ عنوان‌ها و آیکون‌های تصویر مرجع دست‌نخورده‌اند.
        self.stat_labels = {}
        stat_positions = {
            "letters": (590, 477, 165, 43),
            "postal": (800, 477, 170, 43),
            "persons": (1010, 477, 170, 43),
            "contacts": (1220, 477, 170, 43),
            "reminders": (1430, 477, 165, 43),
        }
        for key, geometry in stat_positions.items():
            number = QLabel("۰", self.dashboard)
            number.setAlignment(Qt.AlignCenter)
            number.setStyleSheet(
                "background:rgba(255,250,242,235);color:#142D4E;"
                "font-size:25px;font-weight:bold;border:0;"
            )
            self.dashboard.place(number, *geometry)
            self.stat_labels[key] = number

        # فهرست واقعی یادآوری‌های امروز روی کادر سمت چپ پایین.
        self.today_reminders = QLabel("", self.dashboard)
        self.today_reminders.setWordWrap(True)
        self.today_reminders.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.today_reminders.setStyleSheet(
            "background:rgba(255,252,246,225);color:#142D4E;"
            "font-size:12px;font-weight:bold;border:0;padding:8px;"
        )
        self.dashboard.place(self.today_reminders, 228, 642, 515, 190)

        # سخن بزرگان در قاب تزئینی پایین سمت راست.
        self.quote_text = QLabel("", self.dashboard)
        self.quote_text.setWordWrap(True)
        self.quote_text.setAlignment(Qt.AlignCenter)
        self.quote_text.setStyleSheet(
            "background:rgba(250,240,220,242);color:#172B40;"
            "font-size:17px;font-weight:bold;border:0;padding:8px;"
        )
        self.dashboard.place(self.quote_text, 820, 685, 690, 105)

        self.quote_meaning = QLabel("", self.dashboard)
        self.quote_meaning.setWordWrap(True)
        self.quote_meaning.setAlignment(Qt.AlignCenter)
        self.quote_meaning.setStyleSheet(
            "background:transparent;color:#5C5140;font-size:10px;border:0;"
        )
        self.dashboard.place(self.quote_meaning, 850, 790, 620, 22)

        self.quote_source = QLabel("", self.dashboard)
        self.quote_source.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.quote_source.setStyleSheet(
            "background:transparent;color:#98733A;font-size:11px;"
            "font-weight:bold;border:0;"
        )
        self.dashboard.place(self.quote_source, 815, 812, 650, 25)

        # کنترل موسیقی قبلی حفظ شده و در پایین نوار کناری قرار دارد.
        self.btn_choose_music = QPushButton("♫", self.dashboard)
        self.btn_choose_music.setToolTip("انتخاب موسیقی")
        self.btn_choose_music.setCursor(Qt.PointingHandCursor)
        self.btn_choose_music.setStyleSheet(
            "background:rgba(22,49,76,220);color:#F2D99F;"
            "border:1px solid #C5A45E;border-radius:5px;font-size:13px;"
        )
        self.btn_choose_music.clicked.connect(self.choose_music)
        self.dashboard.place(self.btn_choose_music, 18, 850, 45, 30)

        self.btn_music_toggle = QPushButton("▶", self.dashboard)
        self.btn_music_toggle.setToolTip("پخش یا توقف موسیقی")
        self.btn_music_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_music_toggle.setStyleSheet(
            "background:rgba(22,49,76,220);color:#F2D99F;"
            "border:1px solid #C5A45E;border-radius:5px;font-size:12px;"
        )
        self.btn_music_toggle.clicked.connect(self.toggle_music)
        self.dashboard.place(self.btn_music_toggle, 68, 850, 45, 30)

        self.music_auto_checkbox = QCheckBox("پخش خودکار", self.dashboard)
        self.music_auto_checkbox.setChecked(True)
        self.music_auto_checkbox.setStyleSheet(
            "background:rgba(22,49,76,190);color:#F2D99F;font-size:9px;"
        )
        self.music_auto_checkbox.toggled.connect(self.save_music_autoplay)
        self.dashboard.place(self.music_auto_checkbox, 116, 850, 78, 30)

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
        self.quote_text.setText("«%s»" % quote)
        self.quote_meaning.setText(meaning)
        self.quote_source.setText(source)
        self.quote_top_text.setText("«%s»" % quote)
        self.quote_top_source.setText(source)

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
