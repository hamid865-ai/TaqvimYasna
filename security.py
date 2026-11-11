# -*- coding: utf-8 -*-
import json
from PyQt5.QtWidgets import (
    QWidget, QLineEdit, QTextEdit, QComboBox, QTimeEdit,
    QDateEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QRadioButton, QTableWidget, QAbstractItemView, QPushButton,
    QMessageBox
)


def has_permission(user, key):
    if not user:
        return False
    if user.get("Role") == "مدیر سیستم":
        return True
    try:
        permissions = user.get("Permissions") or {}
        if isinstance(permissions, str):
            permissions = json.loads(permissions)
        return bool(permissions.get(key, False))
    except Exception:
        return False


def is_read_only(user):
    return bool(user) and user.get("Role") == "فقط مشاهده"


def can_edit(user, key):
    return has_permission(user, key) and not is_read_only(user)


def show_denied(parent, message="شما مجوز انجام این عملیات را ندارید."):
    QMessageBox.warning(parent, "عدم دسترسی", message)


def apply_read_only(form, user, permission_key):
    """Disable editing controls for users whose role is read-only."""
    if can_edit(user, permission_key):
        return

    for widget in form.findChildren(QWidget):
        if isinstance(widget, (QLineEdit, QTextEdit)):
            widget.setReadOnly(True)
        elif isinstance(widget, (QComboBox, QTimeEdit, QDateEdit,
                                 QSpinBox, QDoubleSpinBox, QCheckBox,
                                 QRadioButton)):
            widget.setEnabled(False)
        elif isinstance(widget, QTableWidget):
            widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        if isinstance(widget, QPushButton):
            label = (widget.text() or "").strip()
            if any(word in label for word in (
                "ذخیره", "ثبت", "حذف", "ویرایش", "جدید",
                "افزودن", "ارسال", "تحویل", "انجام شد",
                "پاک کردن", "امضا", "انتخاب فایل"
            )):
                widget.setEnabled(False)
