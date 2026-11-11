
# -*- coding: utf-8 -*-

import os
import csv
import html

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextDocument

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QFileDialog, QHeaderView, QFrame
)

from PyQt5.QtPrintSupport import (
    QPrinter, QPrintDialog, QPrintPreviewDialog
)

try:
    from database.database import get_connection
except Exception:
    get_connection = None


STYLE = """
QWidget {
    font-family: Tahoma;
    font-size: 10pt;
}

QWidget#ReportsRoot {
    background: #F3F5F8;
}

QFrame#TopPanel {
    background: white;
    border: 1px solid #E2E6EC;
    border-radius: 9px;
}

QLabel#PageTitle {
    color: #142D4E;
    font-size: 19px;
    font-weight: bold;
}

QLineEdit {
    background: white;
    border: 1px solid #D9E0E8;
    border-radius: 6px;
    padding: 8px;
}

QPushButton {
    background: #142D4E;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 14px;
}

QPushButton:hover {
    background: #294769;
}

QPushButton#GoldButton {
    background: #C5A45E;
    color: #142D4E;
    font-weight: bold;
}

QPushButton#LightButton {
    background: white;
    color: #142D4E;
    border: 1px solid #D9E0E8;
}

QPushButton#BackButton {
    background: #142D4E;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 14px;
    font-weight: bold;
}

QPushButton#BackButton:hover {
    background: #294769;
}

QTabWidget::pane {
    border: 1px solid #DDE3EA;
    background: white;
    border-radius: 7px;
}

QTabBar::tab {
    background: #E8EDF3;
    color: #142D4E;
    padding: 10px 18px;
    margin-left: 3px;
}

QTabBar::tab:selected {
    background: #142D4E;
    color: white;
}

QTableWidget {
    background: white;
    alternate-background-color: #F7F9FB;
    gridline-color: #E5E9EF;
    border: 1px solid #E0E5EB;
}

QHeaderView::section {
    background: #E9EEF4;
    color: #142D4E;
    padding: 8px;
    border: none;
    font-weight: bold;
}
"""


def make_report_font():

    font = QFont()
    font.setFamily("Tahoma")
    font.setPointSize(9)

    return font


