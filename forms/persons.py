
import os
import sqlite3

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView,
    QFileDialog
)

from PyQt5.QtCore import Qt

from database.database import get_connection


class PersonsForm(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("مدیریت اشخاص و مخاطبان")
        self.resize(1050, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        self.selected_person_id = None
        self.template_path = ""

        self.setStyleSheet("""
            QWidget {
                background-color: #F3F5F8;
                font-family: Tahoma;
                font-size: 10pt;
            }

            QLabel {
                color: #142D4E;
            }

            QLineEdit, QTextEdit {
                background-color: white;
                border: 1px solid #DCE2E9;
                border-radius: 6px;
                padding: 8px;
            }

            QPushButton {
                background-color: #142D4E;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 9px 15px;
            }

            QPushButton:hover {
                background-color: #294769;
            }

            QPushButton#SaveButton {
                background-color: #C5A45E;
                color: #142D4E;
                font-weight: bold;
            }

            QPushButton#DeleteButton {
                background-color: #A94442;
            }

            QPushButton#TemplateButton {
                background-color: #285577;
            }

            QTableWidget {
                background-color: white;
                border: 1px solid #DCE2E9;
                gridline-color: #E5E9EF;
                selection-background-color: #D8B66A;
                selection-color: #142D4E;
            }

            QHeaderView::section {
                background-color: #142D4E;
                color: white;
                padding: 9px;
                border: none;
            }
        """)

        self.create_ui()
        self.load_persons()

    # -------------------------------------------------
    # طراحی فرم
    # -------------------------------------------------

    def create_ui(self):

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        title = QLabel("مدیریت اشخاص و مخاطبان")
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )

        main_layout.addWidget(title)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "جستجو بر اساس نام شخص یا سازمان..."
        )

        self.txt_search.textChanged.connect(
            self.search_persons
        )

        main_layout.addWidget(self.txt_search)

        self.table = QTableWidget()
        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels([
            "شناسه",
            "نام شخص",
            "سازمان",
            "شماره تماس",
            "نشانی"
        ])

        self.table.setColumnHidden(0, True)

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.table.itemSelectionChanged.connect(
            self.select_person
        )

        main_layout.addWidget(self.table)

        # اطلاعات شخص

        form_layout = QHBoxLayout()

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("نام و نام خانوادگی")

        self.txt_organization = QLineEdit()
        self.txt_organization.setPlaceholderText("نام سازمان")

        self.txt_phone = QLineEdit()
        self.txt_phone.setPlaceholderText("شماره تماس")

        form_layout.addWidget(self.txt_name)
        form_layout.addWidget(self.txt_organization)
        form_layout.addWidget(self.txt_phone)

        main_layout.addLayout(form_layout)

        self.txt_address = QLineEdit()
        self.txt_address.setPlaceholderText("نشانی")

        main_layout.addWidget(self.txt_address)

        self.txt_description = QTextEdit()
        self.txt_description.setPlaceholderText(
            "توضیحات تکمیلی..."
        )
        self.txt_description.setMaximumHeight(75)

        main_layout.addWidget(self.txt_description)

        # قالب اختصاصی Word

        template_title = QLabel(
            "قالب اختصاصی نامه این شخص"
        )

        template_title.setStyleSheet(
            "font-weight: bold; color: #142D4E;"
        )

        main_layout.addWidget(template_title)

        template_layout = QHBoxLayout()

        self.txt_template = QLineEdit()
        self.txt_template.setReadOnly(True)
        self.txt_template.setPlaceholderText(
            "هنوز قالب Word انتخاب نشده است"
        )

        self.btn_select_template = QPushButton(
            "انتخاب قالب Word"
        )

        self.btn_select_template.setObjectName(
            "TemplateButton"
        )

        self.btn_remove_template = QPushButton(
            "حذف قالب"
        )

        template_layout.addWidget(self.txt_template)
        template_layout.addWidget(self.btn_select_template)
        template_layout.addWidget(self.btn_remove_template)

        main_layout.addLayout(template_layout)

        self.btn_select_template.clicked.connect(
            self.select_template
        )

        self.btn_remove_template.clicked.connect(
            self.remove_template
        )

        # دکمه‌ها

        buttons_layout = QHBoxLayout()

        self.btn_new = QPushButton("شخص جدید")

        self.btn_save = QPushButton("ذخیره اطلاعات")
        self.btn_save.setObjectName("SaveButton")

        self.btn_delete = QPushButton("حذف شخص")
        self.btn_delete.setObjectName("DeleteButton")

        self.btn_clear = QPushButton("پاک کردن فرم")

        self.btn_new.clicked.connect(self.clear_form)
        self.btn_save.clicked.connect(self.save_person)
        self.btn_delete.clicked.connect(self.delete_person)
        self.btn_clear.clicked.connect(self.clear_form)

        buttons_layout.addWidget(self.btn_new)
        buttons_layout.addWidget(self.btn_save)
        buttons_layout.addWidget(self.btn_delete)
        buttons_layout.addWidget(self.btn_clear)

        main_layout.addLayout(buttons_layout)

    # -------------------------------------------------
    # انتخاب قالب Word
    # -------------------------------------------------

    def select_template(self):

        start_directory = ""

        if self.template_path and os.path.isfile(
            self.template_path
        ):
            start_directory = self.template_path

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "انتخاب قالب Word اختصاصی",
            start_directory,
            "Word Files (*.docx *.doc)"
        )

        if not file_path:
            return

        if not os.path.isfile(file_path):

            QMessageBox.warning(
                self,
                "خطا",
                "فایل انتخاب‌شده قابل دسترسی نیست."
            )

            return

        self.template_path = os.path.abspath(file_path)

        self.show_template_name()

    # -------------------------------------------------
    # نمایش نام قالب
    # -------------------------------------------------

    def show_template_name(self):

        if self.template_path:

            self.txt_template.setText(
                os.path.basename(self.template_path)
            )

            self.txt_template.setToolTip(
                self.template_path
            )

        else:

            self.txt_template.clear()

            self.txt_template.setPlaceholderText(
                "هنوز قالب Word انتخاب نشده است"
            )

            self.txt_template.setToolTip("")

    # -------------------------------------------------
    # حذف مسیر قالب
    # -------------------------------------------------

    def remove_template(self):

        self.template_path = ""
        self.show_template_name()

    # -------------------------------------------------
    # بارگذاری اشخاص
    # -------------------------------------------------

    def load_persons(self):

        connection = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT PersonID,
                       PersonName,
                       Organization,
                       Phone,
                       Address
                FROM Persons
                ORDER BY PersonID DESC
            """)

            records = cursor.fetchall()

            self.show_records(records)

        except Exception as e:

            QMessageBox.critical(
                self,
                "خطا در بارگذاری اشخاص",
                str(e)
            )

        finally:

            if connection:
                connection.close()

    # -------------------------------------------------
    # نمایش اطلاعات در جدول
    # -------------------------------------------------

    def show_records(self, records):

        self.table.setRowCount(0)

        for record in records:

            row = self.table.rowCount()
            self.table.insertRow(row)

            for column, value in enumerate(record):

                item = QTableWidgetItem(
                    "" if value is None else str(value)
                )

                item.setTextAlignment(Qt.AlignCenter)

                self.table.setItem(row, column, item)

    # -------------------------------------------------
    # جستجوی اشخاص
    # -------------------------------------------------

    def search_persons(self):

        keyword = self.txt_search.text().strip()

        connection = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT PersonID,
                       PersonName,
                       Organization,
                       Phone,
                       Address
                FROM Persons
                WHERE PersonName LIKE ?
                   OR Organization LIKE ?
                ORDER BY PersonID DESC
            """, (
                "%" + keyword + "%",
                "%" + keyword + "%"
            ))

            records = cursor.fetchall()

            self.show_records(records)

        except Exception as e:

            QMessageBox.critical(
                self,
                "خطا در جستجو",
                str(e)
            )

        finally:

            if connection:
                connection.close()

    # -------------------------------------------------
    # انتخاب شخص
    # -------------------------------------------------

    def select_person(self):

        row = self.table.currentRow()

        if row < 0:
            return

        id_item = self.table.item(row, 0)

        if id_item is None:
            return

        self.selected_person_id = int(id_item.text())

        connection = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT PersonName,
                       Organization,
                       Phone,
                       Address,
                       Description,
                       TemplatePath
                FROM Persons
                WHERE PersonID = ?
            """, (self.selected_person_id,))

            record = cursor.fetchone()

            if not record:
                return

            self.txt_name.setText(record[0] or "")
            self.txt_organization.setText(record[1] or "")
            self.txt_phone.setText(record[2] or "")
            self.txt_address.setText(record[3] or "")

            self.txt_description.setPlainText(
                record[4] or ""
            )

            self.template_path = record[5] or ""

            self.show_template_name()

        except Exception as e:

            QMessageBox.critical(
                self,
                "خطا در دریافت اطلاعات شخص",
                str(e)
            )

        finally:

            if connection:
                connection.close()

    # -------------------------------------------------
    # ذخیره اطلاعات شخص
    # -------------------------------------------------

    def save_person(self):

        name = self.txt_name.text().strip()

        if not name:

            QMessageBox.warning(
                self,
                "توجه",
                "نام شخص را وارد کنید."
            )

            self.txt_name.setFocus()
            return

        data = (
            name,
            self.txt_organization.text().strip(),
            self.txt_phone.text().strip(),
            self.txt_address.text().strip(),
            self.txt_description.toPlainText().strip(),
            self.template_path
        )

        connection = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            if self.selected_person_id is None:

                cursor.execute("""
                    INSERT INTO Persons (
                        PersonName,
                        Organization,
                        Phone,
                        Address,
                        Description,
                        TemplatePath
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, data)

            else:

                cursor.execute("""
                    UPDATE Persons
                    SET
                        PersonName = ?,
                        Organization = ?,
                        Phone = ?,
                        Address = ?,
                        Description = ?,
                        TemplatePath = ?
                    WHERE PersonID = ?
                """, data + (self.selected_person_id,))

            connection.commit()

            self.clear_form()
            self.load_persons()

            QMessageBox.information(
                self,
                "Yasna",
                "اطلاعات شخص با موفقیت ذخیره شد."
            )

        except Exception as e:

            if connection:
                connection.rollback()

            QMessageBox.critical(
                self,
                "خطا در ذخیره اطلاعات",
                str(e)
            )

        finally:

            if connection:
                connection.close()

    # -------------------------------------------------
    # حذف شخص
    # -------------------------------------------------

    def delete_person(self):

        if self.selected_person_id is None:

            QMessageBox.warning(
                self,
                "توجه",
                "ابتدا یک شخص را انتخاب کنید."
            )

            return

        answer = QMessageBox.question(
            self,
            "تأیید حذف",
            "آیا از حذف این شخص اطمینان دارید؟",
            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        connection = None

        try:

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                DELETE FROM Persons
                WHERE PersonID = ?
            """, (self.selected_person_id,))

            connection.commit()

            self.clear_form()
            self.load_persons()

            QMessageBox.information(
                self,
                "Yasna",
                "شخص با موفقیت حذف شد."
            )

        except sqlite3.IntegrityError:

            if connection:
                connection.rollback()

            QMessageBox.warning(
                self,
                "عدم امکان حذف",
                "این شخص به یک یا چند نامه مرتبط است."
            )

        except Exception as e:

            if connection:
                connection.rollback()

            QMessageBox.critical(
                self,
                "خطا در حذف شخص",
                str(e)
            )

        finally:

            if connection:
                connection.close()

    # -------------------------------------------------
    # پاک کردن فرم
    # -------------------------------------------------

    def clear_form(self):

        self.selected_person_id = None
        self.template_path = ""

        self.txt_name.clear()
        self.txt_organization.clear()
        self.txt_phone.clear()
        self.txt_address.clear()
        self.txt_description.clear()

        self.show_template_name()

        self.table.clearSelection()
        self.txt_name.setFocus()
