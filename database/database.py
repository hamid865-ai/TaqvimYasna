# -*- coding: utf-8 -*-
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "Yasna.db")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _columns(cursor, table_name):
    cursor.execute("PRAGMA table_info({})".format(table_name))
    return [row[1] for row in cursor.fetchall()]


def _add_column(cursor, table_name, column_name, definition):
    if column_name not in _columns(cursor, table_name):
        cursor.execute(
            "ALTER TABLE {} ADD COLUMN {} {}".format(
                table_name, column_name, definition
            )
        )


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""CREATE TABLE IF NOT EXISTS Persons (
            PersonID INTEGER PRIMARY KEY AUTOINCREMENT,
            PersonName TEXT NOT NULL, Organization TEXT, Phone TEXT,
            Address TEXT, Description TEXT, TemplatePath TEXT)""")
        _add_column(cursor, "Persons", "TemplatePath", "TEXT")

        cursor.execute("""CREATE TABLE IF NOT EXISTS Subjects (
            SubjectID INTEGER PRIMARY KEY AUTOINCREMENT,
            SubjectName TEXT NOT NULL, SubjectDescription TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Signators (
            SignatorID INTEGER PRIMARY KEY AUTOINCREMENT,
            SignatorName TEXT NOT NULL, SignatorJob TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Letters (
            LetterID INTEGER PRIMARY KEY AUTOINCREMENT,
            LetterNumber TEXT, LetterDate TEXT, SubjectID INTEGER,
            SignatorID INTEGER, LetterBody TEXT, FilePath TEXT,
            CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (SubjectID) REFERENCES Subjects(SubjectID),
            FOREIGN KEY (SignatorID) REFERENCES Signators(SignatorID))""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS LetterPersons (
            LetterPersonID INTEGER PRIMARY KEY AUTOINCREMENT,
            LetterID INTEGER NOT NULL, PersonID INTEGER NOT NULL,
            FOREIGN KEY (LetterID) REFERENCES Letters(LetterID) ON DELETE CASCADE,
            FOREIGN KEY (PersonID) REFERENCES Persons(PersonID))""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Attachments (
            AttachmentID INTEGER PRIMARY KEY AUTOINCREMENT,
            LetterID INTEGER NOT NULL, FileName TEXT NOT NULL,
            FilePath TEXT NOT NULL, AddedAt TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (LetterID) REFERENCES Letters(LetterID) ON DELETE CASCADE)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS Reminders (
            ReminderID INTEGER PRIMARY KEY AUTOINCREMENT,
            ReminderTitle TEXT NOT NULL, ReminderDate TEXT NOT NULL,
            Description TEXT, IsDone INTEGER DEFAULT 0,
            ReminderTime TEXT, CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP)""")
        # افزودن ستون‌های جدید بدون حذف یا تغییر اطلاعات یادآوری‌های قبلی
        _add_column(cursor, "Reminders", "ReminderTime", "TEXT")
        _add_column(cursor, "Reminders", "CreatedAt", "TEXT")
        # زمان اعلام هشدار؛ مانع نمایش چندباره یک یادآوری می‌شود.
        _add_column(cursor, "Reminders", "NotifiedAt", "TEXT")

        # Independent postal sender/receiver directories.
        cursor.execute("""CREATE TABLE IF NOT EXISTS PostalSenders (
            SenderID INTEGER PRIMARY KEY AUTOINCREMENT,
            SenderName TEXT NOT NULL, Organization TEXT, Phone TEXT,
            Address TEXT, Description TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS PostalReceivers (
            ReceiverID INTEGER PRIMARY KEY AUTOINCREMENT,
            ReceiverName TEXT NOT NULL, Organization TEXT, Phone TEXT,
            Address TEXT, Description TEXT)""")

        # Preserve the original PostalLetters table and all its records.
        cursor.execute("""CREATE TABLE IF NOT EXISTS PostalLetters (
            PostalID INTEGER PRIMARY KEY AUTOINCREMENT,
            LetterNumber TEXT, PostalDate TEXT, TrackingCode TEXT,
            ReceiverName TEXT, Description TEXT)""")
        for column_name in ("SenderID", "ReceiverID", "SubjectID", "SignatorID"):
            _add_column(cursor, "PostalLetters", column_name, "INTEGER")

        # وضعیت و زمان‌های گردش مرسوله؛ ستون‌های قدیمی دست‌نخورده می‌مانند.
        _add_column(cursor, "PostalLetters", "PostalStatus", "TEXT DEFAULT 'ثبت‌شده'")
        _add_column(cursor, "PostalLetters", "SentAt", "TEXT")
        _add_column(cursor, "PostalLetters", "DeliveredAt", "TEXT")

        # هر امضا یک رکورد مستقل است تا امضاهای قبلی و اصلاحات احتمالی حفظ شوند.
        # SignatureData تصویر امضا را به‌صورت BLOB نگهداری می‌کند.
        cursor.execute("""CREATE TABLE IF NOT EXISTS PostalSignatures (
            SignatureID INTEGER PRIMARY KEY AUTOINCREMENT,
            PostalID INTEGER NOT NULL,
            PartyType TEXT NOT NULL CHECK (PartyType IN ('sender', 'receiver')),
            SignerName TEXT NOT NULL,
            SignatureMethod TEXT NOT NULL CHECK (
                SignatureMethod IN ('mouse', 'image', 'pad')
            ),
            SignatureData BLOB NOT NULL,
            SignedAt TEXT DEFAULT CURRENT_TIMESTAMP,
            Notes TEXT,
            FOREIGN KEY (PostalID) REFERENCES PostalLetters(PostalID) ON DELETE CASCADE
        )""")

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_postal_tracking ON PostalLetters(TrackingCode)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_postal_signatures_postal ON PostalSignatures(PostalID, PartyType, SignatureID)"
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS AppSettings (
            SettingKey TEXT PRIMARY KEY,
            SettingValue TEXT)""")
        # شمارنده مستقل برای شماره نامه‌های هر سال شمسی
        cursor.execute("""CREATE TABLE IF NOT EXISTS LetterNumberSequences (
            ShamsiYear INTEGER PRIMARY KEY,
            LastNumber INTEGER NOT NULL DEFAULT 0)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS AppUsers (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT NOT NULL UNIQUE,
            FullName TEXT NOT NULL,
            PasswordHash TEXT NOT NULL,
            PasswordSalt TEXT NOT NULL,
            Role TEXT NOT NULL DEFAULT 'کاربر عادی',
            IsActive INTEGER NOT NULL DEFAULT 1,
            Permissions TEXT,
            CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP)""")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print("YASNA DATABASE CREATED SUCCESSFULLY")
    print(DB_PATH)