class ReportTab(QWidget):

    def __init__(
        self,
        title,
        headers,
        query,
        date_column=None,
        parent=None
    ):

        super().__init__(parent)

        self.title = title
        self.headers = headers
        self.query = query
        self.date_column = date_column

        self.rows = []
        self._print_document = None

        self.build_ui()

    def build_ui(self):

        root = QVBoxLayout(self)

        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(9)

        filters = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "جست‌وجو در اطلاعات گزارش..."
        )

        self.from_edit = QLineEdit()
        self.from_edit.setPlaceholderText(
            "از تاریخ (مثلاً 1405/01/01)"
        )

        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText(
            "تا تاریخ (مثلاً 1405/12/29)"
        )

        self.from_edit.setFixedWidth(175)
        self.to_edit.setFixedWidth(175)

        self.search_edit.returnPressed.connect(self.refresh)
        self.from_edit.returnPressed.connect(self.refresh)
        self.to_edit.returnPressed.connect(self.refresh)

        refresh_btn = QPushButton("اعمال فیلتر")
        refresh_btn.setObjectName("GoldButton")
        refresh_btn.clicked.connect(self.refresh)

        clear_btn = QPushButton("پاک‌کردن فیلتر")
        clear_btn.setObjectName("LightButton")
        clear_btn.clicked.connect(self.clear_filters)

        filters.addWidget(self.search_edit, 1)

        if self.date_column:
            filters.addWidget(self.from_edit)
            filters.addWidget(self.to_edit)

        filters.addWidget(refresh_btn)
        filters.addWidget(clear_btn)

        root.addLayout(filters)

        self.count_label = QLabel("تعداد رکوردها: ۰")
        self.count_label.setStyleSheet("color:#68778A;")

        root.addWidget(self.count_label)

        self.table = QTableWidget()

        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)

        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.ExtendedSelection
        )

        self.table.verticalHeader().setVisible(False)

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )

        self.table.horizontalHeader().setStretchLastSection(True)

        root.addWidget(self.table, 1)

    def clear_filters(self):

        self.search_edit.clear()
        self.from_edit.clear()
        self.to_edit.clear()

        self.refresh()

    def refresh(self):

        if get_connection is None:

            QMessageBox.critical(
                self,
                "خطای اتصال",
                "تابع اتصال به پایگاه داده پیدا نشد."
            )

            return

        connection = None

        try:

            connection = get_connection()

            cursor = connection.cursor()

            cursor.execute(self.query)

            raw_rows = cursor.fetchall()

            search = self.search_edit.text().strip().casefold()

            date_from = (
                self.from_edit.text()
                .strip()
                .replace("-", "/")
            )

            date_to = (
                self.to_edit.text()
                .strip()
                .replace("-", "/")
            )

            filtered = []

            date_index = None

            if self.date_column:

                try:
                    date_index = self.headers.index(
                        self.date_column
                    )
                except ValueError:
                    date_index = None

            for row in raw_rows:

                values = [
                    "" if value is None else str(value)
                    for value in row
                ]

                if search:

                    if search not in " | ".join(values).casefold():
                        continue

                if date_index is not None:

                    normalized = (
                        values[date_index]
                        .strip()[:10]
                        .replace("-", "/")
                    )

                    if date_from and normalized:
                        if normalized < date_from:
                            continue

                    if date_to and normalized:
                        if normalized > date_to:
                            continue

                filtered.append(values)

            self.rows = filtered

            self.table.setRowCount(len(filtered))

            for r, row in enumerate(filtered):

                for c, value in enumerate(row):

                    item = QTableWidgetItem(value)

                    item.setTextAlignment(Qt.AlignCenter)

                    self.table.setItem(r, c, item)

            self.count_label.setText(
                "تعداد رکوردها: {:,}".format(len(filtered))
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "خطا در گزارش‌گیری",
                str(exc)
            )

        finally:

            if connection is not None:

                try:
                    connection.close()
                except Exception:
                    pass

    def export_csv(self):

        if not self.rows:

            QMessageBox.information(
                self,
                "گزارش خالی",
                "ابتدا گزارش را به‌روزرسانی کنید."
            )

            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره خروجی Excel/CSV",
            self.title + ".csv",
            "CSV UTF-8 (*.csv)"
        )

        if not path:
            return

        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as file:

                writer = csv.writer(file)

                writer.writerow(self.headers)
                writer.writerows(self.rows)

            QMessageBox.information(
                self,
                "ذخیره شد",
                "خروجی با موفقیت ذخیره شد.\n"
                "این فایل با Microsoft Excel باز می‌شود."
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "خطا",
                str(exc)
            )

    def export_xlsx(self):

        if not self.rows:

            QMessageBox.information(
                self,
                "گزارش خالی",
                "ابتدا گزارش را به‌روزرسانی کنید."
            )

            return

        try:

            import openpyxl

            from openpyxl.styles import (
                Font,
                PatternFill,
                Alignment
            )

            from openpyxl.utils import get_column_letter

        except ImportError:

            QMessageBox.warning(
                self,
                "نیاز به نصب کتابخانه",
                "برای خروجی مستقیم Excel، "
                "کتابخانه openpyxl لازم است.\n\n"
                "در CMD این دستور را اجرا کن:\n"
                "py -m pip install openpyxl\n\n"
                "تا آن زمان می‌توانی از خروجی CSV استفاده کنی."
            )

            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره فایل Excel",
            self.title + ".xlsx",
            "Excel (*.xlsx)"
        )

        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:

            workbook = openpyxl.Workbook()

            sheet = workbook.active
            sheet.title = "گزارش"

            sheet.sheet_view.rightToLeft = True

            sheet.append(self.headers)

            for row in self.rows:
                sheet.append(row)

            for cell in sheet[1]:

                cell.font = Font(
                    name="Tahoma",
                    bold=True,
                    color="FFFFFF"
                )

                cell.fill = PatternFill(
                    "solid",
                    fgColor="142D4E"
                )

                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center"
                )

            for row in sheet.iter_rows(min_row=2):

                for cell in row:

                    cell.font = Font(
                        name="Tahoma",
                        size=10
                    )

                    cell.alignment = Alignment(
                        horizontal="center",
                        vertical="center"
                    )

            for col in sheet.columns:

                max_length = max(
                    len(str(cell.value or ""))
                    for cell in col
                )

                sheet.column_dimensions[
                    get_column_letter(col[0].column)
                ].width = min(
                    max(max_length + 3, 14),
                    42
                )

            sheet.freeze_panes = "A2"

            workbook.save(path)

            QMessageBox.information(
                self,
                "ذخیره شد",
                "فایل Excel با موفقیت ساخته شد."
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "خطا در ساخت Excel",
                str(exc)
            )

    # اصلاح‌شده: ساخت HTML بدون format روی CSS

    def _html_report(self):

        head = "".join(
            "<th>{}</th>".format(
                html.escape(str(h))
            )
            for h in self.headers
        )

        body = []

        for row in self.rows:

            cells = "".join(
                "<td>{}</td>".format(
                    html.escape(str(v))
                )
                for v in row
            )

            body.append("<tr>{}</tr>".format(cells))

        report_html = """
        <html>
        <head>
        <meta charset="utf-8">

        <style>

        body {
            font-family: Tahoma;
            direction: rtl;
        }

        h2 {
            text-align: center;
            color: #142D4E;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 9pt;
        }

        th {
            background: #142D4E;
            color: white;
            padding: 7px;
        }

        td {
            border: 1px solid #bbb;
            padding: 6px;
            text-align: center;
        }

        tr:nth-child(even) {
            background: #f1f4f7;
        }

        </style>

        </head>

        <body>

        <h2>__REPORT_TITLE__</h2>

        <p>تعداد رکوردها: __REPORT_COUNT__</p>

        <table>

        <thead>
        <tr>__REPORT_HEADERS__</tr>
        </thead>

        <tbody>
        __REPORT_ROWS__
        </tbody>

        </table>

        </body>
        </html>
        """

        report_html = report_html.replace(
            "__REPORT_TITLE__",
            html.escape(self.title)
        )

        report_html = report_html.replace(
            "__REPORT_COUNT__",
            str(len(self.rows))
        )

        report_html = report_html.replace(
            "__REPORT_HEADERS__",
            head
        )

        report_html = report_html.replace(
            "__REPORT_ROWS__",
            "".join(body)
        )

        return report_html

    def _create_document(self):

        document = QTextDocument(self)

        document.setDefaultFont(make_report_font())

        document.setHtml(self._html_report())

        return document

    def _paint_preview(self, printer):

        try:

            if self._print_document is not None:

                self._print_document.print_(printer)

        except Exception as exc:

            QMessageBox.critical(
                self,
                "خطا در پیش‌نمایش چاپ",
                str(exc)
            )

    def print_report(self, preview=False):

        if not self.rows:

            QMessageBox.information(
                self,
                "گزارش خالی",
                "ابتدا گزارش را به‌روزرسانی کنید."
            )

            return

        try:

            printer = QPrinter(QPrinter.HighResolution)

            printer.setOrientation(QPrinter.Landscape)

            self._print_document = self._create_document()

            if preview:

                dialog = QPrintPreviewDialog(
                    printer,
                    self
                )

                dialog.paintRequested.connect(
                    self._paint_preview
                )

                dialog.exec_()

            else:

                dialog = QPrintDialog(
                    printer,
                    self
                )

                if dialog.exec_() == QPrintDialog.Accepted:

                    self._print_document.print_(printer)

        except Exception as exc:

            QMessageBox.critical(
                self,
                "خطا در چاپ گزارش",
                str(exc)
            )

        finally:

            self._print_document = None

    def save_pdf(self):

        if not self.rows:

            QMessageBox.information(
                self,
                "گزارش خالی",
                "ابتدا گزارش را به‌روزرسانی کنید."
            )

            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره گزارش PDF",
            self.title + ".pdf",
            "PDF (*.pdf)"
        )

        if not path:
            return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        try:

            printer = QPrinter(
                QPrinter.HighResolution
            )

            printer.setOutputFormat(
                QPrinter.PdfFormat
            )

            printer.setOutputFileName(path)

            printer.setOrientation(
                QPrinter.Landscape
            )

            document = self._create_document()

            document.print_(printer)

            if (
                not os.path.isfile(path)
                or os.path.getsize(path) == 0
            ):

                raise RuntimeError(
                    "فایل PDF ساخته نشد یا خالی است."
                )

            QMessageBox.information(
                self,
                "ذخیره شد",
                "گزارش PDF با موفقیت ساخته شد."
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "خطا در ساخت PDF",
                str(exc)
            )


