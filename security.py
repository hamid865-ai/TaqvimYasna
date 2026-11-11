# -*- coding: utf-8 -*-
import json
from database.database import get_connection
from PyQt5.QtWidgets import (
    QWidget, QLineEdit, QTextEdit, QComboBox, QTimeEdit,
    QDateEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QRadioButton, QTableWidget, QAbstractItemView, QPushButton,
    QMessageBox
)


def refresh_user(user):
    """Refresh role and permissions from the database before access checks."""
    if not user:
        return False
    user_id = user.get("UserID")
    if not user_id:
        # Fail closed: an authenticated session must always map to a DB user.
        user["IsActive"] = False
        return False

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT Username, FullName, Role, IsActive, Permissions "
            "FROM AppUsers WHERE UserID=?",
            (user_id,)
        ).fetchone()
    except Exception:
        return False
    finally:
        conn.close()

    if not row or not row[3]:
        user["IsActive"] = False
        return False

    try:
        permissions = json.loads(row[4] or "{}")
    except Exception:
        permissions = {}

    user.update({
        "Username": row[0],
        "FullName": row[1],
        "Role": row[2],
        "IsActive": bool(row[3]),
        "Permissions": permissions
    })
    return True


def has_permission(user, key):
    if not refresh_user(user):
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
        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText() or ""
            if "جستجو" not in placeholder and "فیلتر" not in placeholder:
                widget.setReadOnly(True)
        elif isinstance(widget, QTextEdit):
            widget.setReadOnly(True)
        elif isinstance(widget, QTableWidget):
            widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        if isinstance(widget, QPushButton):
            label = (widget.text() or "").strip()
            if any(word in label for word in (
                "ذخیره", "ثبت", "حذف", "ویرایش", "جدید",
                "افزودن", "ارسال", "تحویل", "انجام شد",
                "پاک کردن", "امضا", "انتخاب فایل", "ایجاد"
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
            # QPushButton.clicked may supply a boolean to a slot that
            # originally accepted no arguments.
            code = getattr(_original, "__code__", None)
            if (
                args and isinstance(args[0], bool)
                and code is not None and code.co_argcount == 1
            ):
                args = args[1:]
            return _original(self, *args, **kwargs)

        setattr(form_class, method_name, guarded)
