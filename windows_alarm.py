# -*- coding: utf-8 -*-
"""
Windows Task Scheduler integration for Yasna reminders.
Works when Yasna itself is closed, provided the Windows user is signed in.
"""
import os
import sys
import subprocess
from datetime import datetime


TASK_PREFIX = "YasnaReminder_"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALARM_SCRIPT = os.path.join(BASE_DIR, "windows_alarm.py")


def _pythonw_path():
    executable = sys.executable
    folder = os.path.dirname(executable)
    name = os.path.basename(executable).lower()
    if name in ("python.exe", "pythonw.exe"):
        candidate = os.path.join(folder, "pythonw.exe")
        if os.path.isfile(candidate):
            return candidate
    return executable


def remove_reminder_task(reminder_id):
    """Remove the scheduled Windows task for one reminder."""
    task_name = TASK_PREFIX + str(int(reminder_id))
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        # A missing task is not an error for synchronization purposes.
        return result.returncode == 0 or "cannot find" in (
            (result.stdout or "") + (result.stderr or "")
        ).lower()
    except Exception:
        return False


def schedule_reminder_task(reminder_id, year, month, day, hour, minute):
    """
    Create or replace a one-time interactive task for the reminder.
    The task runs under the current Windows account and needs that user
    to be signed in so the sound and dialog can be shown.
    """
    reminder_id = int(reminder_id)
    due = datetime(
        int(year), int(month), int(day), int(hour), int(minute), 0
    )

    if due <= datetime.now():
        remove_reminder_task(reminder_id)
        return True, "موعد یادآوری گذشته است؛ هشدار داخلی برنامه آن را بررسی می‌کند."

    python_exe = _pythonw_path()
    command = '"{}" "{}" --alarm {}'.format(
        python_exe, ALARM_SCRIPT, reminder_id
    )
    task_name = TASK_PREFIX + str(reminder_id)
    task_date = due.strftime("%m/%d/%Y")
    task_time = due.strftime("%H:%M")

    try:
        remove_reminder_task(reminder_id)
        result = subprocess.run(
            [
                "schtasks", "/Create",
                "/TN", task_name,
                "/SC", "ONCE",
                "/SD", task_date,
                "/ST", task_time,
                "/TR", command,
                "/F", "/IT"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if result.returncode == 0:
            return True, "هشدار ویندوز برای این یادآوری زمان‌بندی شد."
        message = (result.stderr or result.stdout or "").strip()
        return False, message or "ساخت وظیفه زمان‌بندی ویندوز ناموفق بود."
    except Exception as error:
        return False, str(error)


def sync_pending_reminders():
    """Create Windows tasks for all pending reminders when Yasna starts."""
    try:
        from database.database import get_connection
        from forms.letters import jalali_to_gregorian

        connection = get_connection()
        try:
            rows = connection.execute("""
                SELECT ReminderID, ReminderDate, COALESCE(ReminderTime, '')
                FROM Reminders
                WHERE COALESCE(IsDone, 0) = 0
                  AND COALESCE(NotifiedAt, '') = ''
            """).fetchall()
        finally:
            connection.close()

        for reminder_id, jalali_date, time_text in rows:
            try:
                parts = [int(value) for value in jalali_date.split("/")]
                gy, gm, gd = jalali_to_gregorian(
                    parts[0], parts[1], parts[2]
                )
                hour, minute = [
                    int(value) for value in (time_text or "23:59").split(":")[:2]
                ]
                schedule_reminder_task(
                    reminder_id, gy, gm, gd, hour, minute
                )
            except Exception as error:
                print("Could not schedule reminder {}: {}".format(
                    reminder_id, error
                ))
    except Exception as error:
        print("Windows reminder synchronization failed:", error)


def run_alarm(reminder_id):
    """Entry point launched by Task Scheduler, without opening the Yasna UI."""
    try:
        from database.database import get_connection
        connection = get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT ReminderTitle, ReminderDate,
                       COALESCE(ReminderTime, ''),
                       COALESCE(Description, ''), COALESCE(IsDone, 0),
                       COALESCE(NotifiedAt, '')
                FROM Reminders
                WHERE ReminderID = ?
                """,
                (int(reminder_id),)
            )
            row = cursor.fetchone()
            if not row or int(row[4]) or row[5]:
                return 0

            title, reminder_date, reminder_time, description = row[:4]
            notified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                UPDATE Reminders SET NotifiedAt = ?
                WHERE ReminderID = ?
                  AND COALESCE(IsDone, 0) = 0
                  AND COALESCE(NotifiedAt, '') = ''
                """,
                (notified_at, int(reminder_id))
            )
            if cursor.rowcount == 0:
                connection.rollback()
                return 0
            connection.commit()
        finally:
            connection.close()

        message = "{}\nتاریخ: {}   ساعت: {}".format(
            title or "یادآوری یسنا",
            reminder_date or "",
            reminder_time or "--:--"
        )
        if description:
            message += "\n\n" + description

        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            winsound.PlaySound(
                "SystemExclamation",
                winsound.SND_ALIAS | winsound.SND_SYNC
            )
        except Exception:
            pass

        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            message,
            "یادآوری یسنا",
            0x00000040 | 0x00010000
        )
        return 0
    except Exception as error:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "خطا در اجرای یادآوری: {}".format(error),
                "Yasna", 0x00000010
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--alarm":
        sys.exit(run_alarm(sys.argv[2]))
    sys.exit(0)
