import sqlite3
import os
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import ttkbootstrap as tb
from ttkbootstrap.widgets import DateEntry
from custom_widgets import CustomDatePicker
from ttkbootstrap.style import Style

from pdf_generator import generate_weekly_schedule

AUSTRIAN_HOLIDAYS = [
    "رأس السنة", "عيد الغطاس", "الجمعة العظيمة", "عيد الفصح", "عيد العمال",
    "عيد الصعود", "عيد الجسد", "العيد الوطني", "عيد جميع القديسين",
    "عيد الميلاد", "يوم القديس ستيفان", "عطلة استثنائية"
]

def setup_database():
    with sqlite3.connect("medicaltrans.db") as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, available_from TEXT, material_from_lab TEXT,
            address TEXT, target_lab TEXT, billing TEXT, issues TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, address TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, address TEXT, phone TEXT,
            car_received_date TEXT,
            employment_end_date TEXT,
            issues TEXT,
            contract_type TEXT)""")
        # تعديل جدول السائقين لإضافة حقول السيارة (إن لم تكن موجودة)
        try:
            c.execute("ALTER TABLE drivers ADD COLUMN assigned_plate TEXT")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        try:
            c.execute("ALTER TABLE drivers ADD COLUMN plate_from TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE drivers ADD COLUMN plate_to TEXT")
        except sqlite3.OperationalError:
            pass

        c.execute("""CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, description TEXT,
            start_date TEXT, end_date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS driver_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_name TEXT, task_date TEXT,
            doctor_name TEXT, lab_name TEXT,
            time_window TEXT, materials TEXT, doctor_address TEXT)""")
        # ✅ جدول أرشفة علاقات السائق بالسيارة
        c.execute("""CREATE TABLE IF NOT EXISTS driver_car_assignments_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER,
            driver_name TEXT,
            assigned_plate TEXT,
            plate_from TEXT,
            plate_to TEXT,
            archived_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS car_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT,
            autobahnpickerl_from TEXT, autobahnpickerl_to TEXT,
            yearly_pickerl_until TEXT, notes TEXT
        )""")
        # ✅ جدول الأرشيف للسيارات
        c.execute("""CREATE TABLE IF NOT EXISTS archived_car_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT,
            autobahnpickerl_from TEXT,
            autobahnpickerl_to TEXT,
            yearly_pickerl_until TEXT,
            notes TEXT
        )""")
        # ✅ جدول المواعيد المرتبطة بالسيارات
        c.execute("""CREATE TABLE IF NOT EXISTS car_appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT,
            appointment_type TEXT,
            appointment_date TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS vacations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_type TEXT, name TEXT,
            start_date TEXT, end_date TEXT)""")

        c.execute("""CREATE TABLE IF NOT EXISTS archived_car_appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT,
            appointment_type TEXT,
            appointment_date TEXT
        )""")

        c.execute("""
            CREATE TABLE IF NOT EXISTS fuel_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT,
                date TEXT,
                amount REAL
            )
        """)
    conn.commit()

class MedicalTransApp(tb.Window):
    def __init__(self):
        super().__init__(themename="lumen")  # الوضع الافتراضي

        self.title("Medicaltrans GmbH – إدارة النقل الطبي")
        self.geometry("1200x700")
        self.current_theme = "lumen"
    
        self._setup_custom_styles()
        self._build_header()
        self._build_layout()
        self._build_sidebar_navigation()
        self._configure_styles()
        self.tabs["main"].pack(fill="both", expand=True)
        self.check_warnings()
        self._check_alerts()
        self.archived_calendar_window = None
        self.archived_vacations_window = None
        self.archived_drivers_window = None
        self._check_appointments()

    def _get_filtered_driver_tasks(self, driver_name, date, cursor):
        cursor.execute("""
            SELECT dt.doctor_name, dt.lab_name, dt.time_window, dt.materials, dt.doctor_address
            FROM driver_tasks dt
            INNER JOIN drivers d ON dt.driver_name = d.name
            WHERE dt.driver_name = ? 
              AND dt.task_date = ?
              AND (d.employment_end_date IS NULL 
                   OR d.employment_end_date = '' 
                   OR date(d.employment_end_date) >= date('now'))
        """, (driver_name, date))
        return [row for row in cursor.fetchall() if not self.is_on_vacation(row[0], date, "طبيب")]

    def _setup_custom_styles(self):
        style = self.style
        
        # تخصيص الأنماط للوضعين
        self.style.configure("custom.TButton", 
                           font=("Segoe UI", 10),
                           padding=8,
                           relief="flat")
                           
        self.style.configure("custom.dark.TFrame", 
                           background="#2d2d2d",
                           bordercolor="#404040",
                           borderwidth=1)
                           
        self.style.configure("custom.light.TFrame", 
                           background="#f5f5f5",
                           bordercolor="#e0e0e0",
                           borderwidth=1)

    def _toggle_theme(self):
        # تبديل بين الوضعين
        if self.current_theme == "lumen":
            self.style.theme_use("darkly")
            self.current_theme = "darkly"
            self.toggle_btn.configure(text="الوضع الفاتح")
        else:
            self.style.theme_use("lumen")
            self.current_theme = "lumen"
            self.toggle_btn.configure(text="الوضع الداكن")
        
        # تحديث الألوان الديناميكية
        self._update_dynamic_colors()

    def _update_dynamic_colors(self):
        # تحديث العناصر التي تحتاج ألوانًا مخصصة
        theme_colors = self.style.colors
        bg = theme_colors.bg
        fg = theme_colors.fg
        
        # تحديث الهيدر
        self.header_frame.configure(style=f"custom.{self.current_theme}.TFrame")
        self.title_label.configure(foreground=fg)
        
        # تحديث معاينة الـ A4
        self._draw_a4_preview([e.get() for e in self.main_entries])

    def _build_header(self):
        self.header_frame = tb.Frame(self, style=f"custom.{self.current_theme}.TFrame")
        self.header_frame.pack(fill="x", pady=(0, 10))

        # الحاوية اليسرى: تحتوي العنوان والأزرار
        title_container = tb.Frame(self.header_frame)
        title_container.pack(side="left", padx=20, pady=10)

        self.title_label = tb.Label(
            title_container,
            text="medicaltrans GmbH – إدارة النقل الطبي",
            font=("Segoe UI", 16, "bold"),
            anchor="w"
        )
        self.title_label.pack(side="left")

        # ⚠️ زر التحذير
        self.alert_icon = tb.Label(
            title_container,
            text=" ⚠️ ",
            font=("Segoe UI", 16, "bold"),
            foreground="orange",
            cursor="hand2"
        )
        self.alert_icon.pack(side="left", padx=5)
        self.alert_icon.bind("<Button-1>", lambda e: self.show_warning_window())
        self.alert_icon.pack_forget()

        # 📌 زر المواعيد القادمة
        self.pin_icon = tb.Label(
            title_container,
            text=" 📌 ",
            font=("Segoe UI", 16, "bold"),
            foreground="red",
            cursor="hand2"
        )
        self.pin_icon.pack(side="left", padx=5)
        self.pin_icon.bind("<Button-1>", lambda e: self.show_upcoming_appointments_popup())

        # الحاوية اليمنى: تحتوي التاريخ وزر الوضع
        right_container = tb.Frame(self.header_frame)
        right_container.pack(side="right", padx=20, pady=10)

        # 📅 التاريخ الحالي
        today_str = datetime.today().strftime("%Y-%m-%d")
        self.date_label = tb.Label(
            right_container,
            text=f"📅 {today_str}",
            font=("Segoe UI", 10),
            foreground="gray"
        )
        self.date_label.pack(side="right", padx=(0, 10))

        # زر تغيير الوضع
        self.toggle_btn = tb.Button(
            right_container,
            text="الوضع الداكن",
            style="custom.TButton",
            command=self._toggle_theme
        )
        self.toggle_btn.pack(side="right", padx=(0, 10))

    def _build_layout(self):
        main_frame = tb.Frame(self)
        main_frame.pack(fill="both", expand=True)

        self.sidebar = tb.Frame(main_frame, width=200, style=f"custom.{self.current_theme}.TFrame")
        self.sidebar.pack(side="left", fill="y", padx=5, pady=5)

        self.content_frame = tb.Frame(main_frame)
        self.content_frame.pack(side="right", fill="both", expand=True)

        self.tabs = {
            "main": self._build_main_tab(),
            "doctors": self._build_doctor_tab(),
            "labs": self._build_lab_tab(),
            "drivers": self._build_driver_tab(),
            "calendar": self._build_calendar_tab(),
            "cars": self._build_car_tab(),
        }

    def _build_sidebar_navigation(self):
        nav_buttons = [
            ("📋 المهام الأسبوعية", "main"),
            ("🧑‍⚕️ الأطباء", "doctors"),
            ("🧪 المخابر", "labs"),
            ("🚗 السائقين", "drivers"),
            ("📅 التقويم", "calendar"),
            ("🚙 السيارات", "cars")
        ]

        for text, tab_key in nav_buttons:
            btn = tb.Button(
                self.sidebar,
                text=text,
                style="custom.TButton",
                width=20,
                command=lambda tk=tab_key: self._show_tab(tk)
            )
            btn.pack(pady=5, padx=5, fill="x")

    def _show_tab(self, tab_key):
        # إعادة تعيين جميع حقول البحث قبل التبديل
        for widget in self.content_frame.winfo_children():
            if isinstance(widget, tb.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tb.Entry) and child.get() == "🔍 بحث":
                        child.delete(0, tk.END)
                        child.insert(0, "🔍 بحث")
                        child.configure(foreground="#808080")
    
        # عرض التبويب المحدد
        for tab in self.tabs.values():
            tab.pack_forget()
        self.tabs[tab_key].pack(fill="both", expand=True)

    def _configure_styles(self):
        # تكوين الأنماط الديناميكية
        theme_colors = self.style.colors
        self.style.configure("TEntry", 
                           font=("Segoe UI", 10),
                           padding=6,
                           relief="flat",
                           bordercolor=theme_colors.border,
                           borderwidth=1)
                           
        self.style.configure("Treeview",
                           rowheight=28,
                           borderwidth=0,
                           relief="flat",
                           background=theme_colors.inputbg,
                           fieldbackground=theme_colors.inputbg)
                           
        self.style.map("Treeview",
                     background=[("selected", theme_colors.primary)],
                     foreground=[("selected", theme_colors.selectfg)])

    def _draw_a4_preview(self, values):
        theme_colors = self.style.colors
        self.preview_canvas.delete("all")
        
        # خلفية ديناميكية
        bg_color = theme_colors.bg if self.current_theme == "lumen" else "#2d2d2d"
        text_color = theme_colors.fg
        
        self.preview_canvas.create_rectangle(0, 0, 595, 842, fill=bg_color, outline=text_color)
        
        self.preview_canvas.create_text(
            297, 40,
            text="جدول مهمة يومية – معاينة",
            font=("Arial", 14, "bold"),
            fill=text_color
        )

    def _edit_vacations(self):
        columns = ("id", "person_type", "name", "start", "end")
        labels = ["", "النوع", "الاسم", "من", "إلى"]
        window, tree, bottom_btn_frame = self.build_centered_popup("📝 تعديل الإجازات", 900, 500, columns, labels)

        def load_vacations():
            tree.delete(*tree.get_children())
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT id, person_type, name, start_date, end_date
                    FROM vacations
                    WHERE end_date >= date('now')
                    ORDER BY start_date ASC
                """)
                for i, row in enumerate(c.fetchall()):
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    tree.insert("", "end", values=row, tags=(tag,))
            self.apply_alternate_row_colors(tree)
            self._refresh_driver_comboboxes()

        def edit_selected():
            selected = tree.selection()
            if not selected:
                self.show_info_popup("تنبيه", "يرجى اختيار إجازة لتعديلها.")
                return

            values = tree.item(selected[0])["values"]
            if len(values) < 5:
                self.show_info_popup("خطأ", "تعذر قراءة بيانات الإجازة المحددة.")
                return

            vac_id, person_type, name, start_old, end_old = values

            edit_win = self.build_centered_popup("✏️ تعديل الإجازة", 450, 300)

            main_frame = tb.Frame(edit_win)
            main_frame.pack(fill="both", expand=True, padx=15, pady=15)

            # النوع (Label ثابت)
            ttk.Label(main_frame, text="النوع:").grid(row=0, column=0, sticky="w", pady=5)
            ttk.Label(main_frame, text=person_type).grid(row=0, column=1, sticky="w", pady=5, padx=5)

            # الاسم (Label ثابت)
            ttk.Label(main_frame, text="الاسم:").grid(row=1, column=0, sticky="w", pady=5)
            ttk.Label(main_frame, text=name).grid(row=1, column=1, sticky="w", pady=5, padx=5)

            # من تاريخ
            ttk.Label(main_frame, text="من تاريخ (YYYY-MM-DD):").grid(row=2, column=0, sticky="w", pady=5)
            self.edit_vac_start_picker = CustomDatePicker(main_frame)
            self.edit_vac_start_picker.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
            self.edit_vac_start_picker.set(start_old)
            self.edit_vac_start_picker.entry.configure(justify="left")

            # إلى تاريخ
            ttk.Label(main_frame, text="إلى تاريخ (YYYY-MM-DD):").grid(row=3, column=0, sticky="w", pady=5)
            self.edit_vac_end_picker = CustomDatePicker(main_frame)
            self.edit_vac_end_picker.grid(row=3, column=1, sticky="ew", pady=5, padx=5)
            self.edit_vac_end_picker.set(end_old)
            self.edit_vac_end_picker.entry.configure(justify="left")

            def save_vacation_edit_changes():
                new_start = self.edit_vac_start_picker.get().strip()
                new_end = self.edit_vac_end_picker.get().strip()

                if not new_start or not new_end:
                    self.show_info_popup("تنبيه", "يرجى ملء كافة الحقول.")
                    return

                if not self.validate_date_range(new_start, new_end, context="الإجازة"):
                    return

                if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حفظ التعديلات على الإجازة؟"):
                    return

                with sqlite3.connect("medicaltrans.db") as conn:
                    c = conn.cursor()
                    c.execute("""
                        UPDATE vacations SET start_date = ?, end_date = ?
                        WHERE id = ?
                    """, (new_start, new_end, vac_id))
                    conn.commit()

                load_vacations()

                self._load_vacations_inline()  # تحديث الجدول الرئيسي للإجازات الحالية
                
                edit_win.destroy()
                self.show_info_popup("تم", "✅ تم تعديل الإجازة بنجاح.")

            btn_frame = tb.Frame(main_frame)
            btn_frame.grid(row=4, column=0, columnspan=2, pady=15, sticky="ew")

            ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_vacation_edit_changes).pack(pady=5, ipadx=20, fill="x")
            main_frame.columnconfigure(1, weight=1)

        def delete_selected():
            selected = tree.selection()
            if not selected:
                self.show_info_popup("تنبيه", "يرجى اختيار إجازة لحذفها.")
                return
            if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حذف الإجازة المحددة؟"):
                return
            vac_id = tree.item(selected[0])["values"][0]
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("DELETE FROM vacations WHERE id = ?", (vac_id,))
                conn.commit()
            load_vacations()

            self._load_vacations_inline()

            self.show_info_popup("تم", "✅ تم حذف الإجازة بنجاح.")

        # ← بعد تعريف الدوال أعلاه، نضيف الأزرار:
        ttk.Button(bottom_btn_frame, text="✏️ تعديل المحدد", style="Green.TButton",
                    command=lambda: edit_selected()).pack(side="left", padx=5, ipadx=10)

        load_vacations()

    def _export_week_schedule(self):
        driver_name = self.main_entries[2].get().strip()
        if not driver_name:
            self.show_info_popup("تنبيه", "يرجى إدخال اسم السائق.")
            return

        start_date = datetime.today().strftime("%Y-%m-%d")
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        weekly_entries = {}

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()

            for i in range(5):  # الأيام من الإثنين إلى الجمعة
                current_date = (start_date_obj + timedelta(days=i)).strftime("%Y-%m-%d")

                # تجاهل اليوم إذا كان عطلة أو إجازة للسائق أو حدث تقويم
                if self.is_on_vacation(driver_name, current_date, "سائق") or self.is_calendar_event(current_date):
                    continue

                rows = self._get_filtered_driver_tasks(driver_name, current_date, c)

                if not rows:
                    continue

                daily_tasks = [
                    [f"{r[0]} / {r[1]}", r[2], r[3], r[4]] for r in rows
                ]

                weekly_entries[i] = daily_tasks

            conn.close()

            filename = f"{driver_name}_schedule_{start_date}.pdf".replace(" ", "_")
            generate_weekly_schedule(driver_name, start_date, weekly_entries, filename)

            self.show_info_popup("تم", f"✅ تم توليد الملف بنجاح:\n{filename}")

        except Exception as e:
            self.show_info_popup("خطأ", f"حدث خطأ أثناء التصدير:\n{e}")

    def is_on_vacation(self, name, date, person_type):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT 1 FROM vacations
                WHERE name = ? AND person_type = ? AND date(?) BETWEEN start_date AND end_date
            """, (name, person_type, date))
            return c.fetchone() is not None

    def is_calendar_event(self, date):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT 1 FROM calendar_events
                WHERE date(?) BETWEEN start_date AND end_date
            """, (date,))
            return c.fetchone() is not None

    def show_info_popup(self, title, message, parent=None):
        win_width = 700 if title == "معلومة" else 500
        win = self.build_centered_popup(title, win_width, 220)
        if parent:
            win.transient(parent)
            win.lift(parent)

        frame = tb.Frame(win)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(frame, text=message, font=("Segoe UI", 12)).pack(pady=10)

        ttk.Button(
            frame, text="موافق", style="Green.TButton", command=win.destroy
        ).pack(pady=10, ipadx=20)

        return win

    def validate_date_range(self, start, end, context="الفترة"):
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            if end_date < start_date:
                self.show_info_popup("خطأ", f"تاريخ نهاية {context} لا يمكن أن يكون قبل تاريخ البداية.")
                return False
        except ValueError:
            self.show_info_popup("خطأ", f"صيغة تاريخ {context} غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return False
        return True

    def show_warning_window(self):
        if not hasattr(self, 'active_warnings'):
            self.active_warnings = []

        column_keys = ("warning",)
        column_labels = ["🚨 قائمة التحذيرات النشطة"]

        # ✅ تحقق من عدد الأعمدة لتفادي القسمة على صفر
        if len(column_labels) == 0:
            self.show_info_popup("خطأ", "تعذر إنشاء جدول التنبيهات. لم يتم العثور على أعمدة كافية.")
            return

        # نافذة تحتوي على جدول تحذيرات
        win, tree, bottom_controls = self.build_centered_popup(
            "⚠️ التنبيهات الحالية", 600, 400,
            columns=column_keys,
            column_labels=column_labels
        )

        # تعبئة الجدول بالتحذيرات (أو تركه فارغًا إذا لا توجد)
        tree._original_items = []
        for i, warning in enumerate(self.active_warnings):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=(warning,), tags=(tag,))
            tree._original_items.append([warning])

        self.apply_alternate_row_colors(tree)

        # ===== أزرار أسفل النافذة =====
        ttk.Button(bottom_controls, text="❌ إغلاق", style="info.TButton", command=win.destroy)\
            .pack(side="left", padx=10, ipadx=15)

        # مستقبلًا:
        # ttk.Button(bottom_controls, text="📁 عرض المؤرشفة", style="info.TButton", command=...)\ 
        #     .pack(side="left", padx=10, ipadx=15)

    def show_alert_popup(self):
        if not hasattr(self, 'current_alerts') or not self.current_alerts:
            return

        win = self.build_centered_popup("⚠️ التنبيهات الحالية", 500, 300)

        frame = tb.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)

        tb.Label(frame, text="🚨 تنبيهات النظام:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))

        alert_text = "\n\n".join(self.current_alerts)
        text_widget = tk.Text(frame, wrap="word", font=("Segoe UI", 10), height=10)
        text_widget.insert("1.0", alert_text)
        text_widget.configure(state="disabled", background=win.cget("bg"), relief="flat")
        text_widget.pack(fill="both", expand=True)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        tb.Button(frame, text="موافق", style="Green.TButton", command=win.destroy).pack(pady=5, ipadx=20)

    def show_custom_confirm(self, title, message):
        result = [False]  # نستخدم قائمة لتخزين النتيجة

        win = self.build_centered_popup(title, 400, 150)  # ✅ استبدل إنشاء Toplevel بهذه السطر

        def close():
            result[0] = False
            win.destroy()

        def confirm():
            result[0] = True
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)  # يجعل زر X كزر إلغاء

        frame = tb.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=message, anchor="center", justify="center", wraplength=350).pack(pady=10)

        btn_frame = tb.Frame(frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="✅ نعم", style="Green.TButton", command=confirm).pack(side="left", padx=10, ipadx=10)
        ttk.Button(btn_frame, text="❌ لا", style="Orange.TButton", command=close).pack(side="left", padx=10, ipadx=10)

        win.wait_window()
        return result[0]
    
    def setup_tree_scrollbars(self, tree, vsb, hsb):
        def show_vsb(*args):
            if float(args[1]) - float(args[0]) >= 1.0:
                vsb.pack_forget()
            else:
                vsb.pack(side="right", fill="y")

        def show_hsb(*args):
            if float(args[1]) - float(args[0]) >= 1.0:
                hsb.pack_forget()
            else:
                hsb.pack(side="bottom", fill="x")

        tree.configure(yscrollcommand=show_vsb, xscrollcommand=show_hsb)

    def apply_alternate_row_colors(self, tree):
        theme = self.current_theme
        even_color = "#ffffff" if theme == "lumen" else "#3a3a3a"
        odd_color = "#f0f0f0" if theme == "lumen" else "#2d2d2d"

        tree.tag_configure('evenrow', background=even_color)
        tree.tag_configure('oddrow', background=odd_color)

        for i, item in enumerate(tree.get_children()):
            # تجاهل صف الإجمالي (المجموع) إذا كان عليه tag "total"
            tags = tree.item(item, "tags")
            if "total" in tags:
                continue
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            tree.item(item, tags=(tag,))

    def fill_treeview_with_rows(self, tree, rows):
        """تعبئة Treeview بالبيانات وتطبيق ألوان الصفوف بالتناوب."""
        tree.delete(*tree.get_children())
        for i, row in enumerate(rows):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=row, tags=(tag,))
        self.apply_alternate_row_colors(tree)

    def _find_treeview_in_window(self, window):
        """البحث عن أول Treeview داخل نافذة معينة."""
        for frame in window.winfo_children():
            if isinstance(frame, tb.Frame):
                for child in frame.winfo_children():
                    if isinstance(child, ttk.Treeview):
                        return child
        return None

    def load_table_from_db(self, treeview, query, params=None):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            if params:
                c.execute(query, params)
            else:
                c.execute(query)
            rows = c.fetchall()
        self.fill_treeview_with_rows(treeview, rows)

    def _load_original_data(self, treeview, query, params=None):
        """تحميل البيانات الأصلية من قاعدة البيانات وتخزينها في treeview._original_items"""
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            if params:
                c.execute(query, params)
            else:
                c.execute(query)
            rows = c.fetchall()
            # تحديث النسخة الأصلية مع تحويل الصفوف إلى قوائم
            treeview._original_items = [list(row) for row in rows]
    
        # إعادة بناء الجدول
        treeview.delete(*treeview.get_children())
        for row in rows:
            treeview.insert("", "end", values=row)
        self.apply_alternate_row_colors(treeview)

    def attach_search_filter(self, parent, treeview, query_callback=None):
        search_frame = tb.Frame(parent)
        search_frame.pack(fill="x", padx=10, pady=(0, 10))

        search_var = tk.StringVar()
        search_entry = tb.Entry(search_frame, textvariable=search_var, width=40, font=("Segoe UI", 10))
        search_entry.insert(0, "🔍 بحث")  # النص الافتراضي
        search_entry.pack(side="left", padx=(0, 10))

        # ------ إدارة أحداث التركيز والخروج ------
        def on_focus_in(event):
            if search_entry.get() == "🔍 بحث":
                search_entry.delete(0, tk.END)  # مسح النص الافتراضي عند التركيز
                search_var.set("")
                search_entry.configure(foreground="#000000")  # إعادة لون النص

        def on_focus_out(event):
            if not search_var.get().strip():
                search_entry.insert(0, "🔍 بحث")  # إعادة النص الافتراضي عند الخروج
                search_entry.configure(foreground="#808080")  # لون رمادي للنص الافتراضي

        search_entry.bind("<FocusIn>", on_focus_in)
        search_entry.bind("<FocusOut>", on_focus_out)
        search_entry.configure(foreground="#808080")  # تطبيق اللون الافتراضي

        # ------ التصفية الديناميكية ------
        def filter_table(*args):
            query = search_var.get().strip().lower()
            if query == "🔍 بحث":  # تجاهل النص الافتراضي
                query = ""
    
            if not hasattr(treeview, "_original_items"):
                return
    
            treeview.delete(*treeview.get_children())
    
            if not query:
                for item in treeview._original_items:
                    treeview.insert("", "end", values=item)
                self.apply_alternate_row_colors(treeview)
                return
        
            filtered = [
                item for item in treeview._original_items
                if any(query in str(val).lower() for val in item)
            ]
        
            for item in filtered:
                treeview.insert("", "end", values=item)
        
            self.apply_alternate_row_colors(treeview)

        search_var.trace_add("write", filter_table)

    def export_table_to_pdf(self, treeview, title="تقرير"):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        import tempfile

        items = treeview.get_children()
        if not items:
            self.show_info_popup("لا يوجد بيانات", "🚫 لا توجد سجلات لطباعتها.")
            return

        # استثناء كل الأعمدة التي اسمها 'id' أو تنتهي بـ '_id'
        excluded_columns = {col for col in treeview["columns"] if col == "id" or col.endswith("_id")}

        # استخراج رؤوس الأعمدة
        headers = [treeview.heading(col)["text"] for col in treeview["columns"] if col not in excluded_columns]
        data = [headers]

        # استخراج صفوف البيانات مع استثناء الأعمدة
        for item in items:
            row = treeview.item(item)["values"]
            filtered_row = [cell for i, cell in enumerate(row) if treeview["columns"][i] not in excluded_columns]
            data.append(filtered_row)

        styles = getSampleStyleSheet()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        doc = SimpleDocTemplate(temp_file.name, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []

        elements.append(Paragraph(title, styles["Title"]))
        elements.append(Spacer(1, 12))

        # ✅ تحديد عرض الأعمدة تلقائيًا حسب عددها
        page_width = landscape(A4)[0] - 60  # خصم الهوامش من اليمين واليسار
        num_cols = len(data[0])
        col_widths = [page_width / num_cols] * num_cols

        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(t)
        doc.build(elements)

        os.startfile(temp_file.name)

    def configure_tree_columns(self, tree, column_labels):
        total_columns = len(column_labels)
        available_width = 540  # عرض تقريبي لتوزيع الأعمدة داخل النافذة

        if total_columns == 0:
            print("⚠️ لا توجد أعمدة لعرضها في الجدول.")
            return
        elif total_columns == 1:
            # عمود واحد فقط، نخصص له العرض الكامل
            tree.heading("#1", text=column_labels[0])
            tree.column("#1", anchor="center", width=available_width)
        else:
            default_col_width = int(available_width / (total_columns - 1))  # -1 لحذف id
            for i, label in enumerate(column_labels):
                col_id = f"#{i + 1}"
                tree.heading(col_id, text=label)
                if column_labels[i] == "":
                    tree.column(col_id, width=0, anchor="center", stretch=False)
                    tree.heading(col_id, text="")
                else:
                    tree.column(col_id, width=default_col_width, anchor="center")

    def build_centered_popup(self, title, width, height, columns=None, column_labels=None, table_height=10):
        window = tb.Toplevel(self)
        window.title(title)
        window.transient(self)
        window.grab_set()
        window.resizable(True, True)

        # تموضع في مركز النافذة الرئيسية
        window.update_idletasks()
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_w = self.winfo_width()
        main_h = self.winfo_height()
        pos_x = main_x + (main_w // 2) - (width // 2)
        pos_y = main_y + (main_h // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

        if columns:
            # في حال طلب جدول
            container = tb.Frame(window)
            container.pack(fill="both", expand=True, padx=10, pady=10)

            tree_frame = tb.Frame(container)
            tree_frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=table_height)
            tree.pack(side="left", fill="both", expand=True)

            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="TScrollbar")
            hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
            self.setup_tree_scrollbars(tree, vsb, hsb)

            self.configure_tree_columns(tree, column_labels)
    
            ttk.Separator(container, orient="horizontal").pack(fill="x", pady=5)

            bottom_btn_frame = tb.Frame(container)
            bottom_btn_frame.pack(side="bottom", pady=10, anchor="center")

            return window, tree, bottom_btn_frame

        def on_close():
            # إعادة تعيين حقول البحث في النافذة الرئيسية
            for widget in self.content_frame.winfo_children():
                if isinstance(widget, tb.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, tb.Entry) and child.get() == "🔍 بحث":
                            child.delete(0, tk.END)
                            child.insert(0, "🔍 بحث")
                            child.configure(foreground="#808080")
            window.destroy()
    
        window.protocol("WM_DELETE_WINDOW", on_close)
        return window

    def on_archive_close(self, window):
        window.destroy()
        self._load_car_data()  # أو أي دالة تحديث للجدول الرئيسي
        self._load_driver_table_data()

    def _preview_week_schedule(self):
        driver_name = self.main_entries[2].get().strip()
        if not driver_name:
            self.show_info_popup("تنبيه", "يرجى إدخال اسم السائق.")
            return

        today = datetime.today()
        monday = today - timedelta(days=today.weekday())
        self.preview_canvas.delete("all")
        self.preview_canvas.create_rectangle(0, 0, 595, 842, fill="white", outline="black")
        self.preview_canvas.create_text(297, 30, text="جدول المهام الأسبوعي", font=("Arial", 14, "bold"))

        headers = ["اليوم", "الطبيب / المخبر", "الوقت", "المواد"]
        col_x = [20, 150, 350, 450]
        col_widths = [130, 200, 100, 125]
        row_height = 26
        current_y = 60

        # رسم رؤوس الأعمدة
        for x, w, header in zip(col_x, col_widths, headers):
            self.preview_canvas.create_rectangle(x, current_y, x + w, current_y + row_height, fill="#d9d9d9", outline="black")
            self.preview_canvas.create_text(x + 5, current_y + 13, text=header, anchor="w", font=("Arial", 10, "bold"))

        current_y += row_height

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()

            for i in range(5):
                date_obj = monday + timedelta(days=i)
                date_str = date_obj.strftime("%Y-%m-%d")
                weekday_name = date_obj.strftime("%A")

                if self.is_on_vacation(driver_name, date_str, "سائق") or self.is_calendar_event(date_str):
                    continue

                rows = self._get_filtered_driver_tasks(driver_name, date_str, c)
                rows = rows or [("لا مهام", "", "", "")]

                for j, (doctor, lab, time, materials) in enumerate(rows):
                    bg_color = "#f2f2f2" if i % 2 == 0 else "#ffffff"
                    values = [
                        weekday_name if j == 0 else "",
                        f"{doctor} / {lab}",
                        time,
                        materials
                    ]

                    for x, w, val in zip(col_x, col_widths, values):
                        self.preview_canvas.create_rectangle(x, current_y, x + w, current_y + row_height, fill=bg_color, outline="black")
                        self.preview_canvas.create_text(x + 5, current_y + row_height // 2, text=val, anchor="w", font=("Arial", 9))

                    current_y += row_height

    def _print_week_schedule(self):
        driver_name = self.main_entries[2].get().strip()
        if not driver_name:
            self.show_info_popup("تنبيه", "يرجى إدخال اسم السائق.")
            return

        monday = datetime.today() - timedelta(days=datetime.today().weekday())
        start_date = monday.strftime("%Y-%m-%d")
        weekly_entries = {}

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            for i in range(5):
                current_date = (monday + timedelta(days=i)).strftime("%Y-%m-%d")

                if self.is_on_vacation(driver_name, current_date, "سائق") or self.is_calendar_event(current_date):
                    continue

                rows = self._get_filtered_driver_tasks(driver_name, current_date, c)

                if rows:
                    daily_tasks = [
                        [f"{doctor} / {lab}", time, materials, address]
                        for doctor, lab, time, materials, address in rows
                    ]
                    weekly_entries[i] = daily_tasks

        filename = f"{driver_name}_schedule_{start_date}.pdf".replace(" ", "_")
        try:
            title_name = "" if self.is_on_vacation(driver_name, start_date, "سائق") else driver_name
            generate_weekly_schedule(title_name, start_date, weekly_entries, filename)

            if self.show_custom_confirm("فتح الملف", f"✅ تم حفظ الجدول:\n{filename}\n\nهل تريد فتح الملف؟"):
                         os.startfile(filename)
        except Exception as e:
            self.show_info_popup("خطأ", f"حدث خطأ أثناء الطباعة:\n{e}")

    def _print_driver_table(self, mode):
        if mode == "current":
            table = self.driver_table
            title = "قائمة السائقين المسجلين"
        else:
            if not self.archived_drivers_window or not self.archived_drivers_window.winfo_exists():
                return
            table = self._find_treeview_in_window(self.archived_drivers_window)
            if not table:
                return
            if not table:
                return
            title = "قائمة السائقين المؤرشفين"

        self.export_table_to_pdf(table, title)

    def _print_car_table(self, mode):
        if mode == "current":
            table = self.car_table
            title = "قائمة السيارات المسجلة"
        else:
            if not hasattr(self, 'archived_car_tree') or not self.archived_car_tree.winfo_exists():
                return
            table = self.archived_car_tree
            if not table:
                return
            title = "قائمة السيارات المؤرشفة"

        self.export_table_to_pdf(table, title)

    def _print_vacations_table(self, mode):
        if mode == "current":
            table = self.vacation_tree
            title = "الإجازات الحالية"
        elif mode == "archived":
            table = getattr(self, "archived_vacation_tree", None)
            if not table or not table.winfo_exists():
                return
            title = "الإجازات المؤرشفة"
        else:
            return

        self.export_table_to_pdf(table, title)

    def _print_calendar_table(self, mode):
        if mode == "current":
            table = self.calendar_tree
            title = "الأحداث المجدولة"
        elif mode == "archived":
            table = getattr(self, "archived_calendar_tree", None)
            if not table or not table.winfo_exists():
                return
            title = "الأحداث المؤرشفة"
        else:
            return  # تجنب حالات غير معروفة

        self.export_table_to_pdf(table, title)

    def _build_main_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)

        # الإطار الأيسر لإدخال البيانات
        left_frame = tb.Frame(frame)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)

        # الإطار الأيمن لمعاينة ورقة A4
        right_frame = tb.LabelFrame(frame, text="🖨️ معاينة ورقة A4", padding=10)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        field_labels = [
            "اسم الطبيب:", "اسم المخبر:", "اسم السائق:",
            "تاريخ المهمة (YYYY-MM-DD):", "الوقت (مثال 08:00-08:30):",
            "ملاحظات:", "عنوان الطبيب:"
        ]
        self.main_entries = []

        for i, label_text in enumerate(field_labels):
            ttk.Label(left_frame, text=label_text).grid(row=i, column=0, sticky="w", pady=4)
            entry = ttk.Combobox(left_frame, values=[""] + self.get_driver_names(), state="readonly", width=37, height=10, justify="left")
            entry.grid(row=i, column=1, pady=4)
            self.main_entries.append(entry)

        # زر حفظ المهمة
        ttk.Button(
            left_frame,
            text="💾 حفظ المهمة",
            style="Green.TButton",
            command=self._save_main_task
        ).grid(row=len(field_labels), column=0, columnspan=2, pady=10)

        # أزرار الجدول الأسبوعي و PDF
        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.grid(row=len(field_labels)+1, column=0, columnspan=2, pady=10)

        ttk.Button(
            buttons_frame,
            text="📅 عرض الأسبوع الكامل",
            style="Orange.TButton",
            command=self._preview_week_schedule
        ).pack(side="left", padx=5)

        ttk.Button(
            buttons_frame,
            text="🖨️ توليد PDF",
            style="Purple.TButton",
            command=self._export_week_schedule
        ).pack(side="left", padx=5)

        # Canvas للمعاينة
        self.preview_canvas = tb.Canvas(right_frame, bg="white", width=595, height=842)
        self.preview_canvas.pack(expand=True)

        return frame

    def _retire_selected_car(self):
        plate = self.retire_plate_combo.get().strip()
        retire_date = self.retire_date_picker.get().strip()
        extra_note = self.retire_notes_entry.get().strip()

        if not plate or not retire_date:
            self.show_info_popup("تنبيه", "يرجى اختيار رقم اللوحة وتاريخ إخراج السيارة من الخدمة.")
            return

        try:
            retire_dt = datetime.strptime(retire_date, "%Y-%m-%d")
        except ValueError:
            self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.")
            return

        today_str = datetime.today().strftime("%Y-%m-%d")

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()

            # تحديث ملاحظات السيارة
            retire_message = f"🚫 اخرجت بتاريخ {retire_date}"
            if extra_note:
                retire_message += f" – {extra_note}"

            c.execute("""
                UPDATE car_maintenance
                SET notes = ? || CHAR(10) || COALESCE(notes, '')
                WHERE license_plate = ?
            """, (retire_message, plate))

            # تعديل المواعيد إلى تاريخ التصفية
            c.execute("""
                UPDATE car_appointments
                SET appointment_date = ?
                WHERE license_plate = ? AND date(appointment_date) >= date(?)
            """, (retire_date, plate, today_str))

            # ✅ أرشفة علاقة السائق بالسيارة إذا كانت قيد الاستخدام
            c.execute("""
                SELECT id, name, plate_from
                FROM drivers
                WHERE assigned_plate = ?
                  AND (plate_to IS NULL OR plate_to = '')
            """, (plate,))
            row = c.fetchone()

            if row:
                driver_id, driver_name, plate_from = row
                archived_at = datetime.now().strftime("%Y-%m-%d")

                # ✅ أولاً: تحديث plate_to في جدول السائقين
                c.execute("""
                    UPDATE drivers
                    SET plate_to = ?
                    WHERE id = ?
                """, (retire_date, driver_id))

                # ✅ ثم أرشفة العلاقة
                c.execute("""
                    INSERT INTO driver_car_assignments_archive (
                        driver_id, driver_name, assigned_plate,
                        plate_from, plate_to, archived_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    driver_id,
                    driver_name,
                    plate,
                    plate_from,
                    retire_date,
                    archived_at
                ))

                # ✅ وأخيراً: إزالة العلاقة من جدول السائقين
                c.execute("""
                    UPDATE drivers
                    SET assigned_plate = NULL,
                        plate_from = NULL,
                        plate_to = NULL
                    WHERE id = ?
                """, (driver_id,))

            conn.commit()

            # ✅ أرشفة المواعيد المستقبلية المرتبطة بالسيارة
            c.execute("""
                INSERT INTO archived_car_appointments (license_plate, appointment_type, appointment_date)
                SELECT license_plate, appointment_type, appointment_date
                FROM car_appointments
                WHERE license_plate = ? AND date(appointment_date) >= date(?)
            """, (plate, today_str))

            # ✅ حذفها من جدول المواعيد النشطة
            c.execute("""
                DELETE FROM car_appointments
                WHERE license_plate = ? AND date(appointment_date) >= date(?)
            """, (plate, today_str))

            conn.commit()

        # ✅ تحديث فوري لواجهة المستخدم بعد التعديل في قاعدة البيانات
        self._load_driver_table_data()     # ← أولًا: تحديث جدول السائقين ليعكس تفريغ السيارة
        self._load_car_data()              # ← ثانيًا: تحديث جدول السيارات

        updated_plates = self.get_all_license_plates()

        # ✅ تحديث القوائم المنسدلة إن وُجدت (مع التحقق من وجودها)
        if hasattr(self, "car_plate_combo") and self.car_plate_combo.winfo_exists():
            self.car_plate_combo["values"] = updated_plates

        if hasattr(self, "retire_plate_combo") and self.retire_plate_combo.winfo_exists():
            self.retire_plate_combo["values"] = updated_plates

        if hasattr(self, "plate_combo") and self.plate_combo.winfo_exists():
            self.plate_combo["values"] = self._get_available_cars_for_drivers()

        if hasattr(self, "driver_car_plate_combo") and self.driver_car_plate_combo.winfo_exists():
            self.driver_car_plate_combo["values"] = self._get_available_cars_for_drivers()

        # إعادة تعيين الحقول
        self.retire_plate_combo.set("")
        self.retire_date_picker.entry.delete(0, tb.END)
        self.retire_notes_entry.delete(0, tb.END)

        # التحديثات النهائية
        self.check_warnings()
        self._check_alerts()
        self._check_appointments()

        self.show_info_popup("تم", f"✅ تم إخراج السيارة عن الخدمة {plate} من الخدمة بتاريخ {retire_date}")

    def _build_car_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)
        self.car_entries = []

        # === الحاوية العلوية لثلاثة إطارات متجاورة ===
        top_container = tb.Frame(frame)
        top_container.pack(fill="x", padx=10, pady=10)
        top_container.columnconfigure(0, weight=1)
        top_container.columnconfigure(1, weight=1)
        top_container.columnconfigure(2, weight=1)

        # === إطار بيانات السيارة ===
        form_frame = ttk.LabelFrame(top_container, text="📋 بيانات السيارة", padding=15)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        form_frame.configure(width=330)

        # --- رقم اللوحة ---
        row1 = tb.Frame(form_frame)
        row1.pack(anchor="w", pady=(6, 0))
        ttk.Label(row1, text="رقم اللوحة:").pack(side="left")
        ttk.Label(row1, text="*", foreground="red").pack(side="left")
        license_plate_entry = tb.Entry(form_frame, width=30)
        license_plate_entry.pack(anchor="w", pady=(0, 6))
        self.car_entries.append(license_plate_entry)

        # --- Autobahn Pickerl من وإلى في نفس السطر ---
        row_autobahn = tb.Frame(form_frame)
        row_autobahn.pack(anchor="w", pady=6)

        # === العمود الأول: من ===
        col_from = tb.Frame(row_autobahn)
        col_from.pack(side="left", padx=(0, 20))

        from_label_row = tb.Frame(col_from)
        from_label_row.pack(anchor="w")
        ttk.Label(from_label_row, text="Autobahn Pickerl من:").pack(side="left")
        ttk.Label(from_label_row, text="*", foreground="red").pack(side="left", padx=(4, 0))

        from_autobahn = CustomDatePicker(col_from)
        from_autobahn.pack(anchor="w")
        self.car_entries.append(from_autobahn.entry)

        # === العمود الثاني: إلى ===
        col_to = tb.Frame(row_autobahn)
        col_to.pack(side="left")

        to_label_row = tb.Frame(col_to)
        to_label_row.pack(anchor="w")
        ttk.Label(to_label_row, text="Autobahn Pickerl إلى:").pack(side="left")
        ttk.Label(to_label_row, text="*", foreground="red").pack(side="left", padx=(4, 0))

        to_autobahn = CustomDatePicker(col_to)
        to_autobahn.pack(anchor="w")
        self.car_entries.append(to_autobahn.entry)

        # --- Jährlich Pickerl حتى ---
        row4 = tb.Frame(form_frame)
        row4.pack(anchor="w", pady=6)
        ttk.Label(row4, text="Jährlich Pickerl حتى:").pack(side="left")
        ttk.Label(row4, text="*", foreground="red").pack(side="left")
        yearly_pickerl = CustomDatePicker(form_frame)
        yearly_pickerl.pack(anchor="w")
        self.car_entries.append(yearly_pickerl.entry)

        # --- ملاحظات ---
        ttk.Label(form_frame, text="ملاحظات:").pack(anchor="w", pady=5)
        notes_entry = tb.Entry(form_frame, width=60)
        notes_entry.pack(anchor="w", pady=(0, 8))
        self.car_entries.append(notes_entry)

        # --- زر الحفظ ---
        ttk.Button(form_frame, text="💾 حفظ بيانات السيارة", style="Green.TButton", command=self.save_car_data).pack(pady=15, ipadx=20)

        # === إطار إضافة الموعد === (تم نقله إلى الوسط)
        appointment_frame = ttk.LabelFrame(top_container, text="📅 إضافة موعد", padding=15)
        appointment_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        appointment_frame.configure(width=330)

        label_row = tb.Frame(appointment_frame)
        label_row.pack(anchor="w", pady=(5, 2))
        ttk.Label(label_row, text="رقم اللوحة:").pack(side="left")
        ttk.Label(label_row, text="*", foreground="red").pack(side="left")
        self.car_plate_combo = ttk.Combobox(appointment_frame, values=self.get_all_license_plates(), state="readonly", width=20)
        self.car_plate_combo.pack(anchor="w", pady=2)

        ttk.Label(appointment_frame, text="نوع الموعد:").pack(anchor="w", pady=(10, 2))
        self.appointment_type_entry = tb.Entry(appointment_frame, width=25)
        self.appointment_type_entry.pack(anchor="w", pady=2)

        label_row = tb.Frame(appointment_frame)
        label_row.pack(anchor="w", pady=(10, 2))
        ttk.Label(label_row, text="تاريخ الموعد:").pack(side="left")
        ttk.Label(label_row, text="*", foreground="red").pack(side="left")
        self.appointment_date_picker = CustomDatePicker(appointment_frame)
        self.appointment_date_picker.pack(anchor="w", pady=2)

        ttk.Button(appointment_frame, text="💾 إضافة الموعد", style="Green.TButton", command=self._add_appointment).pack(pady=15, ipadx=20)

        # === إطار إخراج السيارة عن الخدمة === (تم نقله إلى اليمين)
        retire_frame = ttk.LabelFrame(top_container, text="📤 إخراج السيارة", padding=15)
        retire_frame.grid(row=0, column=2, sticky="nsew")
        retire_frame.configure(width=330)

        ttk.Label(retire_frame, text="إختر السيارة:").pack(anchor="w", pady=(5, 2))
        self.retire_plate_combo = ttk.Combobox(retire_frame, values=self.get_all_license_plates(), state="readonly", width=20)
        self.retire_plate_combo.pack(anchor="w", pady=2)

        label_row = tb.Frame(retire_frame)
        label_row.pack(anchor="w", pady=(10, 2))
        ttk.Label(label_row, text="تاريخ الإخراج:").pack(side="left")
        ttk.Label(label_row, text="*", foreground="red").pack(side="left")
        self.retire_date_picker = CustomDatePicker(retire_frame)
        self.retire_date_picker.pack(anchor="w", pady=2)

        ttk.Label(retire_frame, text="ملاحظات إضافية:").pack(anchor="w", pady=(10, 2))
        self.retire_notes_entry = tb.Entry(retire_frame, width=30)
        self.retire_notes_entry.pack(anchor="w", pady=2)

        ttk.Button(retire_frame, text="💾 موافق", style="Red.TButton", command=self._retire_selected_car).pack(pady=15, ipadx=20)

        # === جدول عرض السيارات ===
        table_frame = ttk.LabelFrame(frame, text="🚗 جدول السيارات", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree_frame = tb.Frame(table_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "license_plate", "autobahn_from", "autobahn_to", "yearly_pickerl", "next_service")
        labels = ["", "رقم اللوحة", "Autobahn Pickerl من", "Autobahn Pickerl إلى", "Jährlich Pickerl حتى", "ملاحظات"]

        self.car_table = ttk.Treeview(tree_frame, columns=columns, show="headings", height=6)
        self.car_table.column("id", width=0, stretch=False)
        self.car_table.heading("id", text="")
        self.car_table.reload_callback = self._load_car_data
        self.car_table.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.car_table.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.car_table.xview)
        self.setup_tree_scrollbars(self.car_table, vsb, hsb)

        self.configure_tree_columns(self.car_table, labels)
        self.apply_alternate_row_colors(self.car_table)

        # === أدوات أسفل الجدول ===
        bottom_controls = tb.Frame(table_frame)
        bottom_controls.pack(fill="x", pady=(10, 10))

        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.car_table)

        buttons_frame = tb.Frame(bottom_controls)
        buttons_frame.pack(side="left", expand=True)

        inner_buttons = tb.Frame(buttons_frame)
        inner_buttons.pack(anchor="center", padx=(0, 300))

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton", command=lambda: self._print_car_table("current")).pack(side="left", padx=10)
        ttk.Button(inner_buttons, text="📁 عرض السيارات المؤرشفة", style="info.TButton", command=self._toggle_archived_cars_window).pack(side="left", padx=10)
        ttk.Button(inner_buttons, text="📝 تعديل السيارة", style="Purple.TButton", command=self._edit_car_record).pack(side="left", padx=10)

        self._load_car_data()
        return frame

    def _toggle_archived_cars_window(self):
        if hasattr(self, 'archived_cars_window') and self.archived_cars_window.winfo_exists():
            self.archived_cars_window.destroy()
            self.archived_cars_window = None
            self._load_car_data()
            return

        columns = (
            "id", "license_plate",
            "autobahnpickerl_from", "autobahnpickerl_to",
            "yearly_pickerl_until", "notes"
        )
        labels = [
            "", "رقم السيارة",
            "Autobahn من", "إلى",
            "Pickerl السنوي حتى", "ملاحظات"
        ]

        win, tree, _ = self.build_centered_popup("📁 السيارات المؤرشفة", 1000, 500, columns, labels)
        tree.column("id", width=0, stretch=False)
        tree.heading("id", text="")
        tree.reload_callback = self._load_archived_cars
        self.archived_cars_window = win

        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=self._load_archived_cars)

        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", command=lambda: self._print_car_table("archived")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", command=win.destroy).pack(side="left", padx=10)

        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        today = datetime.today().strftime("%Y-%m-%d")
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, license_plate,
                       autobahnpickerl_from, autobahnpickerl_to,
                       yearly_pickerl_until, notes
                FROM car_maintenance
                WHERE notes LIKE '🚫%'
                ORDER BY id DESC
            """)
            rows = c.fetchall()

        tree._original_items = [row for row in rows]
        self.fill_treeview_with_rows(tree, rows)
        self.archived_car_tree = tree

    def _save_main_task(self):
        values = [e.get().strip() for e in self.main_entries]

        if not all(values[:4]):
            self.show_info_popup("تنبيه", "يرجى إدخال الحقول الأساسية (الطبيب، المخبر، السائق، التاريخ).")
            return

        try:
            datetime.strptime(values[3], "%Y-%m-%d")
        except ValueError:
            self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO driver_tasks (
                    driver_name, task_date, doctor_name,
                    lab_name, time_window, materials, doctor_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [values[2], values[3], values[0], values[1], values[4], values[5], values[6]])
            conn.commit()
            conn.close()

            self.show_info_popup("تم", "✅ تم حفظ المهمة.")
            for e in self.main_entries:
                if isinstance(e, ttk.Combobox):
                    e.set("")
                else:
                    e.delete(0, tb.END)

            self._draw_a4_preview(values)

        except Exception as e:
            self.show_info_popup("خطأ", f"حدث خطأ أثناء حفظ المهمة:\n{e}")

    def _load_car_data(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self._load_original_data(
            self.car_table,
            """SELECT id, license_plate,
               autobahnpickerl_from, autobahnpickerl_to,
               yearly_pickerl_until, notes
            FROM car_maintenance
            WHERE (notes IS NULL 
                   OR notes NOT LIKE '🚫%' 
                   OR date(substr(notes, instr(notes, 'بتاريخ') + 7, 10)) > date('now'))
            ORDER BY id DESC"""
        )
        
        # ✅ تحديث قائمة رقم السيارة في تبويب السائقين
        if hasattr(self, "driver_car_plate_combo") and self.driver_car_plate_combo.winfo_exists():
            self.driver_car_plate_combo["values"] = self._get_available_cars_for_drivers()

        # ✅ تحديث قائمة رقم السيارة في نافذة تعديل السائق (إن وُجدت)
        if hasattr(self, "plate_combo") and self.plate_combo.winfo_exists():
            self.plate_combo["values"] = self._get_available_cars_for_drivers()

    def check_warnings(self):
        self.active_warnings = []

        today = datetime.today()
        warning_threshold = today + timedelta(days=120)
        today_str = today.strftime("%Y-%m-%d")  # ✅ هذا هو الموضع الصحيح

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT license_plate, yearly_pickerl_until, autobahnpickerl_to 
                FROM car_maintenance
                WHERE notes IS NULL 
                   OR notes NOT LIKE '🚫%' 
                   OR date(substr(notes, instr(notes, 'بتاريخ') + 7, 10)) > date(?)
            """, (today_str,))  # ✅ استخدمنا today_str هنا

            for license_plate, yearly_str, autobahn_str in c.fetchall():
                # تنبيه لـ yearly Pickerl
                try:
                    exp_date = datetime.strptime(yearly_str, "%Y-%m-%d")
                    if exp_date <= warning_threshold:
                        self.active_warnings.append(f"🚗 السيارة {license_plate}: ينتهي الـ Pickerl السنوي في {yearly_str}")
                except Exception:
                    pass

                # تنبيه لـ Autobahn Pickerl
                try:
                    exp_date = datetime.strptime(autobahn_str, "%Y-%m-%d")
                    if exp_date <= warning_threshold:
                        self.active_warnings.append(f"🚧 السيارة {license_plate}: ينتهي Autobahn Pickerl في {autobahn_str}")
                except Exception:
                    pass

        # تحديث الأيقونة حسب وجود تحذيرات
        if self.active_warnings:
            self.alert_icon.configure(foreground="orange")
        else:
            self.alert_icon.configure(foreground="gray")
        self.alert_icon.pack(side="left", padx=(5, 0))

    def _check_alerts(self):
        alerts = []

        try:
            today = datetime.today()
            threshold = today + timedelta(days=120)
            today_str = today.strftime("%Y-%m-%d")  # ✅ إضافة التاريخ الحالي كسلسلة

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT license_plate, yearly_pickerl_until, autobahnpickerl_to
                    FROM car_maintenance
                    WHERE (yearly_pickerl_until IS NOT NULL OR autobahnpickerl_to IS NOT NULL)
                      AND (notes IS NULL 
                           OR notes NOT LIKE '🚫%' 
                           OR date(substr(notes, instr(notes, 'بتاريخ') + 7, 10)) > date(?))
                """, (today_str,))  # ✅ تطبيق نفس منطق التصفية الذكي

                for license_plate, yearly_str, autobahn_str in c.fetchall():
                    # Alert for yearly Pickerl
                    try:
                        pickerl_dt = datetime.strptime(yearly_str, "%Y-%m-%d")
                        if pickerl_dt <= threshold:
                            alerts.append(f"⚠️ السيارة {license_plate}: ينتهي الفحص السنوي في {pickerl_dt.strftime('%Y-%m-%d')}")
                    except:
                        pass

                    # Alert for Autobahn Pickerl
                    try:
                        autobahn_dt = datetime.strptime(autobahn_str, "%Y-%m-%d")
                        if autobahn_dt <= threshold:
                            alerts.append(f"⚠️ السيارة {license_plate}: ينتهي Autobahn Pickerl في {autobahn_dt.strftime('%Y-%m-%d')}")
                    except:
                        pass

        except Exception as e:
            print("خطأ أثناء التحقق من التنبيهات:", e)

        self.current_alerts = alerts

        if alerts:
            self.alert_icon.configure(foreground="orange")
        else:
            self.alert_icon.configure(foreground="gray")
        self.alert_icon.pack(side="left", padx=5)

    def _check_appointments(self):
        today = datetime.today().strftime("%Y-%m-%d")
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT COUNT(*) FROM car_appointments WHERE date(appointment_date) >= date(?)
            """, (today,))
            count = c.fetchone()[0]

        if count > 0:
            self.pin_icon.configure(foreground="red")
        else:
            self.pin_icon.configure(foreground="gray")
        self.pin_icon.pack(side="left", padx=5)

    def save_car_data(self):
        data = [e.get().strip() for e in self.car_entries]

        required_fields = [
            (0, "رقم اللوحة"),
            (1, "Autobahn Pickerl من"),
            (2, "Autobahn Pickerl إلى"),
            (3, "Jährlich Pickerl حتى")
        ]

        # تحقق من الحقول الأساسية
        for idx, label in required_fields:
            if not data[idx]:
                self.show_info_popup("تنبيه", f"الرجاء إدخال {label} (حقل إلزامي).")
                return

        # تحقق من تسلسل التواريخ
        if not self.validate_date_range(data[1], data[2], context="Autobahn Pickerl"):
            return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO car_maintenance (
                        license_plate,
                        autobahnpickerl_from,
                        autobahnpickerl_to,
                        yearly_pickerl_until,
                        notes
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    data[0],  # license_plate
                    data[1],  # autobahn_from
                    data[2],  # autobahn_to
                    data[3],  # yearly_pickerl
                    data[4]   # next_service
                ))
                conn.commit()

            self._load_car_data()
            self.show_info_popup("✔️ تم الحفظ", f"✅ تم حفظ السيارة: {data[0]}")
            self.check_warnings()
            self._check_alerts()
            self._check_appointments()
            self.car_plate_combo['values'] = self.get_all_license_plates()
            self.retire_plate_combo['values'] = self.get_all_license_plates()

        except Exception as e:
            self.show_info_popup("خطأ", f"فشل الحفظ:\n{e}")
            return

        for e in self.car_entries:
            e.delete(0, tb.END)

    def _add_appointment(self):
        plate = self.car_plate_combo.get().strip()
        appt_type = self.appointment_type_entry.get().strip()
        appt_date = self.appointment_date_picker.get().strip()

        if not plate or not appt_type or not appt_date:
            self.show_info_popup("تنبيه", "يرجى إدخال كافة الحقول.")
            return

        # تحقق من تنسيق التاريخ
        try:
            datetime.strptime(appt_date, "%Y-%m-%d")
        except ValueError:
            self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.")
            return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO car_appointments (license_plate, appointment_type, appointment_date)
                    VALUES (?, ?, ?)
                """, (plate, appt_type, appt_date))
                conn.commit()

            self.show_info_popup("✔️ تم", f"✅ تم حفظ الموعد لرقم اللوحة: {plate}")
    
            # إعادة تعيين الحقول
            self.car_plate_combo.set("")
            self.appointment_type_entry.delete(0, tb.END)
            self.appointment_date_picker.entry.delete(0, tb.END)
            self._check_appointments()

        except Exception as e:
            self.show_info_popup("خطأ", f"فشل الحفظ:\n{e}")

    def _edit_car_record(self):
        selected = self.car_table.selection()
        if not selected:
            self.show_info_popup("تنبيه", "يرجى اختيار سيارة أولاً.")
            return

        values = self.car_table.item(selected[0], "values")
        car_id = values[0]
        original_values = values[1:]  # بدون id

        edit_win = self.build_centered_popup("📝 تعديل السيارة", 600, 450)

        main_frame = tb.Frame(edit_win, padding=15)
        main_frame.pack(fill="both", expand=True)

        labels = [
            "رقم اللوحة:",
            "Autobahn Pickerl من:", "إلى:",
            "Jährlich Pickerl حتى:",
            "ملاحظات:"
        ]

        entries = []
    
        for i, label in enumerate(labels):
            ttk.Label(main_frame, text=label).grid(row=i, column=0, sticky="e", padx=(10, 5), pady=6)
            input_frame = tb.Frame(main_frame)
            input_frame.grid(row=i, column=1, sticky="w", padx=(0, 5), pady=6)

            if label.startswith("من") or label.startswith("إلى") or "Pickerl" in label:
                date_picker = CustomDatePicker(input_frame)
                try:
                    dt = datetime.strptime(original_values[i], "%Y-%m-%d")
                    date_str = dt.strftime("%Y-%m-%d")
                except:
                    date_str = original_values[i]
                date_picker.entry.insert(0, date_str)
                date_picker.pack(side="left")
                entry = date_picker.entry
            else:
                entry = tb.Entry(input_frame, width=33)
                entry.insert(0, original_values[i])
                entry.pack(side="left")

            entries.append(entry)

        def save_car_edit_changes():
            new_data = [e.get().strip() if hasattr(e, 'get') else e.get() for e in entries]
            required_indexes = [0, 1, 2, 3]

            for idx in required_indexes:
                if not new_data[idx]:
                    self.show_info_popup("تنبيه", f"يرجى ملء الحقل: {labels[idx]}")
                    return

            if not self.validate_date_range(new_data[1], new_data[2], context="Autobahn"):
                return

            try:
                with sqlite3.connect("medicaltrans.db") as conn:
                    c = conn.cursor()

                    # ✅ الآن نجلب id أيضًا
                    c.execute("SELECT id, license_plate, autobahnpickerl_from, autobahnpickerl_to, yearly_pickerl_until, notes FROM car_maintenance WHERE id = ?", (car_id,))
                    old_record = c.fetchone()

                    if not old_record:
                        self.show_info_popup("خطأ", "تعذر العثور على السجل الأصلي.")
                        return

                    if (new_data[1] != old_record[2] or
                        new_data[2] != old_record[3] or
                        new_data[3] != old_record[4]):
        
                        # ✅ أرشفة البيانات مع تجاهل id (old_record[1:])
                        c.execute("""
                            INSERT INTO archived_car_maintenance (
                                license_plate,
                                autobahnpickerl_from,
                                autobahnpickerl_to,
                                yearly_pickerl_until,
                                notes
                            )
                            VALUES (?, ?, ?, ?, ?)
                        """, old_record[1:])  # ← هذا هو التعديل المهم

                        # ✅ تحديث السجل الحالي
                        c.execute("""
                            UPDATE car_maintenance
                            SET license_plate = ?,
                                autobahnpickerl_from = ?,
                                autobahnpickerl_to = ?,
                                yearly_pickerl_until = ?,
                                notes = ?
                            WHERE id = ?
                        """, (*new_data, car_id))

                    else:
                        c.execute("""
                            UPDATE car_maintenance
                            SET license_plate = ?,
                                notes = ?
                            WHERE id = ?
                        """, (new_data[0], new_data[4], car_id))

                    conn.commit()

                edit_win.destroy()
                self._load_car_data()
                self.check_warnings()
                self._check_alerts()
                self._check_appointments()
                self.car_plate_combo['values'] = self.get_all_license_plates()
                self.show_info_popup("✔️ تم التعديل", "✅ تم تعديل بيانات السيارة بنجاح.")
                self.check_warnings()
                self._check_alerts()

            except Exception as e:
                self.show_info_popup("خطأ", f"فشل التعديل:\n{e}")

        def delete_record():
            if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حذف بيانات السيارة المحددة؟"):
                return
            try:
                conn = sqlite3.connect("medicaltrans.db")
                c = conn.cursor()
                c.execute("DELETE FROM car_maintenance WHERE id = ?", (car_id,))
                conn.commit()
                conn.close()
                edit_win.destroy()
                self._load_car_data()
                self.show_info_popup("✔️ تم الحذف", "✅ تم حذف السيارة بنجاح.")
            except Exception as e:
                self.show_info_popup("خطأ", f"فشل الحذف:\n{e}")

        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=len(labels), column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_car_edit_changes)\
            .pack(side="left", padx=10, ipadx=10)

        main_frame.columnconfigure(1, weight=1)

    def _build_doctor_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)
        # frame.pack(fill="both", expand=True)

        labels = [
            "اسم الطبيب:", "وقت التواجد (من - إلى أو ملاحظة):",
            "المواد من المخبر للطبيب:", "عنوان الطبيب:",
            "المخبر المستقبل للعينات:", "الفواتير (اختياري):"
        ]

        self.doctor_entries = []
        for i, text in enumerate(labels):
            ttk.Label(frame, text=text).grid(row=i, column=0, sticky="w", pady=5)
            entry = tb.Entry(frame, width=60)
            entry.grid(row=i, column=1, pady=5)
            self.doctor_entries.append(entry)

        # زر حفظ بيانات الطبيب بتنسيق احترافي
        ttk.Button(
            frame,
            text="💾 حفظ بيانات الطبيب",
            style="Green.TButton",
            command=self._save_doctor
        ).grid(row=len(labels), column=0, columnspan=2, pady=20)

        return frame

    def _save_doctor(self):
        data = [e.get().strip() for e in self.doctor_entries]
        if not data[0]:
            self.show_info_popup("تنبيه", "يرجى إدخال اسم الطبيب.")
            return

        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO doctors (name, available_from, material_from_lab, address, target_lab, billing)
            VALUES (?, ?, ?, ?, ?, ?)
        """, data)
        conn.commit()
        conn.close()
        for e in self.doctor_entries:
            e.delete(0, tb.END)

        self.show_info_popup("✔️ تم الحفظ", f"✅ تم حفظ الطبيب: {data[0]}")

    def _build_lab_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)
        # frame.pack(fill="both", expand=True)

        labels = ["اسم المخبر:", "عنوان المخبر:"]
        self.lab_entries = []

        for i, text in enumerate(labels):
            ttk.Label(frame, text=text).grid(row=i, column=0, sticky="w", pady=5)
            entry = tb.Entry(frame, width=60)
            entry.grid(row=i, column=1, pady=5)
            self.lab_entries.append(entry)

        # زر حفظ بيانات المخبر بتنسيق احترافي
        ttk.Button(
            frame,
            text="💾 حفظ بيانات المخبر",
            style="Green.TButton",
            command=self._save_lab
        ).grid(row=len(labels), column=0, columnspan=2, pady=20)

        return frame

    def _save_lab(self):
        name, address = [e.get().strip() for e in self.lab_entries]
        if not name:
            self.show_info_popup("تنبيه", "يرجى إدخال اسم المخبر.")
            return

        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()
        c.execute("INSERT INTO labs (name, address) VALUES (?, ?)", (name, address))
        conn.commit()
        conn.close()
        for e in self.lab_entries:
            e.delete(0, tb.END)

        self.show_info_popup("✔️ تم الحفظ", f"✅ تم حفظ المخبر: {name}")

    def _load_driver_table_data(self):
        self._load_original_data(
            self.driver_table,
            """SELECT id, name, address, phone,
                   car_received_date, employment_end_date,
                   contract_type,
                   assigned_plate, plate_from, plate_to,
                   issues
            FROM drivers
            WHERE employment_end_date IS NULL OR employment_end_date = '' 
               OR date(employment_end_date) >= date('now')"""
        )

    def _load_current_drivers(self):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, name, address, phone, car_received_date, employment_end_date, issues, contract_type
                FROM drivers
                WHERE employment_end_date IS NULL OR employment_end_date = '' OR date(employment_end_date) >= date('now')
            """)
            rows = c.fetchall()

        self.fill_treeview_with_rows(self.driver_table, rows)

    def _load_archived_drivers(self, tree):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, name, address, phone,
                       car_received_date, employment_end_date, issues
                FROM drivers
                WHERE employment_end_date IS NOT NULL
                  AND employment_end_date != ''
                  AND date(employment_end_date) <= date('now')
                ORDER BY employment_end_date DESC
            """)
            rows = c.fetchall()

        # إفراغ الجدول ثم تعبئته
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)

    def _load_archived_cars(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self.load_table_from_db(
            self.car_table,
            """
            SELECT id, license_plate,
                   autobahnpickerl_from, autobahnpickerl_to,
                   yearly_pickerl_until, next_service_date
            FROM car_maintenance
            WHERE notes LIKE '🚫%' AND notes IS NOT NULL
            ORDER BY next_service_date DESC
            """,
            (today,)
        )

    def reload_archived_data(self, treeview, table_name, condition):
        """تعيد تحميل البيانات الأرشيفية حسب الجدول والشرط"""
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute(f"""
                SELECT * FROM {table_name}
                WHERE {condition}
                ORDER BY employment_end_date DESC
            """)
            rows = c.fetchall()
        treeview._original_items = [list(row) for row in rows]
        self.fill_treeview_with_rows(treeview, rows)

    def _build_driver_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)
        frame.pack(fill="both", expand=True)

        top_row = tb.Frame(frame)
        top_row.pack(fill="x", padx=10, pady=10)
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=1)

        self.driver_entries = []

        # ==== إطار بيانات السائق ====
        form_frame = ttk.LabelFrame(top_row, text="📋 بيانات السائق الجديد", padding=15)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # ==== إطار مصاريف الوقود ====
        fuel_frame = ttk.LabelFrame(top_row, text="⛽ مصاريف الوقود", padding=15)
        fuel_frame.grid(row=0, column=1, sticky="nsew")

        # --- اسم السائق ---
        ttk.Label(fuel_frame, text="اسم السائق:").pack(anchor="w", pady=5)
        self.fuel_driver_combo = ttk.Combobox(fuel_frame, values=self.get_driver_names(), state="readonly", width=30)
        self.fuel_driver_combo.pack(anchor="w", pady=5)

        # --- التاريخ ---
        ttk.Label(fuel_frame, text="التاريخ:").pack(anchor="w", pady=5)
        self.fuel_date_picker = CustomDatePicker(fuel_frame)
        self.fuel_date_picker.pack(anchor="w", pady=5)

        # --- المبلغ ---
        ttk.Label(fuel_frame, text="المبلغ (€):").pack(anchor="w", pady=5)
        self.fuel_amount_entry = tb.Entry(fuel_frame, width=20)
        self.fuel_amount_entry.pack(anchor="w", pady=5)

        # --- أزرار ---
        btns_frame = tb.Frame(fuel_frame)
        btns_frame.pack(pady=10)
        ttk.Button(btns_frame, text="💾 حفظ", style="Green.TButton", command=self._save_fuel_expense).pack(side="left", padx=5)
        ttk.Button(btns_frame, text="📊 عرض", style="info.TButton", command=self._show_fuel_expense_table).pack(side="left", padx=5)

        # --- حقل: اسم السائق + من + إلى ---
        name_label_frame = tb.Frame(form_frame)
        name_label_frame.grid(row=0, column=0, sticky="e", pady=5, padx=(10, 5))
        ttk.Label(name_label_frame, text="اسم السائق:").pack(side="left")
        ttk.Label(name_label_frame, text="*", foreground="red").pack(side="left", padx=(2, 0))
        
        name_frame = tb.Frame(form_frame)
        name_frame.grid(row=0, column=1, sticky="w", pady=5, padx=(0, 5))

        name_entry = tb.Entry(name_frame, width=20)
        name_entry.pack(side="left")
        self.driver_entries.append(name_entry)
        self.driver_name_entry = name_entry

        from_label = tb.Frame(name_frame)
        from_label.pack(side="left", padx=(10, 2))
        ttk.Label(from_label, text="من (بداية العمل):").pack(side="left")
        ttk.Label(from_label, text="*", foreground="red").pack(side="left", padx=(2, 0))

        self.driver_from_picker = CustomDatePicker(name_frame)
        self.driver_from_picker.pack(side="left", padx=(0, 10))

        ttk.Label(name_frame, text="إلى (نهاية العمل):").pack(side="left", padx=(5, 2))
        self.driver_to_picker = CustomDatePicker(name_frame)
        self.driver_to_picker.pack(side="left")

        # --- عنوان السائق ---
        address_label_frame = tb.Frame(form_frame)
        address_label_frame.grid(row=1, column=0, sticky="e", pady=5, padx=(10, 5))
        ttk.Label(address_label_frame, text="عنوان السائق:").pack(side="left")
        # إذا أردت وضع نجمة فقط للحقول الإلزامية أضفها بهذا الشكل:
        ttk.Label(address_label_frame, text=" ", foreground="red").pack(side="left", padx=(2, 0))

        address_entry = tb.Entry(form_frame, width=60)
        address_entry.grid(row=1, column=1, sticky="w", pady=5)
        self.driver_entries.append(address_entry)

        # --- رقم الهاتف ---
        phone_label_frame = tb.Frame(form_frame)
        phone_label_frame.grid(row=2, column=0, sticky="e", pady=5, padx=(10, 5))
        ttk.Label(phone_label_frame, text="رقم الهاتف:").pack(side="left")
        ttk.Label(phone_label_frame, text=" ", foreground="red").pack(side="left", padx=(2, 0))

        phone_entry = tb.Entry(form_frame, width=60)
        phone_entry.grid(row=2, column=1, sticky="w", pady=5)
        self.driver_entries.append(phone_entry)

        # --- تسجيل العمل ---
        contract_label_frame = tb.Frame(form_frame)
        contract_label_frame.grid(row=3, column=0, sticky="e", pady=5, padx=(10, 5))
        ttk.Label(contract_label_frame, text="تسجيل العمل:").pack(side="left")
        ttk.Label(contract_label_frame, text="*", foreground="red").pack(side="left", padx=(2, 0))

        contract_combo = ttk.Combobox(form_frame, values=["Vollzeit", "Teilzeit", "Geringfügig"], state="readonly", width=53, height=10, justify="left")
        contract_combo.grid(row=3, column=1, sticky="w", pady=5)

        self.driver_entries.append(contract_combo)
        self.contract_type_combo = contract_combo

        # --- السيارة + من + إلى ---
        car_label_frame = tb.Frame(form_frame)
        car_label_frame.grid(row=4, column=0, sticky="e", pady=5, padx=(10, 5))
        ttk.Label(car_label_frame, text="السيارة (رقم اللوحة):").pack(side="left")
        ttk.Label(car_label_frame, text=" ", foreground="red").pack(side="left", padx=(2, 0))

        car_frame = tb.Frame(form_frame)
        car_frame.grid(row=4, column=1, sticky="w", pady=5)

        self.driver_car_plate_combo = ttk.Combobox(
            car_frame,
            values=self._get_available_cars_for_drivers(),
            state="readonly",
            width=18
        )
        self.driver_car_plate_combo.pack(side="left")

        from_label_frame = tb.Frame(car_frame)
        from_label_frame.pack(side="left", padx=(5, 2))
        ttk.Label(from_label_frame, text="من:").pack(side="left")
        # ttk.Label(from_label_frame, text="*", foreground="red").pack(side="left", padx=(2, 0))

        self.driver_car_from_picker = CustomDatePicker(car_frame)
        self.driver_car_from_picker.pack(side="left", padx=(0, 5))

        ttk.Label(car_frame, text="إلى:").pack(side="left", padx=(5, 2))
        self.driver_car_to_picker = CustomDatePicker(car_frame)
        self.driver_car_to_picker.pack(side="left")

        # --- ملاحظات ---
        notes_label_frame = tb.Frame(form_frame)
        notes_label_frame.grid(row=5, column=0, sticky="e", pady=5, padx=(10, 5))
        ttk.Label(notes_label_frame, text="ملاحظات:").pack(side="left")
        ttk.Label(notes_label_frame, text=" ", foreground="red").pack(side="left", padx=(2, 0))

        notes_entry = tb.Entry(form_frame, width=60)
        notes_entry.grid(row=5, column=1, sticky="w", pady=5)
        self.driver_entries.append(notes_entry)

        # زر الحفظ
        buttons_frame = tb.Frame(form_frame)
        buttons_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(
            buttons_frame,
            text="💾 حفظ",
            style="Green.TButton",
            command=self._save_driver
        ).pack(ipadx=30)

        # ==== جدول عرض السائقين ====
        table_frame = ttk.LabelFrame(frame, text="🚗 قائمة السائقين المسجلين", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tree_frame = tb.Frame(table_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = (
            "id", "name", "address", "phone",
            "car_received_date", "employment_end_date",
            "contract_type",
            "assigned_plate", "plate_from", "plate_to",
            "issues"
        )

        labels = [
            "", "اسم السائق", "العنوان", "الهاتف",
            "من", "إلى",
            "نوع العقد",
            "رقم اللوحة", "تاريخ استلام السيارة", "تاريخ تسليم السيارة",
            "ملاحظات"
        ]

        self.driver_table = ttk.Treeview(tree_frame, columns=columns, show="headings", height=6)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.driver_table.yview, style="TScrollbar")
        self.driver_table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.driver_table.column("id", width=0, stretch=False)
        self.driver_table.heading("id", text="")
        self.driver_table.reload_callback = self._load_driver_table_data
        self.driver_table.pack(side="left", fill="both", expand=True)

        self.configure_tree_columns(self.driver_table, labels)
        self.apply_alternate_row_colors(self.driver_table)

        bottom_controls = tb.Frame(table_frame)
        bottom_controls.pack(fill="x", pady=(10, 10))

        # حقل البحث
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.driver_table)

        # أزرار المنتصف
        buttons_frame = tb.Frame(bottom_controls)
        buttons_frame.pack(side="left", expand=True)

        inner_buttons = tb.Frame(buttons_frame)
        inner_buttons.pack(anchor="center", padx=(0, 300))

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self._print_driver_table("current")).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📁 عرض السائقين المؤرشفين", style="info.TButton",
                   command=self._toggle_archived_drivers_window).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📁 أرشيف قيادة السيارات", style="info.TButton",
                   command=self._toggle_driver_car_assignments_archive).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📝 تعديل السائق", style="Purple.TButton",
                   command=self._edit_driver_record).pack(side="left", padx=10)

        self._load_driver_table_data()
        self.driver_table.update_idletasks()
        self.configure_tree_columns(self.driver_table, labels)

        return frame

    def _save_driver(self):
        data = [e.get().strip() for e in self.driver_entries]

        driver_name = data[0]
        driver_from = self.driver_from_picker.get().strip()
        driver_to = self.driver_to_picker.get().strip()

        # --- التحقق من الحقول الإلزامية ---
        missing_fields = []

        if not driver_name:
            missing_fields.append("اسم السائق")
        if not driver_from:
            missing_fields.append("تاريخ بداية العمل")
        if not self.contract_type_combo.get().strip():
            missing_fields.append("نوع العقد")

        if missing_fields:
            self.show_info_popup("تنبيه", f"يرجى تعبئة الحقول التالية:\n- " + "\n- ".join(missing_fields))
            return

        # --- معلومات السيارة ---
        assigned_plate = self.driver_car_plate_combo.get().strip()
        plate_from = self.driver_car_from_picker.get().strip()
        plate_to = self.driver_car_to_picker.get().strip()

        if plate_from and driver_from:
            try:
                d_from = datetime.strptime(driver_from, "%Y-%m-%d")
                p_from = datetime.strptime(plate_from, "%Y-%m-%d")
                if p_from < d_from:
                    self.show_info_popup("تنبيه", "تاريخ استلام السيارة يجب أن يكون في نفس يوم بداية العمل أو بعده.")
                    return
            except ValueError:
                pass  # تجاهل الخطأ إن كانت التواريخ غير صالحة

        # التحقق من أن السيارة وتاريخ من إجباريان
        if assigned_plate and not plate_from:
            self.show_info_popup("تنبيه", "يرجى إدخال تاريخ استلام السيارة.")
            return

        if plate_from and not assigned_plate:
            self.show_info_popup("تنبيه", "يرجى اختيار رقم اللوحة.")
            return

        if plate_from and plate_to:
            if not self.validate_date_range(plate_from, plate_to, context="السيارة"):
                return

        # لم نعد نستخدم license_plate
        if driver_from and driver_to:
            if not self.validate_date_range(driver_from, driver_to, context="العمل"):
                return

        if not driver_name:
            self.show_info_popup("تنبيه", "يرجى إدخال اسم السائق.")
            return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()

                # التحقق من التكرار
                c.execute("""
                    SELECT 1 FROM drivers
                    WHERE name = ? AND (employment_end_date IS NULL OR employment_end_date = '' OR date(employment_end_date) > date('now'))
                """, (driver_name,))
                if c.fetchone():
                    self.show_info_popup("تنبيه", f"السائق '{driver_name}' لديه عقد حالي لم ينته بعد.")
                    return

                # حفظ السائق
                c.execute("""
                    INSERT INTO drivers (
                        name, address, phone,
                        car_received_date, employment_end_date,
                        assigned_plate, plate_from, plate_to,
                        issues, contract_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    driver_name, data[1], data[2],
                    driver_from, driver_to,
                    assigned_plate if assigned_plate else None,
                    plate_from if plate_from else None,
                    plate_to if plate_to else None,
                    data[4],  # الملاحظات
                    data[3]   # نوع العقد
                ))
                conn.commit()

        except Exception as e:
            self.show_info_popup("خطأ", f"فشل الحفظ:\n{e}")
            return

        for e in self.driver_entries:
            e.delete(0, tb.END)
        self.driver_from_picker.entry.delete(0, tb.END)
        self.driver_to_picker.entry.delete(0, tb.END)

        self.contract_type_combo.set("")

        self.driver_car_plate_combo.set("")
        self.driver_car_from_picker.entry.delete(0, tb.END)
        self.driver_car_to_picker.entry.delete(0, tb.END)

        # أرشفة العلاقة إذا تم إدخال تاريخ تسليم السيارة
        if assigned_plate and plate_from and plate_to:
            archived_at = datetime.now().strftime("%Y-%m-%d")
            try:
                with sqlite3.connect("medicaltrans.db") as conn:
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO driver_car_assignments_archive (
                            driver_id, driver_name, assigned_plate,
                            plate_from, plate_to, archived_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        self._get_last_driver_id(),  # سنضيف هذه الدالة بعد قليل
                        driver_name,
                        assigned_plate,
                        plate_from,
                        plate_to,
                        archived_at
                    ))
                    # تفريغ السيارة في جدول السائقين
                    c.execute("""
                        UPDATE drivers SET
                            assigned_plate = NULL,
                            plate_from = NULL,
                            plate_to = NULL
                        WHERE name = ?
                    """, (driver_name,))
                    conn.commit()
            except Exception as e:
                self.show_info_popup("خطأ", f"⚠️ فشل أرشفة علاقة السيارة:\n{e}")

        self._load_driver_table_data()
        self.show_info_popup("✔️ تم الحفظ", f"✅ تم حفظ السائق: {driver_name}")
        self._load_car_data()
        self._refresh_driver_comboboxes()
        self._refresh_driver_comboboxes()

    def _get_last_driver_id(self):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(id) FROM drivers")
            row = c.fetchone()
            return row[0] if row and row[0] else None

    def _edit_driver_record(self):
        selected = self.driver_table.selection()
        if not selected:
            self.show_info_popup("تنبيه", "يرجى اختيار سائق أولاً.")
            return

        values = self.driver_table.item(selected[0], "values")
        driver_id = values[0]
        name = values[1]
        address = values[2]
        phone = values[3]
        date_from = values[4]
        date_to = values[5]
        contract_type = values[6]
        assigned_plate = values[7] if len(values) > 7 else ""
        plate_from = values[8] if len(values) > 8 else ""
        plate_to = values[9] if len(values) > 9 else ""

        if not assigned_plate or assigned_plate.lower() == "none":
            assigned_plate = "🔓 بدون سيارة"

        # 🧼 تنظيف التواريخ إذا لم توجد سيارة
        if assigned_plate == "🔓 بدون سيارة":
            plate_from = ""
            plate_to = ""

        issues = values[10] if len(values) > 10 else ""

        edit_win = self.build_centered_popup("📝 تعديل بيانات السائق", 900, 350)
        main_frame = tb.Frame(edit_win, padding=15)
        main_frame.pack(fill="both", expand=True)

        entries = []

        # اسم السائق
        # اسم السائق + من + إلى في نفس السطر
        name_row = tb.Frame(main_frame)
        name_row.grid(row=0, column=0, columnspan=6, sticky="w", pady=6, padx=(50, 5))

        ttk.Label(name_row, text="اسم السائق:").pack(side="left", padx=(0, 4))
        name_entry = tb.Entry(name_row, width=20)
        name_entry.insert(0, name)
        name_entry.pack(side="left", padx=(0, 10))
        entries.append(name_entry)

        ttk.Label(name_row, text="من (بداية العمل):").pack(side="left", padx=(0, 4))
        from_picker = CustomDatePicker(name_row)
        from_picker.set(date_from)
        from_picker.pack(side="left", padx=(0, 10))

        ttk.Label(name_row, text="إلى (نهاية العمل):").pack(side="left", padx=(0, 4))
        to_picker = CustomDatePicker(name_row)
        to_picker.set(date_to)
        to_picker.pack(side="left", padx=(0, 10))

        # عنوان السائق
        ttk.Label(main_frame, text="عنوان السائق:").grid(row=1, column=0, sticky="e", padx=(10, 5), pady=6)
        address_entry = tb.Entry(main_frame, width=35)
        address_entry.insert(0, address)
        address_entry.grid(row=1, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(address_entry)

        # رقم الهاتف
        ttk.Label(main_frame, text="رقم الهاتف:").grid(row=2, column=0, sticky="e", padx=(10, 5), pady=6)
        phone_entry = tb.Entry(main_frame, width=35)
        phone_entry.insert(0, phone)
        phone_entry.grid(row=2, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(phone_entry)

        # نوع العقد
        ttk.Label(main_frame, text="نوع العقد:").grid(row=3, column=0, sticky="e", padx=(10, 5), pady=6)
        contract_combo = ttk.Combobox(main_frame, values=["Vollzeit", "Teilzeit", "Geringfügig"],
                                      state="readonly", width=30, justify="left")
        contract_combo.set(contract_type)
        contract_combo.grid(row=3, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(contract_combo)

        # السيارة + من + إلى
        ttk.Label(main_frame, text="السيارة (رقم اللوحة):").grid(row=4, column=0, sticky="e", padx=(10, 5), pady=6)
        car_row_frame = tb.Frame(main_frame)
        car_row_frame.grid(row=4, column=1, columnspan=5, sticky="w", padx=(0, 5), pady=6)

        available_plates = ["🔓 بدون سيارة"]

        # ✅ إضافة السيارة الحالية للسائق إن وُجدت
        if assigned_plate and assigned_plate not in available_plates:
            available_plates.append(assigned_plate)

        # ✅ ثم إضافة باقي السيارات غير المرتبطة بسائقين آخرين
        for plate in self._get_available_cars_for_drivers():
            if plate != assigned_plate:
                available_plates.append(plate)

        plate_combo = ttk.Combobox(car_row_frame, values=available_plates, state="readonly", width=18)
        self.plate_combo = plate_combo
        plate_combo.set(assigned_plate)
        plate_combo.pack(side="left")
        # ttk.Label(car_row_frame, text="*", foreground="red").pack(side="left", padx=(4, 10))

        from_label_frame = tb.Frame(car_row_frame)
        from_label_frame.pack(side="left", padx=(5, 2))
        ttk.Label(from_label_frame, text="من:").pack(side="left")
        # ttk.Label(from_label_frame, text="*", foreground="red").pack(side="left", padx=(2, 0))

        plate_from_picker = CustomDatePicker(car_row_frame)
        if plate_from and plate_from.lower() != "none":
            plate_from_picker.set(plate_from)
        else:
            plate_from_picker.set("")
        plate_from_picker.pack(side="left", padx=(0, 5))

        ttk.Label(car_row_frame, text="إلى:").pack(side="left", padx=(5, 2))
        plate_to_picker = CustomDatePicker(car_row_frame)
        if plate_to and plate_to.lower() != "none":
            plate_to_picker.set(plate_to)
        else:
            plate_to_picker.set("")
        plate_to_picker.pack(side="left")

        # الملاحظات
        ttk.Label(main_frame, text="ملاحظات:").grid(row=5, column=0, sticky="e", padx=(10, 5), pady=6)
        notes_entry = tb.Entry(main_frame, width=35)
        notes_entry.insert(0, issues)
        notes_entry.grid(row=5, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(notes_entry)

        def save_driver_edit_changes(edit_win):
            new_data = [e.get().strip() if hasattr(e, 'get') else e.get() for e in entries]
            new_plate = plate_combo.get().strip()
            if new_plate.startswith("🔓") or new_plate.lower() == "none":
                new_plate = ""
            new_plate_from = plate_from_picker.get().strip()
            new_plate_to = plate_to_picker.get().strip()
            if not new_plate:
                new_plate_from = ""
                new_plate_to = ""
            new_from = from_picker.get().strip()
            new_to = to_picker.get().strip()
            archived = False
            extra_message = ""

            # ✅ منع إنهاء العقد إذا لم يتم إنهاء استخدام السيارة
            if new_to and new_plate and not new_plate_to:
                self.show_info_popup("تنبيه", "❗ يجب أولاً إنهاء استخدام السيارة (إدخال تاريخ 'إلى') قبل إنهاء عقد السائق.")
                return
            # ❗ التحقق من الشروط
            if not new_plate and (new_plate_from or new_plate_to):
                self.show_info_popup("تنبيه", "❗ لا يمكن إدخال تاريخ بدون اختيار سيارة.\nيرجى إما اختيار سيارة أو حذف التواريخ.")
                return
            if new_plate and new_plate_to and not new_plate_from:
                self.show_info_popup("تنبيه", "❗ لا يمكن إدخال تاريخ تسليم (إلى) بدون إدخال تاريخ استلام (من).")
                return
            if not new_data[0]:
                self.show_info_popup("تنبيه", "يرجى إدخال اسم السائق.")
                return
            if new_from and new_to:
                if not self.validate_date_range(new_from, new_to, context="مدة العمل"):
                    return
            if new_plate_from and not new_plate:
                self.show_info_popup("تنبيه", "يرجى اختيار رقم اللوحة.")
                return
            if new_plate and not new_plate_from:
                self.show_info_popup("تنبيه", "يرجى إدخال تاريخ استلام السيارة.")
                return
            if new_plate_from and new_plate_to:
                if not self.validate_date_range(new_plate_from, new_plate_to, context="السيارة"):
                    return
            if new_plate and new_to and not new_plate_to:
                new_plate_to = new_to
                self.show_info_popup("معلومة", "✅ تم استخدام تاريخ نهاية العمل كتاريخ تسليم السيارة، لأن حقل التسليم كان فارغًا.")
            if new_plate_from and new_from:
                try:
                    d_from = datetime.strptime(new_from, "%Y-%m-%d")
                    p_from = datetime.strptime(new_plate_from, "%Y-%m-%d")
                    if p_from < d_from:
                        self.show_info_popup("تنبيه", "تاريخ استلام السيارة يجب أن يكون في نفس يوم بداية العمل أو بعده.")
                        return
                except ValueError:
                    pass

            try:
                conn = sqlite3.connect("medicaltrans.db")
                c = conn.cursor()

                # ✅ استخراج رقم اللوحة الأصلي من قاعدة البيانات
                c.execute("SELECT assigned_plate, plate_to FROM drivers WHERE id = ?", (driver_id,))
                row = c.fetchone()
                original_plate = row[0] if row else ""
                original_plate_to = row[1] if row else ""

                # ✅ لا يسمح بتغيير السيارة دون إنهاء السابقة أولًا
                if original_plate and original_plate != new_plate and not original_plate_to:
                    self.show_info_popup("تنبيه", "❗ لا يمكن تغيير السيارة الحالية قبل إدخال تاريخ تسليم لها، أو إعادة اختيار نفس السيارة إن لم ترغب بتغييرها..")
                    conn.close()
                    return

                # ✅ أرشفة السيارة القديمة
                if original_plate and new_plate != original_plate:
                    try:
                        if not new_plate_to:
                            new_plate_to = datetime.today().strftime("%Y-%m-%d")
                            extra_message = "📌 تم استخدام تاريخ اليوم كتاريخ تسليم السيارة السابقة."
                        archived_at = datetime.now().strftime("%Y-%m-%d")
                        c.execute("""
                            INSERT INTO driver_car_assignments_archive (
                                driver_id, driver_name, assigned_plate,
                                plate_from, plate_to, archived_at
                            )
                            SELECT id, name, assigned_plate, plate_from, ?, ?
                            FROM drivers
                            WHERE id = ? AND assigned_plate IS NOT NULL AND plate_from IS NOT NULL
                        """, (new_plate_to, archived_at, driver_id))
                        conn.commit()

                        c.execute("""
                            UPDATE drivers SET
                                assigned_plate = NULL,
                                plate_from = NULL,
                                plate_to = NULL
                            WHERE id = ?
                        """, (driver_id,))
                        conn.commit()
                    except Exception as e:
                        self.show_info_popup("⚠️ تنبيه", f"فشل أرشفة السيارة السابقة:\n{e}")
                        conn.close()
                        return

                # ✅ تحديث بيانات السائق بعد الأرشفة
                c.execute("""
                    UPDATE drivers SET
                        name = ?, address = ?, phone = ?,
                        car_received_date = ?, employment_end_date = ?,
                        assigned_plate = ?, plate_from = ?, plate_to = ?,
                        issues = ?, contract_type = ?
                    WHERE id = ?
                """, (
                    new_data[0], new_data[1], new_data[2],
                    new_from, new_to,
                    new_plate or None,
                    new_plate_from or None,
                    new_plate_to or None,
                    new_data[4],
                    new_data[3],
                    driver_id
                ))
                conn.commit()

                # ✅ أرشفة السيارة الجديدة فورًا إذا مكتملة
                if new_plate and new_plate_from and new_plate_to:
                    try:
                        archived_at = datetime.now().strftime("%Y-%m-%d")
                        c.execute("""
                            INSERT INTO driver_car_assignments_archive (
                                driver_id, driver_name, assigned_plate,
                                plate_from, plate_to, archived_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            driver_id,
                            new_data[0],
                            new_plate,
                            new_plate_from,
                            new_plate_to,
                            archived_at
                        ))
                        c.execute("""
                            UPDATE drivers SET
                                assigned_plate = NULL,
                                plate_from = NULL,
                                plate_to = NULL
                            WHERE id = ?
                        """, (driver_id,))
                        conn.commit()
                        archived = True
                    except Exception as archive_err:
                        self.show_info_popup("⚠️ تنبيه", f"لم يتم أرشفة العلاقة:\n{archive_err}")

                conn.close()

                # ✅ أرشفة عند نهاية العمل إن لم تتم الأرشفة مسبقًا
                if not archived and new_plate and new_plate_from and (new_plate_to or new_to):
                    try:
                        archived_to = new_plate_to or new_to
                        archived_at = datetime.now().strftime("%Y-%m-%d")
                        conn = sqlite3.connect("medicaltrans.db")
                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO driver_car_assignments_archive (
                                driver_id, driver_name, assigned_plate,
                                plate_from, plate_to, archived_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            driver_id,
                            new_data[0],
                            new_plate,
                            new_plate_from,
                            archived_to,
                            archived_at
                        ))
                        c.execute("""
                            UPDATE drivers SET
                                assigned_plate = NULL,
                                plate_from = NULL,
                                plate_to = NULL
                            WHERE id = ?
                        """, (driver_id,))
                        conn.commit()
                        conn.close()
                        if not new_plate_to and new_to:
                            self.show_info_popup("معلومة", "✅ تم استخدام تاريخ نهاية العمل كتاريخ تسليم السيارة.")
                    except Exception as archive_err:
                        self.show_info_popup("⚠️ تنبيه", f"فشل أرشفة العلاقة:\n{archive_err}")

                # ✅ التحديث النهائي وإغلاق النافذة
                self._load_driver_table_data()
                self.driver_table.reload_callback()
                self._load_car_data()
                self._refresh_driver_comboboxes()
                edit_win.destroy()
                message = "✅ تم تعديل بيانات السائق بنجاح."
                if extra_message:
                    message += f"\n{extra_message}"
                self.show_info_popup("✔️ تم التعديل", message)

            except Exception as e:
                self.show_info_popup("خطأ", f"فشل التعديل:\n{e}")

        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=6, pady=20)

        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=lambda: save_driver_edit_changes(edit_win)).pack(anchor="center", ipadx=10)

        main_frame.columnconfigure(1, weight=1)

    def _open_weekly_schedule_dialog(self):
        # إنشاء نافذة مخصصة بدلاً من استخدام simpledialog
        dialog = tb.Toplevel(self)
        dialog.title("إنشاء برنامج أسبوعي")
        dialog.geometry("450x250")
        dialog.transient(self)
        dialog.grab_set()

        # الإطار الرئيسي
        main_frame = tb.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # حقل إدخال اسم السائق
        ttk.Label(main_frame, text="اسم السائق:").grid(row=0, column=0, sticky="w", pady=5)
        driver_entry = tb.Entry(main_frame, width=30)
        driver_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # حقل إدخال تاريخ البداية (معدل)
        ttk.Label(main_frame, text="تاريخ البداية (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", pady=5)
        self.schedule_start_picker = CustomDatePicker(main_frame)
        self.schedule_start_picker.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.schedule_start_picker.entry.configure(justify="left")

        # زر التوليد
        def generate_schedule():
            driver_name = driver_entry.get().strip()
            start_date = self.schedule_start_picker.get().strip()

            if not driver_name or not start_date:
                self.show_info_popup("تنبيه", "يرجى إدخال كافة الحقول.")
                return

            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
                return

            try:
                conn = sqlite3.connect("medicaltrans.db")
                c = conn.cursor()
                weekly_entries = {}

                for i in range(5):
                    current_date = (start_date_obj + timedelta(days=i)).strftime("%Y-%m-%d")

                    if self.is_on_vacation(driver_name, current_date, "سائق") or self.is_calendar_event(current_date):
                        continue

                    c.execute("""
                        SELECT doctor_name, lab_name, time_window, materials, doctor_address
                        FROM driver_tasks
                        WHERE driver_name = ? AND task_date = ?
                    """, (driver_name, current_date))
                    rows = c.fetchall()

                    rows = [row for row in rows if not self.is_on_vacation(row[0], current_date, "طبيب")]

                    if rows:
                        daily_tasks = [
                            [f"{row[0]} / {row[1]}", row[2], row[3], row[4]]
                            for row in rows
                        ]
                        weekly_entries[i] = daily_tasks

                conn.close()

                if not weekly_entries:
                    self.show_info_popup("ملاحظة", "لا توجد مهام لهذا الأسبوع.")
                    return

                filename = f"{driver_name}_schedule_{start_date}.pdf".replace(" ", "_")
                generate_weekly_schedule(driver_name, start_date, weekly_entries, filename)

                dialog.destroy()
                self.show_info_popup("تم", f"✅ تم توليد الملف:\n{filename}")

            except Exception as e:
                self.show_info_popup("خطأ", f"حدث خطأ أثناء التوليد:\n{e}")

        # إطار الأزرار
        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15, sticky="ew")

        ttk.Button(
            btn_frame,
            text="🖨️ توليد الجدول",
            style="Green.TButton",
            command=generate_schedule
        ).pack(side="left", padx=10, expand=True, fill="x")

        ttk.Button(
            btn_frame,
            text="إلغاء",
            style="Orange.TButton",
            command=dialog.destroy
        ).pack(side="left", padx=10, expand=True, fill="x")

        # تكوين أوزان الأعمدة
        main_frame.columnconfigure(1, weight=1)

    def _build_calendar_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)

        # ===== قسم إضافة حدث تقويم =====
        calendar_event_frame = tb.LabelFrame(frame, text="إضافة حدث تقويمي", padding=10)
        calendar_event_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        # نوع الحدث أو العطلة + الوصف / الملاحظات
        row0_frame = tb.Frame(calendar_event_frame)
        row0_frame.pack(fill="x", pady=5)

        ttk.Label(row0_frame, text="نوع الحدث أو العطلة:").pack(side="left", padx=(5, 5))
        self.event_type_combo = ttk.Combobox(row0_frame, values=AUSTRIAN_HOLIDAYS, state="readonly", width=30, justify="left")
        self.event_type_combo.pack(side="left", padx=(0, 15))

        ttk.Label(row0_frame, text="الوصف / الملاحظات:").pack(side="left", padx=(20, 5))
        self.event_desc_text = tb.Text(row0_frame, width=60, height=3, wrap="word")
        self.event_desc_text.pack(side="left", padx=(0, 10))
        self.event_desc_text.tag_configure("left", justify="left")
        self.event_desc_text.insert("1.0", "")
        self.event_desc_text.tag_add("left", "1.0", "end")

        # صف التاريخ من - إلى + زر الحفظ
        row1_frame = tb.Frame(calendar_event_frame)
        row1_frame.pack(fill="x", pady=10)

        ttk.Label(row1_frame, text="من:").pack(side="left", padx=(5, 2))
        self.start_date_entry = CustomDatePicker(row1_frame)
        self.start_date_entry.entry.configure(justify="left")
        self.start_date_entry.pack(side="left", padx=(0, 10))

        ttk.Label(row1_frame, text="إلى:").pack(side="left", padx=(5, 2))
        self.end_date_entry = CustomDatePicker(row1_frame)
        self.end_date_entry.entry.configure(justify="left")
        self.end_date_entry.pack(side="left", padx=(0, 10))

        save_btn = ttk.Button(
            row1_frame,
            text="💾 حفظ الحدث في التقويم",
                 style="Green.TButton",
            command=self._save_calendar_event
        )
        save_btn.pack(side="left", padx=(10, 0))

        # ===== إضافة إجازة =====
        vacation_frame = tb.LabelFrame(frame, text="إضافة إجازة", padding=10)
        vacation_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        # إعادة ترتيب العناصر: النوع ← الاسم ← من ← إلى (من اليسار إلى اليمين)
        ttk.Label(vacation_frame, text="النوع:").grid(row=0, column=0, sticky="w", padx=(5, 2))
        self.vac_type = ttk.Combobox(vacation_frame, values=["سائق", "طبيب"], state="readonly", width=15, height=10, justify="left")
        self.vac_type.grid(row=0, column=1, padx=5, pady=5)
        self.vac_type.bind("<<ComboboxSelected>>", self._load_vacation_names)

        ttk.Label(vacation_frame, text="الاسم:").grid(row=0, column=2, sticky="w", padx=(5, 2))
        self.vac_name = ttk.Combobox(vacation_frame, values=[""], state="readonly", width=30, height=10, justify="left")
        self.vac_name.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(vacation_frame, text="من:").grid(row=0, column=4, sticky="w", padx=(5, 2))
        self.vac_start = CustomDatePicker(vacation_frame)
        self.vac_start.grid(row=0, column=5, padx=5, pady=5)

        ttk.Label(vacation_frame, text="إلى:").grid(row=0, column=6, sticky="w", padx=(5, 2))
        self.vac_end = CustomDatePicker(vacation_frame)
        self.vac_end.grid(row=0, column=7, padx=5, pady=5)

        btns_frame = tb.Frame(vacation_frame)
        btns_frame.grid(row=2, column=0, columnspan=8, pady=10)

        # تأطير داخلي لمركزة الأزرار أفقياً
        inner_btns = tb.Frame(btns_frame)
        inner_btns.pack(anchor="center")  # المنتصف تمامًا

        ttk.Button(
            inner_btns,
            text="💾 حفظ الإجازة",
              style="Orange.TButton",
            command=self._save_vacation
        ).pack(side="left", padx=10, ipadx=20)        

        # ===== جدول الأحداث المجدولة =====
        events_frame = tb.LabelFrame(frame, text="الأحداث المجدولة", padding=10)
        events_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        tree_frame = tb.Frame(events_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "title", "description", "start", "end")
        self.calendar_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=5)
        self.calendar_tree.column("id", width=0, stretch=False)
        self.calendar_tree.heading("id", text="")
        self.calendar_tree.reload_callback = self._load_calendar_events
        self._load_calendar_events()  # تحميل البيانات الأصلية
        self.calendar_tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.calendar_tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.calendar_tree.xview)
        hsb.pack(side="bottom", fill="x")

        self.setup_tree_scrollbars(self.calendar_tree, vsb, hsb)
        self.configure_tree_columns(self.calendar_tree, ["", "نوع الحدث", "ملاحظات", "من", "إلى"])

        bottom_controls = tb.Frame(events_frame)
        bottom_controls.pack(fill="x", pady=(10, 10))

        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.calendar_tree, query_callback=self._load_calendar_events)

        buttons_frame = tb.Frame(bottom_controls)
        buttons_frame.pack(side="left", expand=True)

        inner_buttons = tb.Frame(buttons_frame)
        inner_buttons.pack(anchor="center", padx=(0, 300))

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self._print_calendar_table("current")).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📁 عرض الأحداث المؤرشفة", style="info.TButton",
                   command=self._toggle_archived_calendar_window).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📝 تعديل الحدث", style="Purple.TButton",
                   command=self._edit_calendar_event).pack(side="left", padx=10)

        # ===== جدول الإجازات المباشر =====
        vac_table_frame = tb.LabelFrame(frame, text="الإجازات الحالية", padding=10)
        vac_table_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        tree_frame = tb.Frame(vac_table_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "person_type", "name", "start", "end")
        self.vacation_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=5)
        self.vacation_tree.column("id", width=0, stretch=False)
        self.vacation_tree.heading("id", text="")
        self.vacation_tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.vacation_tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.vacation_tree.xview)
        hsb.pack(side="bottom", fill="x")

        self.setup_tree_scrollbars(self.vacation_tree, vsb, hsb)
        self.configure_tree_columns(self.vacation_tree, ["", "النوع", "الاسم", "من", "إلى"])

        self._load_vacations_inline = self._define_vac_load_func()
        self.vacation_tree.reload_callback = self._load_vacations_inline
        self._load_vacations_inline()

        # ✅ تحميل البيانات الأصلية لدعم البحث
        self._load_original_data(
            self.vacation_tree,
            "SELECT id, person_type, name, start_date, end_date FROM vacations WHERE end_date >= date('now') ORDER BY start_date ASC"
        )

        bottom_controls = tb.Frame(vac_table_frame)
        bottom_controls.pack(fill="x", pady=(10, 10))

        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.vacation_tree, query_callback=self._load_vacations_inline)

        buttons_frame = tb.Frame(bottom_controls)
        buttons_frame.pack(side="left", expand=True)

        inner_buttons = tb.Frame(buttons_frame)
        inner_buttons.pack(anchor="center", padx=(0, 300))

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self._print_vacations_table("current")).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📁 عرض الإجازات المؤرشفة", style="info.TButton",
                   command=self._toggle_archived_vacations_window).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📝 تعديل الإجازة", style="Purple.TButton",
                   command=self._edit_vacations).pack(side="left", padx=10)

        self._load_upcoming_calendar_events()

        frame.columnconfigure(0, weight=1)

        return frame

    def _define_vac_load_func(self):
        def _load_vacations_inline():
            self.load_table_from_db(
                self.vacation_tree,
                "SELECT id, person_type, name, start_date, end_date FROM vacations WHERE end_date >= date('now') ORDER BY start_date ASC"
            )
        return _load_vacations_inline

    def _load_archived_vacations(self, treeview=None):
        today = datetime.today().strftime("%Y-%m-%d")
        tree = treeview or getattr(self, 'archived_vacations_tree', None)
        if not tree or not tree.winfo_exists():
            return
        self._load_original_data(
            tree,
            "SELECT id, person_type, name, start_date, end_date FROM vacations WHERE end_date < ? ORDER BY end_date DESC",
            (today,)
        )

    def _toggle_archived_drivers_window(self):
        if self.archived_drivers_window is not None and self.archived_drivers_window.winfo_exists():
            self.archived_drivers_window.destroy()
            self.archived_drivers_window = None
            return

        # --- الأعمدة والعناوين ---
        columns = ("id", "name", "address", "phone", "car_received_date", "employment_end_date", "issues")
        labels = ["", "اسم السائق", "العنوان", "الهاتف", "من", "إلى", "ملاحظات"]

        # --- إنشاء النافذة والجدول ---
        win, tree, _ = self.build_centered_popup("📁 السائقين المؤرشفين", 1000, 500, columns, labels)
        tree.column("id", width=0, stretch=False)
        tree.heading("id", text="")

        self.archived_drivers_window = win

        # --- قسم التحكم السفلي ---
        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        # --- يسار: حقل البحث ---
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=self._load_archived_drivers)

        # --- وسط: الأزرار ---
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", command=lambda: self.export_table_to_pdf(tree, "السائقين المؤرشفين")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", command=win.destroy).pack(side="left", padx=10)

        # --- يمين: فاصل للتوسيط ---
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        # --- تحميل البيانات ---
        self._load_archived_drivers(tree)

    def _toggle_driver_car_assignments_archive(self):
        if hasattr(self, 'archived_driver_car_window') and self.archived_driver_car_window.winfo_exists():
            self.archived_driver_car_window.destroy()
            self.archived_driver_car_window = None
            return

        columns = (
            "id", "driver_id", "driver_name", "assigned_plate",
            "plate_from", "plate_to", "archived_at"
        )
        labels = [
            "", "", "اسم السائق", "رقم اللوحة",
            "من", "إلى", "تاريخ الأرشفة"
        ]

        win = tb.Toplevel(self)
        win.title("📁 أرشيف قيادة السيارات")
        win.geometry("1000x500")
        self.archived_driver_car_window = win

        # ==== إطار الجدول ====
        table_frame = tb.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, labels)
        self.apply_alternate_row_colors(tree)

        # ==== قسم التحكم السفلي ====
        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        # حقل البحث في اليسار
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=self._load_driver_car_archive)

        # الأزرار في المنتصف
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self.export_table_to_pdf(tree, "أرشيف قيادة السيارات")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton", command=win.destroy).pack(side="left", padx=10)

        # تحميل البيانات
        self._load_driver_car_archive(tree)

    def _load_driver_car_archive(self, treeview=None):
        tree = treeview or getattr(self, 'archived_driver_car_tree', None)
        if not tree or not tree.winfo_exists():
            return

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, driver_id, driver_name, assigned_plate,
                       plate_from, plate_to, archived_at
                FROM driver_car_assignments_archive
                ORDER BY archived_at DESC
            """)
            rows = c.fetchall()

        tree._original_items = [list(row) for row in rows]
        self.fill_treeview_with_rows(tree, rows)
        self.archived_driver_car_tree = tree

    # ------ تحميل البيانات الأصلية ------
    def load_archived_drivers():
        self.reload_archived_data(
            treeview=tree,
            table_name="drivers",
            condition="employment_end_date IS NOT NULL AND employment_end_date != ''"
        )

        load_archived_drivers()

        # ===== السطر السفلي: مقسم لـ 3 أعمدة (يسار - وسط - يمين) =====
        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        # 1. يسار - حقل البحث
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=load_archived_drivers)

        # 2. وسط - الأزرار في المنتصف الحقيقي للنافذة
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", command=lambda: self.export_table_to_pdf(tree, "السائقين المؤرشفين")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", command=win.destroy).pack(side="left", padx=10)

        # 3. يمين - إطار فارغ يوازن التوسيط
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

    def _load_calendar_events(self):
        self._load_original_data(
            self.calendar_tree,
            "SELECT id, title, description, start_date, end_date FROM calendar_events WHERE end_date >= date('now') ORDER BY start_date ASC"
        )

    def _load_upcoming_calendar_events(self):
        today = datetime.today().strftime("%Y-%m-%d")
        self.load_table_from_db(
            self.calendar_tree,
            "SELECT id, title, description, start_date, end_date FROM calendar_events WHERE end_date >= ? ORDER BY start_date ASC",
            (today,)
        )

    def _load_archived_calendar_events(self, treeview=None):
        today = datetime.today().strftime("%Y-%m-%d")
        tree = treeview or getattr(self, 'archived_calendar_tree', None)
        if not tree or not tree.winfo_exists():
            return
        self._load_original_data(
            tree,
            "SELECT id, title, description, start_date, end_date FROM calendar_events WHERE end_date < ? ORDER BY end_date DESC",
            (today,)
        )

    def _toggle_archived_calendar_window(self):
        if self.archived_calendar_window and self.archived_calendar_window.winfo_exists():
            self.archived_calendar_window.destroy()
            self.archived_calendar_window = None
            return

        columns = ("id", "title", "description", "start", "end")
        labels = ["", "نوع الحدث", "الوصف", "من", "إلى"]
        win, tree, _ = self.build_centered_popup("📁 الأحداث المؤرشفة", 900, 500, columns, labels)
        tree.column("id", width=0, stretch=False)
        tree.heading("id", text="")
        self.archived_calendar_tree = tree

        # ===== السطر السفلي: مقسم لـ 3 أعمدة (يسار - وسط - يمين) =====
        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        # 1. يسار - حقل البحث
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=lambda: self._load_archived_calendar_events(tree))

        # 2. وسط - الأزرار في المنتصف الحقيقي للنافذة
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", command=lambda: self._print_calendar_table("archived")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", command=win.destroy).pack(side="left", padx=10)

        # 3. يمين - إطار فارغ يوازن التوسيط
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        self._load_archived_calendar_events(tree)

    def _toggle_archived_vacations_window(self):
        if self.archived_vacations_window and self.archived_vacations_window.winfo_exists():
            self.archived_vacations_window.destroy()
            self.archived_vacations_window = None
            return

        columns = ("id", "person_type", "name", "start", "end")
        labels = ["", "النوع", "الاسم", "من", "إلى"]
        win, tree, _ = self.build_centered_popup("📁 الإجازات المؤرشفة", 900, 500, columns, labels)
        tree.column("id", width=0, stretch=False)
        tree.heading("id", text="")
        self.archived_vacation_tree = tree

        tree.reload_callback = self._load_archived_vacations

        # ===== السطر السفلي: مقسم لـ 3 أعمدة (يسار - وسط - يمين) =====
        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        # 1. يسار - حقل البحث
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=lambda: self._load_archived_vacations(tree))

        # 2. وسط - الأزرار في المنتصف الحقيقي للنافذة
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", command=lambda: self._print_vacations_table("archived")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", command=win.destroy).pack(side="left", padx=10)

        # 3. يمين - إطار فارغ يوازن التوسيط
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        today = datetime.today().strftime("%Y-%m-%d")
        self._load_original_data(
            tree,
            "SELECT id, person_type, name, start_date, end_date FROM vacations WHERE end_date < ? ORDER BY end_date DESC",
            (today,)
        )

    def _edit_calendar_event(self):
        self._current_event_id = None

        edit_win = self.build_centered_popup("📝 تعديل الحدث", 550, 450)
        main_frame = tb.Frame(edit_win)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="نوع الحدث:").grid(row=0, column=0, sticky="w", pady=10)
        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()
        c.execute("SELECT DISTINCT title FROM calendar_events WHERE title IS NOT NULL")
        raw_titles = [row[0].strip() for row in c.fetchall()]
        conn.close()

        event_titles = sorted({t for t in raw_titles if t})

        title_combo = ttk.Combobox(main_frame, values=event_titles, state="readonly", width=30, height=10, justify="left")
        title_combo.grid(row=0, column=1, sticky="ew", pady=10, padx=5)
        title_combo.config(height=10)

        ttk.Label(main_frame, text="الوصف:").grid(row=1, column=0, sticky="nw", pady=10)
        desc_entry = tb.Text(main_frame, width=40, height=8)
        desc_entry.grid(row=1, column=1, sticky="nsew", pady=10, padx=5)

        # الحقول الأخرى
        self.start_date_picker = CustomDatePicker(main_frame)
        self.start_date_picker.grid(row=2, column=1, sticky="ew", pady=10, padx=5)
        self.start_date_picker.entry.configure(justify="left")

        self.end_date_picker = CustomDatePicker(main_frame)
        self.end_date_picker.grid(row=3, column=1, sticky="ew", pady=10, padx=5)
        self.end_date_picker.entry.configure(justify="left")

        def update_fields_from_title(event):
            selected_title = title_combo.get().strip()
            if not selected_title:
                return

            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("""
                SELECT id, description, start_date, end_date
                FROM calendar_events
                WHERE TRIM(title) = ?
                ORDER BY id DESC
                LIMIT 1
            """, (selected_title,))
            row = c.fetchone()
            conn.close()

            if row:
                self._current_event_id = row[0]
                desc_entry.delete("1.0", tb.END)
                desc_entry.insert("1.0", row[1])                
                self.start_date_picker.set(row[2])
                self.end_date_picker.set(row[3])
            else:
                self._current_event_id = None
                desc_entry.delete("1.0", tb.END)
                self.start_date_picker.set("")
                self.end_date_picker.set("")

        title_combo.bind("<<ComboboxSelected>>", update_fields_from_title)

        if event_titles:
            title_combo.set(event_titles[-1])  # تحديد أحدث عنوان تلقائيًا
            update_fields_from_title(None)     # تحميل بياناته مباشرة

        def save_calendar_edit_changes():
            new_title = title_combo.get().strip()
            new_desc = desc_entry.get("1.0", tb.END).strip()

            start_str = self.start_date_picker.get()
            end_str = self.end_date_picker.get()

            if not self.validate_date_range(start_str, end_str, context="الحدث"):
                return

            if not new_title or self._current_event_id is None:
                self.show_info_popup("تنبيه", "يرجى اختيار الحدث وتعبئة الحقول.")
                return

            if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حفظ التعديلات على الحدث؟"):
                return

            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("""
                UPDATE calendar_events
                SET title = ?, description = ?, start_date = ?, end_date = ?
                WHERE id = ?
            """, (
                new_title,
                new_desc,
                start_str,
                end_str,
                self._current_event_id
            ))
            conn.commit()
            conn.close()

            self._load_calendar_events()
            edit_win.destroy()
            self.show_info_popup("تم", "✅ تم تعديل الحدث بنجاح.")

        def delete_event():
            if self._current_event_id is None:
                self.show_info_popup("تنبيه", "يرجى اختيار الحدث أولاً.")
                return

            if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حذف الحدث؟"):
                return

            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("DELETE FROM calendar_events WHERE id = ?", (self._current_event_id,))
            conn.commit()
            conn.close()

            self._load_calendar_events()
            edit_win.destroy()
            self.show_info_popup("تم", "✅ تم حذف الحدث بنجاح.")

        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20, sticky="ew")

        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_calendar_edit_changes)\
            .pack(side="left", padx=10, expand=True, fill="x")

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def _load_vacation_names(self, event):
        selected_type = self.vac_type.get()
        if selected_type == "سائق":
            self.vac_name['values'] = self.get_driver_names()
        elif selected_type == "طبيب":
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM doctors")
                names = [row[0] for row in c.fetchall()]
            names.insert(0, "")
            self.vac_name['values'] = names
        else:
            self.vac_name['values'] = []

    def _save_vacation(self):
        person_type = self.vac_type.get()
        name = self.vac_name.get()

        # الحصول على التواريخ كنص وتحويلها
        try:
            # استخدم entry.get() لاستخراج النص
            start_str = self.vac_start.entry.get()
            end_str = self.vac_end.entry.get()
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError:
            self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return

        if not person_type or not name:
            self.show_info_popup("تنبيه", "يرجى اختيار النوع والاسم.")
            return

        if not self.validate_date_range(start_str, end_str, context="الإجازة"):
            return

        if not self.show_custom_confirm(
            "تأكيد الإجراء",
            f"⚠️ هل أنت متأكد أنك تريد حفظ إجازة {person_type} '{name}' من {start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}؟"
        ):
            return

        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO vacations (person_type, name, start_date, end_date)
            VALUES (?, ?, ?, ?)
        """, (person_type, name, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()

        self.show_info_popup("تم", f"✅ تم حفظ الإجازة بنجاح لـ {name}.")

        # ✅ إعادة تعيين القوائم
        self.vac_type.set("")
        self.vac_name.set("")
        self.vac_start.entry.delete(0, tb.END)
        self.vac_end.entry.delete(0, tb.END)

        if hasattr(self, '_load_vacations_inline'):
            self._load_vacations_inline()

    def get_driver_names(self):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT name 
                FROM drivers 
                WHERE (employment_end_date IS NULL 
                       OR employment_end_date = '' 
                       OR date(employment_end_date) >= date('now'))
                ORDER BY name ASC
            """)
            return [row[0] for row in c.fetchall()]

    def _save_fuel_expense(self):
        name = self.fuel_driver_combo.get().strip()
        date = self.fuel_date_picker.get().strip()
        amount = self.fuel_amount_entry.get().strip()

        if not name or not date or not amount:
            self.show_info_popup("تنبيه", "يرجى ملء كل الحقول.")
            return

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.show_info_popup("خطأ", "صيغة المبلغ غير صحيحة. يجب أن يكون رقمًا موجبًا.")
            return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO fuel_expenses (driver_name, date, amount) VALUES (?, ?, ?)",
                    (name, date, amount)
                )
                conn.commit()

            self.show_info_popup("✔️ تم الحفظ", "✅ تم حفظ مصروف الوقود.")
            self.fuel_driver_combo.set("")
            self.fuel_date_picker.entry.delete(0, tb.END)
            self.fuel_amount_entry.delete(0, tb.END)

        except Exception as e:
            self.show_info_popup("خطأ", f"فشل الحفظ:\n{e}")

    def _show_fuel_expense_table(self):
        win, tree, bottom_frame = self.build_centered_popup(
            "📊 مصاريف الوقود", 850, 500,
            columns=("driver", "date", "amount"),
            column_labels=["اسم السائق", "تاريخ الدفع", "المبلغ (€)"]
        )

        win.transient(self)
        win.grab_set()
        win.focus_set()

        filter_frame = tb.Frame(win)
        filter_frame.pack(fill="x", padx=10, pady=(0, 10))

        # قائمة السائقين مع "🔄 الكل"
        driver_names = ["🔄 الكل"] + self.get_driver_names()
        driver_filter_combo = ttk.Combobox(filter_frame, values=driver_names, width=20, state="readonly")
        driver_filter_combo.set("🔄 الكل")
        driver_filter_combo.pack(side="left", padx=(0, 15))

        # من تاريخ
        ttk.Label(filter_frame, text="من:").pack(side="left")
        from_picker = CustomDatePicker(filter_frame)
        from_picker.pack(side="left", padx=(0, 10))

        # إلى تاريخ
        ttk.Label(filter_frame, text="إلى:").pack(side="left")
        to_picker = CustomDatePicker(filter_frame)
        to_picker.pack(side="left", padx=(0, 10))

        # زر الفلترة
        def apply_filter():
            selected_driver = driver_filter_combo.get()
            driver_name = None if selected_driver == "🔄 الكل" else selected_driver
            from_date = from_picker.get().strip()
            to_date = to_picker.get().strip()
            self._show_filtered_fuel_expenses(driver_name, from_date, to_date)

        ttk.Button(
            filter_frame, text="🔍 تطبيق الفلتر", style="info.TButton", command=apply_filter
        ).pack(side="left", padx=(10, 0))

        # تحميل البيانات
        def load_all_fuel_expenses():
            try:
                with sqlite3.connect("medicaltrans.db") as conn:
                    c = conn.cursor()
                    c.execute("SELECT driver_name, date, amount FROM fuel_expenses ORDER BY date ASC")
                    rows = c.fetchall()
            except Exception as e:
                self.show_info_popup("خطأ", f"تعذر تحميل بيانات المصاريف:\n{e}", parent=win)
                return

            tree.delete(*tree.get_children())
            total = 0.0
            for i, row in enumerate(rows):
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                try:
                    amount_val = float(row[2])
                    total += amount_val
                    amount_str = f"{amount_val:.2f}"
                except Exception:
                    amount_str = "غير صالح"
                tree.insert("", "end", values=(row[0], row[1], amount_str), tags=(tag,))

            tree.insert("", "end", values=("", "📌 الإجمالي", f"{total:.2f}"), tags=("total",))
            tree.tag_configure("total", background="#e6e6e6", font=("Helvetica", 10, "bold"))
            self.apply_alternate_row_colors(tree)

        load_all_fuel_expenses()

        # ✅ الأزرار في أسفل النافذة بتوسيط بصري واضح
        controls_frame = tb.Frame(win)
        controls_frame.pack(fill="x", pady=10)

        center_buttons = tb.Frame(controls_frame)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self.export_table_to_pdf(tree, "تقرير مصاريف الوقود")).pack(side="left", padx=10)

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton",
                   command=win.destroy).pack(side="left", padx=10)

        def open_edit_popup():
            selected = tree.selection()
            if not selected:
                self.show_info_popup("تنبيه", "يرجى تحديد سطر يحتوي على مصروف وقود.")
                return

            values = tree.item(selected[0], "values")
            if not values or not values[0].strip():
                self.show_info_popup("تنبيه", "⚠️ السطر المحدد لا يحتوي على اسم سائق صالح.")
                return

            old_driver = values[0].strip()
            old_date = values[1].strip()
            old_amount = values[2].strip()

            edit_win = self.build_centered_popup("📝 تعديل مصروف الوقود", 400, 260)
            frm = tb.Frame(edit_win, padding=20)
            frm.pack(fill="both", expand=True)

            ttk.Label(frm, text="اسم السائق:").pack(anchor="w")
            driver_entry = ttk.Combobox(frm, values=self.get_driver_names(), width=30)
            driver_entry.set(old_driver)
            driver_entry.pack(anchor="w", pady=5)

            ttk.Label(frm, text="التاريخ:").pack(anchor="w")
            date_picker = CustomDatePicker(frm)
            date_picker.set(old_date)
            date_picker.pack(anchor="w", pady=5)

            ttk.Label(frm, text="المبلغ (€):").pack(anchor="w")
            amount_entry = tb.Entry(frm)
            amount_entry.insert(0, old_amount)
            amount_entry.pack(anchor="w", pady=5)

            def save_edit():
                new_driver = driver_entry.get().strip()
                new_date = date_picker.get().strip()
                try:
                    new_amount = float(amount_entry.get().strip())
                    if new_amount <= 0:
                        raise ValueError
                except:
                    self.show_info_popup("خطأ", "المبلغ غير صالح.")
                    return

                if not new_driver or not new_date:
                    self.show_info_popup("تنبيه", "يرجى إدخال اسم السائق والتاريخ.")
                    return

                try:
                    old_amount_val = float(old_amount)
                except:
                    self.show_info_popup("خطأ", "المبلغ القديم غير صالح.")
                    return

                try:
                    with sqlite3.connect("medicaltrans.db") as conn:
                        c = conn.cursor()
                        c.execute("""
                            SELECT id FROM fuel_expenses
                            WHERE driver_name = ? AND date = ? AND amount = ?
                            LIMIT 1
                        """, (old_driver, old_date, old_amount_val))
                        row = c.fetchone()
                        if not row:
                            self.show_info_popup("خطأ", "لم يتم العثور على السجل الأصلي.")
                            return
                        expense_id = row[0]

                        c.execute("""
                            UPDATE fuel_expenses
                            SET driver_name = ?, date = ?, amount = ?
                            WHERE id = ?
                        """, (new_driver, new_date, new_amount, expense_id))
                        conn.commit()

                    edit_win.destroy()
                    self.show_info_popup("✔️ تم", "✅ تم تعديل المصروف بنجاح.", parent=win)
                    if hasattr(self, '_refresh_driver_comboboxes'):
                        self._refresh_driver_comboboxes()
                    load_all_fuel_expenses()  # تحديث الجدول بعد التعديل مباشرة
                except Exception as e:
                    self.show_info_popup("خطأ", f"فشل التعديل:\n{e}")

            btns = tb.Frame(frm)
            btns.pack(pady=10)
            ttk.Button(btns, text="💾 حفظ", style="Green.TButton", command=save_edit).pack(side="left", padx=10, ipadx=15)
            ttk.Button(btns, text="❌ إلغاء", style="Orange.TButton", command=edit_win.destroy).pack(side="left", padx=10, ipadx=15)

        ttk.Button(center_buttons, text="✏️ تعديل", style="Purple.TButton", command=open_edit_popup).pack(side="left", padx=10)

    def _edit_fuel_expense_popup(self, driver_name, year_month):
        win, tree, bottom_frame = self.build_centered_popup(
            f"✏️ تعديل مصاريف {driver_name} – {year_month}",
            700, 450,
            columns=("id", "date", "amount", "action"),
            column_labels=["", "التاريخ", "المبلغ (€)", "حذف"]
        )

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, date, amount
                FROM fuel_expenses
                WHERE driver_name = ? AND strftime('%Y-%m', date) = ?
                ORDER BY date ASC
            """, (driver_name, year_month))
            rows = c.fetchall()

        tree._original_items = []
        tree.delete(*tree.get_children())

        for i, (row_id, date_str, amount) in enumerate(rows):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            values = (row_id, date_str, f"{amount:.2f}", "🗑 حذف")
            tree.insert("", "end", values=values, tags=(tag,))
            tree._original_items.append(values)

        self.apply_alternate_row_colors(tree)

        # حذف السجل عند الضغط على زر الحذف
        def on_click(event):
            item = tree.identify_row(event.y)
            column = tree.identify_column(event.x)
            if not item or column != "#4":
                return

            row_values = tree.item(item)["values"]
            record_id, date_val = row_values[0], row_values[1]

            if not self.show_custom_confirm("تأكيد الحذف", f"⚠️ هل تريد حذف المصروف بتاريخ {date_val}؟"):
                return

            try:
                with sqlite3.connect("medicaltrans.db") as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM fuel_expenses WHERE id = ?", (record_id,))
                    conn.commit()
                tree.delete(item)
                self.show_info_popup("✔️ تم الحذف", "✅ تم حذف المصروف بنجاح.")
            except Exception as e:
                self.show_info_popup("خطأ", f"فشل الحذف:\n{e}")

        tree.bind("<Button-1>", on_click)


    def _show_filtered_fuel_expenses(self, driver_name, start_date, end_date):
        win, tree, bottom_frame = self.build_centered_popup("📊 مصاريف محددة", 850, 500,
            columns=("driver", "date", "amount"),
            column_labels=["اسم السائق", "تاريخ الدفع", "المبلغ (€)"]
        )

        query = "SELECT driver_name, date, amount FROM fuel_expenses WHERE 1=1"
        params = []

        if driver_name:
            query += " AND driver_name = ?"
            params.append(driver_name)

        if start_date:
            query += " AND date(date) >= date(?)"
            params.append(start_date)

        if end_date:
            query += " AND date(date) <= date(?)"
            params.append(end_date)

        query += " ORDER BY date ASC"

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute(query, tuple(params))
                rows = c.fetchall()
        except Exception as e:
            self.show_info_popup("خطأ", f"حدث خطأ أثناء جلب البيانات:\n{e}", parent=win)
            win.destroy()
            return

        if not rows:
            self.show_info_popup("🚫 لا توجد بيانات", "لا توجد مصاريف مطابقة للفلتر.", parent=win)
            win.destroy()
            return

        tree._original_items = []
        tree.delete(*tree.get_children())

        total = 0.0  # ← جمع المبالغ

        for i, (driver, date_str, amount) in enumerate(rows):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'

            try:
                amount_float = float(amount)
            except (ValueError, TypeError):
                amount_float = 0.0

            total += amount_float
            formatted_amount = f"{amount_float:.2f}"

            tree.insert("", "end", values=(driver, date_str, formatted_amount), tags=(tag,))
            tree._original_items.append([driver, date_str, formatted_amount])

        # ✅ صف الإجمالي مباشرة بعد السطور العادية
        tree.insert("", "end", values=("", "📌 الإجمالي", f"{total:.2f}"), tags=("total",))
        tree.tag_configure("total", background="#e6e6e6", font=("Helvetica", 10, "bold"))

        self.apply_alternate_row_colors(tree)

        # ===== أزرار الطباعة والإغلاق في المنتصف =====
        inner_buttons = tb.Frame(bottom_frame)
        inner_buttons.pack(anchor="center")

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self.export_table_to_pdf(tree, "تقرير مصاريف مفلترة")).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="❌ إغلاق", style="danger.TButton",
                   command=win.destroy).pack(side="left", padx=10)

    def _export_monthly_fuel_pdf(self, driver_name, year_month):
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        import tempfile

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT date, amount FROM fuel_expenses
                    WHERE driver_name = ? AND strftime('%Y-%m', date) = ?
                    ORDER BY date
                """, (driver_name, year_month))
                rows = c.fetchall()

            if not rows:
                self.show_info_popup("لا يوجد بيانات", "🚫 لا توجد مصاريف لهذا الشهر.")
                return

            # تجهيز البيانات
            data = [["📅 التاريخ", "💶 المبلغ (€)"]]
            total = 0.0
            for date, amount in rows:
                data.append([date, f"{amount:.2f}"])
                total += amount

            data.append(["", ""])
            data.append(["📌 الإجمالي", f"{total:.2f} €"])

            styles = getSampleStyleSheet()
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            doc = SimpleDocTemplate(temp_file.name, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

            elements = [
                Paragraph(f"تقرير مصاريف الوقود – {driver_name} ({year_month})", styles["Title"]),
                Spacer(1, 12),
                Table(data, colWidths=[200, 150])
            ]

            elements[2].setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -2), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))

            doc.build(elements)
            os.startfile(temp_file.name)

        except Exception as e:
            self.show_info_popup("خطأ", f"فشل إنشاء PDF:\n{e}")

    def _refresh_driver_comboboxes(self):
        """تحديث جميع القوائم المنسدلة التي تعرض أسماء السائقين"""
        drivers = self.get_driver_names()

        # تحديث تبويب السيارات
        try:
            if isinstance(self.car_entries[1], ttk.Combobox):
                self.car_entries[1]['values'] = drivers
        except Exception:
            pass  # تجاهل التحديث إذا لم يكن العنصر ComboBox

        # تحديث تبويب المهام
        try:
            if isinstance(self.main_entries[2], ttk.Combobox):
                self.main_entries[2]['values'] = drivers
        except Exception:
            pass

        # ✅ تحديث تبويب مصاريف الوقود
        if hasattr(self, "fuel_driver_combo") and self.fuel_driver_combo.winfo_exists():
            self.fuel_driver_combo['values'] = drivers

        # تحديث تبويب الإجازات إذا كان النوع "سائق"
        if hasattr(self, 'vac_name') and self.vac_type.get() == "سائق":
            self.vac_name['values'] = drivers

    def get_all_license_plates(self):
        today = datetime.today().strftime("%Y-%m-%d")
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT license_plate, notes FROM car_maintenance
                WHERE notes IS NULL OR notes NOT LIKE '🚫%' 
                   OR date(substr(notes, instr(notes, 'بتاريخ') + 7, 10)) > date(?)
                ORDER BY license_plate ASC
            """, (today,))
            return [row[0] for row in c.fetchall()]

    def _save_calendar_event(self):
        title = self.event_type_combo.get().strip()

        if title == "عطلة استثنائية":
            # ✅ استخدام نافذة مخصصة بدلًا من simpledialog
            win = self.build_centered_popup("📝 أدخل اسم العطلة الاستثنائية", 420, 180)

            frame = tb.Frame(win, padding=20)
            frame.pack(fill="both", expand=True)

            ttk.Label(frame, text="📝 الرجاء إدخال اسم العطلة الاستثنائية:").pack(pady=(0, 10))

            holiday_name_var = tk.StringVar()
            name_entry = tb.Entry(frame, textvariable=holiday_name_var, width=40)
            name_entry.pack(pady=(0, 10))
            name_entry.focus()

            def confirm():
                entered = holiday_name_var.get().strip()
                if not entered:
                    self.show_info_popup("تنبيه", "يرجى إدخال اسم العطلة.")
                    return
                nonlocal title
                title = entered
                win.destroy()

            tb.Button(frame, text="✅ تأكيد", style="Green.TButton", command=confirm).pack(ipadx=20)
            win.wait_window()

            if not title or title == "عطلة استثنائية":
                return  # المستخدم أغلق النافذة أو لم يدخل الاسم

        desc = self.event_desc_text.get("1.0", tb.END).strip()

        try:
            # الحصول على التاريخ كـ string مباشرة من الـ Entry
            start_str = self.start_date_entry.get()
            end_str = self.end_date_entry.get()

            # تحويل التاريخ من تنسيق YYYY-MM-DD
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError:
            self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return

        if not self.validate_date_range(start_str, end_str, context="الحدث"):
            return

        # تحويل التواريخ إلى تنسيق قاعدة البيانات
        start = start_date.strftime("%Y-%m-%d")
        end = end_date.strftime("%Y-%m-%d")

        if not title or not start or not end:
            self.show_info_popup("تنبيه", "يرجى اختيار نوع الحدث والتاريخين.")
            return

        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO calendar_events (title, description, start_date, end_date)
            VALUES (?, ?, ?, ?)
        """, (title, desc, start, end))
        conn.commit()
        conn.close()

        self.show_info_popup("تم", f"✅ تم حفظ حدث {title} في التقويم!")

        self.event_type_combo.set("")
        self.event_desc_text.delete("1.0", tb.END)
        self.start_date_entry.entry.delete(0, tb.END)
        self.end_date_entry.entry.delete(0, tb.END)

        self._load_calendar_events()

    def show_upcoming_appointments_popup(self):
        win = self.build_centered_popup("📌 المواعيد القادمة", 700, 450)

        frame = tb.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)

        self.appointment_tree = ttk.Treeview(frame, columns=("id", "car", "type", "date"), show="headings", height=12)
        self.appointment_tree.pack(fill="both", expand=True)

        self.appointment_tree.heading("id", text="")
        self.appointment_tree.heading("car", text="رقم اللوحة")
        self.appointment_tree.heading("type", text="نوع الموعد")
        self.appointment_tree.heading("date", text="تاريخ الموعد")

        self.appointment_tree.column("id", width=0, stretch=False)
        self.appointment_tree.column("car", anchor="center")
        self.appointment_tree.column("type", anchor="center")
        self.appointment_tree.column("date", anchor="center")

        # أزرار التعديل + الأرشيف
        btns = tb.Frame(win)
        btns.pack(pady=10)

        ttk.Button(btns, text="📝 تعديل الموعد", style="Purple.TButton",
                   command=self._edit_selected_appointment).pack(side="left", padx=10)

        ttk.Button(btns, text="📁 عرض المؤرشفة", style="info.TButton",
                   command=self._show_archived_appointments_window).pack(side="left", padx=10)

        self._load_upcoming_appointments()

    def _load_upcoming_appointments(self):
        today = datetime.today().strftime("%Y-%m-%d")
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, license_plate, appointment_type, appointment_date
                FROM car_appointments
                WHERE date(appointment_date) >= date(?)
                ORDER BY appointment_date ASC
            """, (today,))
            rows = c.fetchall()

        self.appointment_tree.delete(*self.appointment_tree.get_children())
        for i, row in enumerate(rows):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.appointment_tree.insert("", "end", values=row, tags=(tag,))
        self.apply_alternate_row_colors(self.appointment_tree)

    def _edit_selected_appointment(self):
        selected = self.appointment_tree.selection()
        if not selected:
            self.show_info_popup("تنبيه", "يرجى اختيار موعد أولاً.")
            return

        values = self.appointment_tree.item(selected[0], "values")
        appt_id, plate, appt_type, appt_date = values

        win = self.build_centered_popup("📝 تعديل الموعد", 400, 250)

        frm = tb.Frame(win, padding=20)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="رقم اللوحة:").grid(row=0, column=0, sticky="e", pady=5)
        plate_entry = tb.Entry(frm)
        plate_entry.insert(0, plate)
        plate_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frm, text="نوع الموعد:").grid(row=1, column=0, sticky="e", pady=5)
        type_entry = tb.Entry(frm)
        type_entry.insert(0, appt_type)
        type_entry.grid(row=1, column=1, pady=5)

        ttk.Label(frm, text="تاريخ الموعد:").grid(row=2, column=0, sticky="e", pady=5)
        date_picker = CustomDatePicker(frm)
        date_picker.set(appt_date)
        date_picker.grid(row=2, column=1, pady=5)

        def save_appointment_edit_changes():
            new_plate = plate_entry.get().strip()
            new_type = type_entry.get().strip()
            new_date = date_picker.get().strip()

            try:
                datetime.strptime(new_date, "%Y-%m-%d")
            except:
                self.show_info_popup("خطأ", "صيغة التاريخ غير صحيحة.")
                return

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    UPDATE car_appointments
                    SET license_plate = ?, appointment_type = ?, appointment_date = ?
                    WHERE id = ?
                """, (new_plate, new_type, new_date, appt_id))
                conn.commit()

            win.destroy()
            self._load_upcoming_appointments()
            self._check_appointments()
            self.show_info_popup("تم", "✅ تم تعديل الموعد بنجاح.")

        ttk.Button(frm, text="💾 حفظ التعديلات", style="Green.TButton", command=save_appointment_edit_changes).grid(row=3, columnspan=2, pady=15)

    def _show_archived_appointments_window(self):
        win, tree, _ = self.build_centered_popup("📁 المواعيد المؤرشفة", 700, 450, columns=("id", "car", "type", "date"),
                                                 column_labels=["", "رقم اللوحة", "نوع الموعد", "تاريخ الموعد"])
        
        tree.column("id", width=0, stretch=False)
        tree.heading("id", text="")

        today = datetime.today().strftime("%Y-%m-%d")
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, license_plate, appointment_type, appointment_date
                FROM car_appointments
                WHERE date(appointment_date) < date(?)
                ORDER BY appointment_date DESC
            """, (today,))
            rows = c.fetchall()

        tree._original_items = rows
        self.fill_treeview_with_rows(tree, rows)

    def _get_available_cars_for_drivers(self):
        today = datetime.today().strftime("%Y-%m-%d")
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            # جلب السيارات التي لم يتم إخراجها من الخدمة
            c.execute("""
                SELECT license_plate FROM car_maintenance
                WHERE (notes IS NULL OR notes NOT LIKE '🚫%')
                  AND license_plate NOT IN (
                    SELECT assigned_plate FROM drivers
                    WHERE assigned_plate IS NOT NULL AND (plate_to IS NULL OR plate_to = '')
                  )
                ORDER BY license_plate ASC
            """)
            return [row[0] for row in c.fetchall()]

if __name__ == "__main__":
    setup_database()
    app = MedicalTransApp()
    app.mainloop()
