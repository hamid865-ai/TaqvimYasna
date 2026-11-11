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


def protect_form_methods(form, user, permission_key, method_names):
    """Add a permission check to each data-changing form action."""
    for method_name in method_names:
        original = getattr(form, method_name, None)
        if original is None or not callable(original):
            continue

        def guarded(*args, _original=original, **kwargs):
            if not can_edit(user, permission_key):
                show_denied(form)
                return None
            return _original(*args, **kwargs)

        setattr(form, method_name, guarded)


def guard_class_methods(form_class, permission_key, method_names):
    """Guard slots at class level so Qt signals cannot bypass the checks."""
    for method_name in method_names:
        original = getattr(form_class, method_name, None)
        if original is None or not callable(original):
            continue

        def guarded(self, *args, _original=original, **kwargs):
            user = getattr(self, "current_user", None)
            if not can_edit(user, permission_key):
                show_denied(self)
                return None
            return _original(self, *args, **kwargs)

        setattr(form_class, method_name, guarded)