class ReportsForm(QWidget):

    def __init__(self, parent=None, on_back=None):

        super().__init__(parent)

        self.on_back = on_back

        self.setObjectName("ReportsRoot")

        self.setLayoutDirection(Qt.RightToLeft)

        self.setStyleSheet(STYLE)

        self.setWindowTitle("Yasna | گزارش‌گیری")

        self.build_ui()

    def build_ui(self):

        root = QVBoxLayout(self)

        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(12)

        top = QFrame()

        top.setObjectName("TopPanel")

        top_layout = QHBoxLayout(top)

        top_layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("مرکز گزارش‌گیری Yasna")

        title.setObjectName("PageTitle")

        back_btn = QPushButton("بازگشت به داشبورد")

        back_btn.setObjectName("BackButton")

        back_btn.clicked.connect(self.go_back)

        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(back_btn)

        root.addWidget(top)

        self.tabs = QTabWidget()

        # گزارش نامه‌های اداری

        self.letters_tab = ReportTab(
            "گزارش نامه‌های اداری",

            [
                "شناسه",
                "شماره نامه",
                "تاریخ نامه",
                "موضوع",
                "امضاکننده",
                "گیرندگان",
                "مسیر فایل"
            ],

            """
            SELECT
                l.LetterID,
                l.LetterNumber,
                l.LetterDate,
                COALESCE(s.SubjectName,''),
                COALESCE(g.SignatorName,''),
                COALESCE(GROUP_CONCAT(DISTINCT p.PersonName),''),
                COALESCE(l.FilePath,'')

            FROM Letters l

            LEFT JOIN Subjects s
                ON s.SubjectID=l.SubjectID

            LEFT JOIN Signators g
                ON g.SignatorID=l.SignatorID

            LEFT JOIN LetterPersons lp
                ON lp.LetterID=l.LetterID

            LEFT JOIN Persons p
                ON p.PersonID=lp.PersonID

            GROUP BY l.LetterID

            ORDER BY l.LetterID DESC
            """,

            date_column="تاریخ نامه"
        )

        # گزارش مرسوله‌های پستی

        self.postal_tab = ReportTab(
            "گزارش مرسوله‌های پستی",

            [
                "شناسه",
                "شماره نامه",
                "تاریخ ثبت",
                "کد رهگیری",
                "فرستنده",
                "گیرنده",
                "موضوع",
                "امضاکننده",
                "وضعیت",
                "زمان ارسال",
                "زمان تحویل"
            ],

            """
            SELECT
                p.PostalID,
                COALESCE(p.LetterNumber,''),
                COALESCE(p.PostalDate,''),
                COALESCE(p.TrackingCode,''),
                COALESCE(s.SenderName,''),
                COALESCE(r.ReceiverName,p.ReceiverName,''),
                COALESCE(sb.SubjectName,''),
                COALESCE(g.SignatorName,''),
                COALESCE(p.PostalStatus,'ثبت‌شده'),
                COALESCE(p.SentAt,''),
                COALESCE(p.DeliveredAt,'')

            FROM PostalLetters p

            LEFT JOIN PostalSenders s
                ON s.SenderID=p.SenderID

            LEFT JOIN PostalReceivers r
                ON r.ReceiverID=p.ReceiverID

            LEFT JOIN Subjects sb
                ON sb.SubjectID=p.SubjectID

            LEFT JOIN Signators g
                ON g.SignatorID=p.SignatorID

            ORDER BY p.PostalID DESC
            """,

            date_column="تاریخ ثبت"
        )

        # گزارش امضاها

        self.signatures_tab = ReportTab(
            "گزارش امضاها",

            [
                "شناسه امضا",
                "شناسه مرسوله",
                "شماره نامه",
                "نوع امضا",
                "نام امضاکننده",
                "روش ثبت",
                "تاریخ و ساعت امضا",
                "توضیحات"
            ],

            """
            SELECT
                sg.SignatureID,
                sg.PostalID,
                COALESCE(p.LetterNumber,''),

                CASE sg.PartyType
                    WHEN 'sender' THEN 'فرستنده'
                    WHEN 'receiver' THEN 'گیرنده'
                    ELSE sg.PartyType
                END,

                sg.SignerName,

                CASE sg.SignatureMethod
                    WHEN 'mouse' THEN 'ترسیم با ماوس'
                    WHEN 'image' THEN 'تصویر'
                    WHEN 'pad' THEN 'قلم نوری'
                    ELSE sg.SignatureMethod
                END,

                COALESCE(sg.SignedAt,''),
                COALESCE(sg.Notes,'')

            FROM PostalSignatures sg

            LEFT JOIN PostalLetters p
                ON p.PostalID=sg.PostalID

            ORDER BY sg.SignatureID DESC
            """,

            date_column="تاریخ و ساعت امضا"
        )

        self.tabs.addTab(
            self.letters_tab,
            "نامه‌های اداری"
        )

        self.tabs.addTab(
            self.postal_tab,
            "مرسوله‌های پستی"
        )

        self.tabs.addTab(
            self.signatures_tab,
            "امضاها"
        )

        root.addWidget(self.tabs, 1)

        # دکمه‌های عملیات

        actions = QHBoxLayout()

        actions.addStretch()

        preview_btn = QPushButton("پیش‌نمایش چاپ")
        preview_btn.setObjectName("LightButton")

        print_btn = QPushButton("چاپ گزارش")

        excel_btn = QPushButton("خروجی Excel")

        csv_btn = QPushButton("خروجی CSV")

        pdf_btn = QPushButton("خروجی PDF")
        pdf_btn.setObjectName("GoldButton")

        preview_btn.clicked.connect(
            lambda: self.current_tab().print_report(True)
        )

        print_btn.clicked.connect(
            lambda: self.current_tab().print_report(False)
        )

        excel_btn.clicked.connect(
            lambda: self.current_tab().export_xlsx()
        )

        csv_btn.clicked.connect(
            lambda: self.current_tab().export_csv()
        )

        pdf_btn.clicked.connect(
            lambda: self.current_tab().save_pdf()
        )

        for button in (
            preview_btn,
            print_btn,
            excel_btn,
            csv_btn,
            pdf_btn
        ):

            actions.addWidget(button)

        root.addLayout(actions)

        self.refresh_all()

    def current_tab(self):

        return self.tabs.currentWidget()

    def refresh_all(self):

        for tab in (
            self.letters_tab,
            self.postal_tab,
            self.signatures_tab
        ):

            tab.refresh()

    def go_back(self):

        if callable(self.on_back):

            self.on_back()

        else:

            self.hide()
