import sqlite3
import json
import datetime
import os
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import ttkbootstrap as tb
from ttkbootstrap.widgets import DateEntry
from custom_widgets import CustomDatePicker
from ttkbootstrap.style import Style

import unicodedata
from ttkwidgets.autocomplete import AutocompleteCombobox

def super_normalize(text):
    if not text:
        return ''
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    # استبدل كل أنواع الفراغات إلى فراغ عادي
    text = ''.join(' ' if unicodedata.category(c) == 'Zs' else c for c in text)
    # استبدل كل أنواع الـ dash إلى dash عادي
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
    return text.strip()

def best_match_option(val):
    valid_options = ["bis", "von - bis", "ab", "nach Anruf", "Anschl."]
    val = super_normalize(val)
    for opt in valid_options:
        if val.startswith(super_normalize(opt)):
            return opt
    return None

AUSTRIAN_HOLIDAYS = [
    "رأس السنة", "عيد الغطاس", "الجمعة العظيمة", "عيد الفصح", "عيد العمال",
    "عيد الصعود", "عيد الجسد", "العيد الوطني", "عيد جميع القديسين",
    "عيد الميلاد", "يوم القديس ستيفان", "عطلة استثنائية"
]

def get_selected_weekdays(weekday_vars: dict) -> list:
    """ترجع قائمة الأيام المفعّلة حسب المتغيرات الممررة."""
    label_map = {
        "mon": "الإثنين", "tue": "الثلاثاء", "wed": "الأربعاء",
        "thu": "الخميس", "fri": "الجمعة"
    }
    return [label_map[k] for k, (v, _, _, _) in weekday_vars.items() if v.get()]

def get_weekday_times(weekday_vars: dict, validate: bool = False) -> list:
    """ترجع قائمة الأوقات المفعّلة مع التحقق إذا طُلب ذلك."""
    results = []
    label_map = {
        "mon": "الإثنين", "tue": "الثلاثاء", "wed": "الأربعاء",
        "thu": "الخميس", "fri": "الجمعة"
    }

    for key, (active_var, type_var, from_var, to_var) in weekday_vars.items():
        if not active_var.get():
            continue

        label = label_map.get(key, key)
        typ = type_var.get()
        f = from_var.get().strip()
        t = to_var.get().strip()

        if typ == "von - bis":
            if validate:
                if not f or not t:
                    raise ValueError(f"❗ يرجى تحديد الوقت من وإلى ليوم {label}.")
                if f >= t:
                    raise ValueError(f"❗ الوقت 'إلى' يجب أن يكون بعد 'من' في يوم {label}.")
            results.append(f"{typ} {f} - {t}" if f and t else typ)
        elif typ in ["bis", "ab"]:
            if validate and not f:
                raise ValueError(f"❗ يرجى تحديد الساعة ليوم {label}.")
            results.append(f"{typ} {f}" if f else typ)
        else:
            results.append(typ)

    return results

class ToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.text = ""

    def show(self, text, x, y):
        self.hide()
        self.text = text
        if not self.text:
            return
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffe0", relief="solid", borderwidth=1,
            font=("tahoma", "8", "normal"), wraplength=400
        )
        label.pack(ipadx=1)

    def hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

# ✅ دعم datetime لـ SQLite
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat(" "))
sqlite3.register_converter("timestamp", lambda s: datetime.datetime.fromisoformat(s.decode()))

def setup_database():
    conn = sqlite3.connect("medicaltrans.db", detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()

    # الجداول كما كانت تمامًا
    c.execute("""CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        street TEXT,
        city TEXT,
        zip_code TEXT,
        materials TEXT,
        labs TEXT,
        weekdays TEXT,
        price_per_trip REAL,
        mon_time TEXT,
        tue_time TEXT,
        wed_time TEXT,
        thu_time TEXT,
        fri_time TEXT
    )""")

    try: c.execute("ALTER TABLE doctors ADD COLUMN street TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN city TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN zip_code TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN visit_type TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN phone TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN materials TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN labs TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN weekdays TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN billing_by TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN weekday_times TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE doctors ADD COLUMN price_per_trip REAL")
    except sqlite3.OperationalError: pass

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

    try: c.execute("ALTER TABLE drivers ADD COLUMN assigned_plate TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE drivers ADD COLUMN plate_from TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE drivers ADD COLUMN plate_to TEXT")
    except sqlite3.OperationalError: pass

    c.execute("""CREATE TABLE IF NOT EXISTS calendar_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT,
        start_date timestamp, end_date timestamp)""")

    c.execute("""CREATE TABLE IF NOT EXISTS driver_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_name TEXT, task_date timestamp,
        doctor_name TEXT, lab_name TEXT,
        time_window TEXT, materials TEXT, doctor_address TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS driver_car_assignments_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER,
        driver_name TEXT,
        assigned_plate TEXT,
        plate_from TEXT,
        plate_to TEXT,
        archived_at timestamp
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS car_maintenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_plate TEXT,
        autobahnpickerl_from timestamp,
        autobahnpickerl_to timestamp,
        yearly_pickerl_until timestamp,
        notes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS archived_car_maintenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_plate TEXT,
        autobahnpickerl_from timestamp,
        autobahnpickerl_to timestamp,
        yearly_pickerl_until timestamp,
        notes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS car_appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_plate TEXT,
        appointment_type TEXT,
        appointment_date timestamp
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS vacations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_type TEXT, name TEXT,
        start_date timestamp, end_date timestamp)""")

    try: c.execute("ALTER TABLE vacations ADD COLUMN notes TEXT")
    except sqlite3.OperationalError: pass

    c.execute("""CREATE TABLE IF NOT EXISTS archived_car_appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_plate TEXT,
        appointment_type TEXT,
        appointment_date timestamp
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS fuel_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_name TEXT,
        date timestamp,
        amount REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS billing_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER,
        doctor_name TEXT,
        lab_name TEXT,
        trip_date timestamp,
        price_per_trip REAL
    )""")

    try: c.execute("ALTER TABLE billing_records ADD COLUMN trip_count INTEGER")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE billing_records ADD COLUMN price_at_time REAL")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE billing_records ADD COLUMN total REAL")
    except sqlite3.OperationalError: pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            driver TEXT
        )
    """)

    # ✅ إنشاء جدول route_days
    c.execute("""
        CREATE TABLE IF NOT EXISTS route_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER,
            day TEXT,
            data TEXT
        )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS route_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_name TEXT,
        date TEXT,
        driver TEXT,
        name TEXT,
        time TEXT,
        lab TEXT,
        description TEXT,
        address TEXT,
        notes TEXT
    )
    """)

    conn.commit()
    conn.close()

class MedicalTransApp(tb.Window):
    def __init__(self):
        super().__init__(themename="lumen")  # الوضع الافتراضي

        self.title("Medicaltrans GmbH – إدارة النقل الطبي")
        self.geometry("1200x700")
        self.current_theme = "lumen"
        self.tooltip = ToolTip(self)

        self.tab_frames = {}
    
        setup_database()
        self._setup_custom_styles()
        self._build_header()
        self._build_layout()
        self._init_styles()
        self._configure_styles()
        self.notebook.select(self.tab_frames["الرئيسية"])
        self.check_warnings()
        self._check_alerts()
        self.archived_calendar_window = None
        self.archived_vacations_window = None
        self.archived_drivers_window = None
        self._check_appointments()
        self.main_preview_driver = None
        self.main_preview_days = []
        self.main_preview_index = 0
        self._selected_route_row_index = None
        self.route_driver_names = {}
        self.route_start_hours = {}

    def _init_styles(self):
        style = tb.Style()
        style.configure("RouteCard.TFrame", background="#ffffff")
        style.configure("SelectedRouteCard.TFrame", background="#f0ad4e")

    def ask_choice_dialog(self, title, message, options):
        import tkinter as tk
        from tkinter import simpledialog

        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        # محتوى الرسالة
        label = ttk.Label(dialog, text=message, justify="center", padding=20)
        label.pack()

        selected = tk.StringVar(value="")

        # أزرار الخيارات
        for opt in options:
            ttk.Button(dialog, text=opt, command=lambda o=opt: (selected.set(o), dialog.destroy())).pack(fill="x", padx=20, pady=5)

        # تموضع في الوسط
        self.center_window(dialog, 400, 200)
        dialog.wait_window()

        return selected.get()

    def center_window(self, window, width, height):
        window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

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
        self.content_frame = tb.Frame(self)
        self.content_frame.pack(fill="both", expand=True)

        # 🔁 إنشاء إطار يغلف الـNotebook ويضيف هوامش
        padded_frame = tb.Frame(self.content_frame)
        padded_frame.pack(fill="both", expand=True, padx=50, pady=(10, 5))  # ← الهامش من اليمين واليسار

        self.notebook = ttk.Notebook(padded_frame)
        self.notebook.pack(fill="both", expand=True)

        self.tab_frames = {}

        self.tab_frames["الرئيسية"] = self._build_main_tab()
        self.notebook.add(self.tab_frames["الرئيسية"], text="الرئيسية")

        self.tab_frames["الأطباء"] = self._build_doctor_tab()
        self.notebook.add(self.tab_frames["الأطباء"], text="الأطباء")

        self.tab_frames["المخابر"] = self._build_lab_tab()
        self.notebook.add(self.tab_frames["المخابر"], text="المخابر")

        self.tab_frames["السائقين"] = self._build_driver_tab()
        self.notebook.add(self.tab_frames["السائقين"], text="السائقين")

        self.tab_frames["التقويم"] = self._build_calendar_tab()
        self.notebook.add(self.tab_frames["التقويم"], text="التقويم")

        self.tab_frames["السيارات"] = self._build_car_tab()
        self.notebook.add(self.tab_frames["السيارات"], text="السيارات")
    
    def _show_tab(self, tab_key):
        if tab_key in self.tab_frames:
            self.notebook.select(self.tab_frames[tab_key])

        # إعادة تعيين الحقول "بحث" في الإطار المحدد
        selected_tab = self.tab_frames.get(tab_key)
        if selected_tab:
            for child in selected_tab.winfo_children():
                if isinstance(child, tb.Entry) and child.get() == "🔍 بحث":
                    child.delete(0, tk.END)
                    child.insert(0, "🔍 بحث")
                    child.configure(foreground="#808080")

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
                self.show_message("error", f"تاريخ نهاية {context} لا يمكن أن يكون قبل تاريخ البداية.")
                return False
        except ValueError:
            self.show_message("error", f"صيغة تاريخ {context} غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return False
        return True

    def show_warning_window(self):
        if not hasattr(self, 'active_warnings'):
            self.active_warnings = []

        columns = ("warning",)
        labels = ["🚨 قائمة التحذيرات النشطة"]

        if not labels:
            self.show_message("error", "تعذر إنشاء جدول التنبيهات. لم يتم العثور على أعمدة كافية.")
            return

        win = self.build_centered_popup("⚠️ التنبيهات الحالية", 600, 450)

        # إطار الجدول + الشريط العمودي
        tree_frame = tb.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, labels)

        # تعبئة البيانات
        tree._original_items = []
        for i, warning in enumerate(self.active_warnings):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=(warning,), tags=(tag,))
            tree._original_items.append([warning])

        self.apply_alternate_row_colors(tree)

        # الأزرار السفلية بتوسيط واضح
        controls_frame = tb.Frame(win)
        controls_frame.pack(fill="x", pady=10)

        center_buttons = tb.Frame(controls_frame)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton", command=win.destroy).pack(side="left", padx=10)

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
    
    def show_message(self, kind: str, message: str, parent=None, confirm_callback=None):
        import tkinter as tk

        root = parent or self
        win = tb.Toplevel(root)
        win.title("")
        win.transient(root)
        win.grab_set()
        win.resizable(False, False)

        # ===== الإطار الرئيسي =====
        container = tb.Frame(win, padding=20)
        container.pack(expand=True, fill="both")

        # ===== عنوان الرسالة =====
        title_map = {
            "success": "✔️ تم",
            "warning": "⚠️ تنبيه",
            "error": "❌ خطأ",
            "info": "ℹ️ معلومة",
            "confirm": "❓ تأكيد"
        }
        title = title_map.get(kind, "ℹ️ معلومة")
        ttk.Label(container, text=title, font=("Segoe UI", 12, "bold"), anchor="center", justify="center").pack(pady=(0, 10), fill="x")

        # ===== نص الرسالة =====
        justify_style = "right" if "\n" in message else "center"
        anchor_style = "center"
        ttk.Label(
            container,
            text=message,
            wraplength=400,
            justify=justify_style,
            anchor=anchor_style,
            font=("Segoe UI", 10)
        ).pack(pady=(0, 15), fill="x")

        # ===== أزرار الرسالة =====
        btn_frame = tb.Frame(container)
        btn_frame.pack()

        def close():
            win.destroy()

        def on_confirm():
            win.destroy()
            if callable(confirm_callback):
                confirm_callback()

        if kind == "confirm":
            ttk.Button(btn_frame, text="نعم", style="Primary.TButton", command=on_confirm).pack(side="left", padx=10, ipadx=10)
            ttk.Button(btn_frame, text="لا", command=close).pack(side="left", padx=10, ipadx=10)
        else:
            ttk.Button(btn_frame, text="موافق", style="Primary.TButton", command=close).pack(ipadx=10)

        # ===== إغلاق بـ Enter =====
        win.bind("<Return>", lambda e: close())

        # ===== تحديث وموضعة في المنتصف =====
        win.update_idletasks()
        w = max(win.winfo_width(), 400)
        h = win.winfo_height()
        x = root.winfo_x() + (root.winfo_width() // 2) - (w // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

        ttk.Style().configure("Primary.TButton", anchor="center")

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
            current_text = search_entry.get()
            if current_text == "🔍 بحث":  # التحقق من النص الافتراضي
                search_entry.delete(0, tk.END)
                search_var.set("")  # إعادة تعيين المتغير
                search_entry.configure(foreground="#000000")

        def on_focus_out(event):
            current_text = search_entry.get()
            if not current_text.strip():  # إذا كان الحقل فارغاً
                search_entry.delete(0, tk.END)
                search_entry.insert(0, "🔍 بحث")
                search_var.set("🔍 بحث")  # تحديث المتغير
                search_entry.configure(foreground="#808080")

        search_entry.bind("<FocusIn>", on_focus_in)
        search_entry.bind("<FocusOut>", on_focus_out)
        search_entry.configure(foreground="#808080")  # تطبيق اللون الافتراضي

        # ------ التصفية الديناميكية ------
        def filter_table(*args):
            query = search_var.get().strip().lower()
        
            # تجاهل النص الافتراضي "🔍 بحث"
            if query == "🔍 بحث":
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
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        import tempfile
        import os

        items = treeview.get_children()
        if not items:
            self.show_message("info", "🚫 لا توجد سجلات لطباعتها.")
            return

        excluded_columns = {col for col in treeview["columns"] if col == "id" or col.endswith("_id")}
        headers = [treeview.heading(col)["text"] for col in treeview["columns"] if col not in excluded_columns]
        data = [headers]

        styles = getSampleStyleSheet()
        wrapped_style = ParagraphStyle(name='Wrapped', fontName='Helvetica', fontSize=9, wordWrap='CJK')

        columns = treeview["columns"]
        for item in items:
            tags = treeview.item(item, "tags")
            row = treeview.item(item)["values"]
            filtered_row = []

            for i, cell in enumerate(row):
                col_name = columns[i]
                if col_name in excluded_columns:
                    continue

                if isinstance(cell, str):
                    cell = Paragraph(cell.replace("\n", "<br/>"), wrapped_style)
                filtered_row.append(cell)

            data.append(filtered_row)

            # ✅ إذا كان الصف هو "الإجمالي" أضف تمييز خاص له
            if "total" in tags:
                data.append(["" for _ in headers])  # فراغ لفصل الإجمالي

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        doc = SimpleDocTemplate(temp_file.name, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []

        elements.append(Paragraph(title, styles["Title"]))
        elements.append(Spacer(1, 12))

        t = Table(data, colWidths='*', repeatRows=1)
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])

        # ✅ تطبيق تنسيق خاص لصف الإجمالي إن وجد
        for i, row in enumerate(data):
            if any(isinstance(cell, str) and "📌 الإجمالي" in cell for cell in row):
                style.add("BACKGROUND", (0, i), (-1, i), colors.lightgrey)
                style.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")
                style.add("FONTSIZE", (0, i), (-1, i), 10)

        t.setStyle(style)

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
            tree.heading("#1", text=column_labels[0])
            tree.column("#1", anchor="center", width=available_width, stretch=True)
        else:
            default_col_width = int(available_width / (total_columns - 1))  # -1 لحذف id
            for i, label in enumerate(column_labels):
                col_id = f"#{i + 1}"
                tree.heading(col_id, text=label)
                if column_labels[i] == "":
                    tree.column(col_id, width=0, anchor="center", stretch=False)
                    tree.heading(col_id, text="")
                else:
                    # ✅ زيادة عرض الأعمدة الطويلة (مثل الأيام والأوقات)
                    if label in ("🗓 الأيام", "⏰ Zeit"):
                        width = 180
                    else:
                        width = default_col_width
                    tree.column(col_id, width=width, anchor="center", stretch=True)

    def _attach_tooltip_to_tree(self, tree):
        def on_motion(event):
            region = tree.identify("region", event.x, event.y)
            if region == "cell":
                rowid = tree.identify_row(event.y)
                col = tree.identify_column(event.x)
                if not rowid or not col:
                    self.tooltip.hide()
                    return

                col_index = int(col[1:]) - 1
                values = tree.item(rowid, "values")
                if col_index >= len(values):
                    self.tooltip.hide()
                    return

                value = values[col_index]
                if isinstance(value, str) and (len(value) > 30 or "\n" in value):
                    x = tree.winfo_rootx() + event.x + 20
                    y = tree.winfo_rooty() + event.y + 20
                    self.tooltip.show(str(value), x, y)
                else:
                    self.tooltip.hide()
            else:
                self.tooltip.hide()

        tree.bind("<Motion>", on_motion)

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

    def build_table_window_with_search(
        self,
        title: str,
        width: int,
        height: int,
        columns: list,
        column_labels: list,
        reload_callback: callable,
        export_title: str = "",
        extra_buttons: list = None  # [(label, command, style), ...]
    ):
        """
        ينشئ نافذة منبثقة تحتوي على جدول منسق مع شريط بحث وأزرار متمركزة.

        1. النافذة متمركزة باستخدام build_centered_popup.
        2. يتم إنشاء Treeview يدويًا مع Scrollbar أنيق style="TScrollbar".
        3. يتم إخفاء عمود ID تلقائيًا إن كان label == "".
        4. يتم توزيع الأعمدة بالتساوي باستخدام configure_tree_columns.
        5. يتم تطبيق ألوان صفوف متناوبة باستخدام apply_alternate_row_colors.
        6. يتم إنشاء قسم سفلي بـ 3 أجزاء:
            - search_frame على اليسار.
            - center_buttons في المنتصف.
            - right_spacer لموازنة التمركز.
        7. يتم وضع زر إغلاق أحمر بشكل افتراضي.
        8. يمكن إضافة أزرار إضافية عبر extra_buttons.
        9. يتم تحميل البيانات باستخدام reload_callback.
        """

        # نافذة متمركزة
        win = self.build_centered_popup(title, width, height)
    
        # ==== إطار الجدول ====
        table_frame = tb.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # توزيع الأعمدة + إخفاء ID + محاذاة وسط
        self.configure_tree_columns(tree, column_labels)

        # ألوان صفوف بالتناوب
        self.apply_alternate_row_colors(tree)

        # ==== القسم السفلي بثلاثة أجزاء ====
        bottom_controls = tb.Frame(win)
        bottom_controls.pack(fill="x", pady=10, padx=10)

        # يسار: حقل البحث
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left")
        self.attach_search_filter(search_frame, tree, query_callback=reload_callback)

        # وسط: الأزرار المتمركزة
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        if export_title:
            ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton",
                       command=lambda: self.export_table_to_pdf(tree, export_title)).pack(side="left", padx=10)

        # أزرار إضافية إن وجدت
        if extra_buttons:
            for label, command, style in extra_buttons:
                ttk.Button(center_buttons, text=label, style=style, command=lambda cmd=command: cmd(tree)).pack(side="left", padx=10)

        # زر إغلاق أحمر دائمًا
        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton", command=win.destroy).pack(side="left", padx=10)

        # يمين: فراغ موازن
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        # تحميل البيانات
        reload_callback(tree)
        tree.event_generate("<<TreeviewSelect>>")

    def on_archive_close(self, window):
        window.destroy()
        self._load_car_data()  # أو أي دالة تحديث للجدول الرئيسي
        self._load_driver_table_data()

    def _preview_week_schedule(self):
        import sqlite3
        from datetime import datetime, timedelta

        driver = self.main_driver_combo.get().strip()
        if not driver:
            self.show_message("warning", "يرجى اختيار اسم السائق أولاً.")
            return

        win, tree, bottom_frame = self.build_centered_popup(
            "📅 جدول المهام الأسبوعي", 950, 500,
            columns=("day", "date", "doctor", "lab", "time", "materials", "address"),
            column_labels=["اليوم", "التاريخ", "الطبيب", "المخبر", "Zeit", "الوصف", "العنوان"]
        )

        tree._original_items = []

        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday())

        weekdays_map = {
            0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة"
        }

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()

            for i in range(7):
                current_date = start_of_week + timedelta(days=i)
                weekday_index = current_date.weekday()
                if weekday_index > 4:
                    continue  # تجاهل السبت والأحد

                date_str = current_date.strftime("%Y-%m-%d")

                # عطلة رسمية؟
                c.execute("SELECT 1 FROM holidays WHERE date = ?", (date_str,))
                if c.fetchone():
                    continue

                # عطلة سائق؟
                c.execute("""
                    SELECT 1 FROM vacations
                    WHERE name = ? AND ? BETWEEN from_date AND to_date
                """, (driver, date_str))
                if c.fetchone():
                    continue

                # إجازة طبيب؟
                c.execute("""
                    SELECT doctor FROM driver_tasks
                    WHERE driver = ? AND date = ?
                """, (driver, date_str))
                doctors = c.fetchall()

                skip_day = False
                for (doc,) in doctors:
                    c.execute("""
                        SELECT 1 FROM vacations
                        WHERE name = ? AND ? BETWEEN from_date AND to_date
                    """, (doc, date_str))
                    if c.fetchone():
                        skip_day = True
                        break

                if skip_day:
                    continue

                # المهام الصالحة لهذا اليوم
                c.execute("""
                    SELECT doctor, lab, time, materials, address
                    FROM driver_tasks
                    WHERE driver = ? AND date = ?
                    ORDER BY time
                """, (driver, date_str))
                rows = c.fetchall()

                for row in rows:
                    tree.insert("", "end", values=(
                        weekdays_map[weekday_index],
                        current_date.strftime("%d/%m/%Y"),
                        *row
                    ))
                    tree._original_items.append([
                        weekdays_map[weekday_index],
                        current_date.strftime("%d/%m/%Y"),
                        *row
                    ])

        self.apply_alternate_row_colors(tree)

    def _print_week_schedule(self):
        driver_name = self.main_entries[2].get().strip()
        if not driver_name:
            self.show_message("warning", "يرجى إدخال اسم السائق.")
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
            self.show_message("error", f"حدث خطأ أثناء الطباعة:\n{e}")

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

    def _print_calendar_table(self, mode, tree=None):
        if mode == "current":
            table = self.calendar_tree
            title = "الأحداث المجدولة"
        elif mode == "archived":
            table = tree
            if not table or not table.winfo_exists():
                return
            title = "الأحداث المؤرشفة"
        else:
            return  # تجنب حالات غير معروفة

        self.export_table_to_pdf(table, title)

    def _build_main_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)

        # === الإطار الأيسر لإدارة Routes ===
        left_frame = tb.Frame(frame)
        left_frame.pack(side="left", fill="y", padx=(10, 5), pady=10)

        # ✅ إطار مركزي لتوسيط البطاقات
        cards_wrapper = tb.Frame(frame)
        cards_wrapper.pack(fill="x", pady=(0, 10))

        self.routes_card_frame = tb.Frame(cards_wrapper)
        self.routes_card_frame.pack()

        # ✅ أزرار التحكم أسفل البطاقات
        controls_wrapper = tb.Frame(frame)
        controls_wrapper.pack(fill="x", pady=(5, 15))

        controls_frame = tb.Frame(controls_wrapper)
        controls_frame.pack()

        self.add_edit_route_btn = ttk.Button(
            controls_frame,
            text="➕ إضافة Route",
            style="Accent.TButton",
            command=self._on_add_edit_route_btn
        )
        self.add_edit_route_btn.pack(side="left", padx=5)

        self.delete_route_btn = ttk.Button(
            controls_frame,
            text="🗑 حذف Route",
            style="danger.TButton",
            command=self._delete_route,
            state="disabled"
        )
        self.delete_route_btn.pack(side="left", padx=5)

        # === الإطار الأيمن: عرض تفاصيل Route المحددة ===
        right_frame = tb.LabelFrame(frame, text="🚚 عرض Route", padding=10)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        # ✅ Canvas لعرض الجدول
        self.route_main_canvas = tk.Canvas(right_frame, bg="white", width=1100, height=400)
        # self.route_main_canvas.bind("<Configure>", lambda e: self._draw_route_main_canvas("-", "-"))
        self.route_main_canvas.pack(fill="both", expand=True)

        # ✅ أزرار التنقل والطباعة
        self.route_main_btns_frame = tb.Frame(right_frame)
        self.route_main_btns_frame.pack(pady=10)

        self.route_main_prev_btn = ttk.Button(
            self.route_main_btns_frame, text="⬅️ اليوم السابق",
            command=self._load_prev_route_day
        )
        self.route_main_prev_btn.pack(side="left", padx=5)

        self.route_main_next_btn = ttk.Button(
            self.route_main_btns_frame, text="اليوم التالي➡️",
            command=self._load_next_route_day
        )
        self.route_main_next_btn.pack(side="left", padx=5)

        self.route_main_print_btn = ttk.Button(
            self.route_main_btns_frame, text="🖨️ طباعة",
            command=self._print_route_pdf
        )
        self.route_main_print_btn.pack(side="left", padx=5)

        self._refresh_route_cards()
        self.selected_route_id = None
        self._update_add_edit_route_btn()
        self.route_main_right_frame = right_frame

        return frame

    def _refresh_route_cards(self):
        import sqlite3
        from datetime import datetime

        for widget in self.routes_card_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("SELECT id, name, date, driver FROM routes ORDER BY date")
            routes = c.fetchall()
            conn.close()
        except Exception as e:
            self.show_message("error", f"فشل تحميل Routes: {e}")
            return

        self.route_cards = []
        for route in routes:
            route_id, name, date_str, driver = route

            # تنسيق التاريخ
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                readable_date = date.strftime("%d/%m/%Y")
            except:
                readable_date = date_str

            card = tb.Frame(self.routes_card_frame, style="RouteCard.TFrame", borderwidth=2, relief="groove", padding=8)
            card.pack(side="left", padx=5, pady=5)
            card.route_id = route_id  # لتسهيل التظليل لاحقاً

            ttk.Label(card, text=f"📛 {name}", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Label(card, text=f"📅 {readable_date}").pack(anchor="w")
            ttk.Label(card, text=f"🚗 {driver}").pack(anchor="w")

            card.bind("<Button-1>", lambda e, rid=route_id: self._toggle_route_selection(rid))
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, rid=route_id: self._toggle_route_selection(rid))

            self.route_cards.append(card)

        # إعادة ضبط زر الإضافة/تعديل للوضع الافتراضي عند إعادة تحميل البطاقات
        self.selected_route_id = None
        self._update_add_edit_route_btn()

    def _on_add_edit_route_btn(self):
        """
        منطق زر إضافة/تعديل Route الذكي:
        - إذا لا يوجد بطاقة محددة: نافذة إضافة جديدة.
        - إذا هناك بطاقة محددة: نافذة تعديل مع تمرير الـroute_id.
        """
        if getattr(self, "selected_route_id", None) is not None:
            self._edit_route_popup(self.selected_route_id)
        else:
            self._add_route_popup()

    def _update_add_edit_route_btn(self):
        """
        تحديث نص ووظيفة زر إضافة/تعديل Route حسب التحديد.
        """
        if hasattr(self, "add_edit_route_btn"):
            if getattr(self, "selected_route_id", None) is not None:
                self.add_edit_route_btn.config(text="✏️ تعديل Route", command=self._on_add_edit_route_btn)
            else:
                self.add_edit_route_btn.config(text="➕ إضافة Route", command=self._on_add_edit_route_btn)

    def _select_route(self, route_id):
        print("📌 تم اختيار البطاقة ذات المعرف:", route_id)
        # تحديد البطاقة المختارة
        self.selected_route_id = route_id

        # 1. تظليل البطاقة المختارة وإلغاء تظليل الباقي
        for card in getattr(self, "route_cards", []):
            if getattr(card, "route_id", None) == route_id:
                card.configure(style="SelectedRouteCard.TFrame")
            else:
                card.configure(style="RouteCard.TFrame")

        # 2. تفعيل زر الحذف عند التحديد
        if hasattr(self, "delete_route_btn"):
            self.delete_route_btn.config(state="normal")

        # 3. تحديث زر إضافة/تعديل Route حسب التحديد
        if hasattr(self, "_update_add_edit_route_btn"):
            self._update_add_edit_route_btn()

        # 4. عرض تفاصيل البطاقة في إطار العرض الجانبي (للقراءة فقط)
        self._display_route_details(route_id)

        # 5. (اختياري) إذا كانت نافذة منبثقة مفتوحة أغلقها
        if hasattr(self, "_route_popup") and self._route_popup.winfo_exists():
            self._route_popup.destroy()

        # print(f"📦 Route المحددة ID = {route_id}")

    def _toggle_route_selection(self, route_id):
        if self.selected_route_id == route_id:
            self._unselect_route()
        else:
            self._select_route(route_id)

    def _unselect_route(self):
        self.selected_route_id = None

        # إعادة تلوين البطاقات
        for card in getattr(self, "route_cards", []):
            card.config(style="RouteCard.TFrame")

        # زر الإضافة
        if hasattr(self, "add_edit_route_btn"):
            self.add_edit_route_btn.config(state="normal", text="➕ إضافة Route")

        # تعطيل زر الحذف
        if hasattr(self, "delete_route_btn"):
            self.delete_route_btn.config(state="disabled")

        # تفريغ التفاصيل
        if hasattr(self, "route_details_name_label"):
            self.route_details_name_label.config(text="")
        if hasattr(self, "route_details_date_label"):
            self.route_details_date_label.config(text="")
        if hasattr(self, "route_details_driver_label"):
            self.route_details_driver_label.config(text="")

        # تعطيل التنقل بين الأيام
        if hasattr(self, "route_main_prev_btn"):
            self.route_main_prev_btn.config(state="disabled")
        if hasattr(self, "route_main_next_btn"):
            self.route_main_next_btn.config(state="disabled")

        # ✅ تفريغ الـ Canvas دون تدميره
        if hasattr(self, "route_main_canvas") and self.route_main_canvas:
            try:
                self.route_main_canvas.delete("all")
            except:
                pass

        # ✅ مسح البيانات
        self.route_days = []
        self.current_route_index = 0
        self.route_start_hours = {}
        self._route_inputs = {}

    def _display_route_details(self, route_id):
        import sqlite3
        import json
        from datetime import datetime

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()

            # ✅ تحميل معلومات Route
            c.execute("SELECT name, date, driver FROM routes WHERE id = ?", (route_id,))
            row = c.fetchone()

            if not row:
                conn.close()
                return

            route_name, route_date, driver = row
            print("✅ تحميل Route:", route_name, route_date, driver)

            # ✅ تحميل البيانات المرتبطة بالأيام
            c.execute("SELECT day, data FROM route_days WHERE route_id = ?", (route_id,))
            day_rows = c.fetchall()
            conn.close()
            print("🗓 عدد الأيام:", len(day_rows))

            self.route_days = []
            self.route_temp_data = {}
            self.route_driver_names = {}
            self.route_start_hours = {}

            for day_str, raw_data in day_rows:
                print(f"📅 قراءة بيانات اليوم: {day_str}")
                print(f"📦 شكل البيانات الخام:\n{raw_data[:100]}")  # طباعة أول 100 حرف فقط

                day_obj = datetime.strptime(day_str, "%Y-%m-%d").date()
                self.route_days.append(day_obj)

                try:
                    data = json.loads(raw_data)
                    self.route_temp_data[day_str] = data.get("rows", [])
                    self.route_driver_names[day_str] = data.get("driver", "-")
                    self.route_start_hours[day_str] = data.get("start", "-")
                except:
                    rows = []
                    for line in raw_data.strip().split("\n"):
                        cols = line.strip().split("\t")
                        rows.append((cols + [""] * 6)[:6])
                    self.route_temp_data[day_str] = rows
                    self.route_driver_names[day_str] = "-"
                    self.route_start_hours[day_str] = "-"

                print(f"🔢 عدد الصفوف المحملة لليوم {day_str}: {len(self.route_temp_data[day_str])}")

            self.current_route_index = 0
            self.selected_route_id = route_id
            self._refresh_route_day_display()
            self._update_route_nav_buttons()
            self.route_main_prev_btn.config(state="normal")
            self.route_main_next_btn.config(state="normal")

        except Exception as e:
            print("خطأ في تحميل تفاصيل Route:", e)

    def _delete_route(self):
        route_id = getattr(self, "selected_route_id", None)
        if not route_id:
            self.show_message("warning", "يرجى تحديد Route أولاً قبل الحذف.")
            return

        if not self.show_custom_confirm("تأكيد الحذف", "⚠️ هل تريد حذف هذا الـ Route نهائيًا؟"):
            return

        try:
            import sqlite3
            import json
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()

            # ✅ جلب بيانات route_name والسائق
            c.execute("SELECT name, driver FROM routes WHERE id = ?", (route_id,))
            row = c.fetchone()
            if not row:
                self.show_message("error", "❌ لم يتم العثور على Route.")
                conn.close()
                return

            route_name, driver = row

            # ✅ جلب جميع الأيام المرتبطة بالـ Route
            c.execute("SELECT day FROM route_days WHERE route_id = ?", (route_id,))
            day_rows = c.fetchall()
            day_keys = [row[0] for row in day_rows]

            # ✅ حذف المهام المرتبطة بكل يوم
            for day_key in day_keys:
                c.execute("""
                    DELETE FROM route_tasks 
                    WHERE route_name = ? AND driver = ? AND date = ?
                """, (route_name, driver, day_key))

            # ✅ حذف الأيام
            c.execute("DELETE FROM route_days WHERE route_id = ?", (route_id,))

            # ✅ حذف السطر الرئيسي من جدول routes
            c.execute("DELETE FROM routes WHERE id = ?", (route_id,))

            conn.commit()
            conn.close()

            self.selected_route_id = None
            self._refresh_route_cards()
            self._unselect_route()
            if hasattr(self, "delete_route_btn"):
                self.delete_route_btn.config(state="disabled")
            if hasattr(self, "route_details_name_label"):
                self.route_details_name_label.config(text="")
            if hasattr(self, "route_details_date_label"):
                self.route_details_date_label.config(text="")
            if hasattr(self, "route_details_driver_label"):
                self.route_details_driver_label.config(text="")

            self.show_message("success", "✅ تم حذف الـ Route بكافة أيامه بنجاح.")

        except Exception as e:
            self.show_message("error", f"حدث خطأ أثناء الحذف:\n{e}")

    def _edit_route_popup(self, route_id):
        import sqlite3
        from datetime import datetime

        self._editing_route_id = route_id  # ← لتفعيل وضع التعديل لاحقًا أثناء الحفظ

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()

            # جلب بيانات Route الأساسية
            c.execute("SELECT name, date, driver FROM routes WHERE id = ?", (route_id,))
            route_row = c.fetchone()
            if not route_row:
                self.show_message("error", "لم يتم العثور على بيانات Route.")
                return

            route_name, first_date_str, driver = route_row

            # جلب جميع الأيام المرتبطة بنفس الاسم والسائق
            c.execute("SELECT DISTINCT date FROM routes WHERE name = ? AND driver = ? ORDER BY date", (route_name, driver))
            date_rows = c.fetchall()
            self.route_days = [datetime.strptime(d[0], "%Y-%m-%d") for d in date_rows]

            # جلب بيانات route_tasks لكل يوم
            self.route_temp_data = {}
            for day in self.route_days:
                day_key = day.strftime("%Y-%m-%d")
                c.execute("""
                    SELECT name, time, lab, description, address, notes
                    FROM route_tasks
                    WHERE route_name = ? AND date = ? AND driver = ?
                """, (route_name, day_key, driver))
                rows = c.fetchall()
                self.route_temp_data[day_key] = rows

            conn.close()

        except Exception as e:
            self.show_message("error", f"حدث خطأ أثناء تحميل Route:\n{e}")
            return

        # فتح واجهة الإضافة في وضع التعديل عبر تمرير المعرف مباشرة
        # ✅ تحديث زر الإضافة/تعديل Route في الواجهة الرئيسية قبل فتح نافذة التعديل
        if hasattr(self, "_update_add_edit_route_btn"):
            self._update_add_edit_route_btn()
        self._add_route_popup(editing_route_id=route_id)

    def _add_route_popup(self, editing_route_id=None):
        import tkinter as tk
        from datetime import datetime, timedelta
        import sqlite3
        import json

        self._editing_route_id = editing_route_id

        today = datetime.today()
        days_ahead = (7 - today.weekday()) % 7
        next_monday = today + timedelta(days=days_ahead)
        self.route_days = []
        for i in range(5):
            day = next_monday + timedelta(days=i)
            if not self.is_holiday(day):
                self.route_days.append(day)
        if not self.route_days:
            self.show_message("warning", "لا توجد أيام متاحة هذا الأسبوع (عطل فقط)")
            return

        self.route_temp_data = {}
        self.route_driver_names = {}
        self.route_start_hours = {}
        self.current_route_index = 0

        win_title = "➕ إضافة Route جديدة" if editing_route_id is None else "✏️ تعديل Route"
        win = self.build_centered_popup(win_title, 1250, 800)
        self._route_popup = win

        top_frame = tb.Frame(win)
        top_frame.pack(fill="x", padx=10, pady=10)

        name_label_frame = tb.Frame(top_frame)
        name_label_frame.grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(name_label_frame, text="📛 اسم Route:").pack(side="left")
        ttk.Label(name_label_frame, text="*", foreground="red").pack(side="left")

        route_name_entry = tb.Entry(top_frame, width=25)
        route_name_entry.grid(row=0, column=1, padx=5)

        ttk.Label(top_frame, text="📅 التاريخ:").grid(row=0, column=2, sticky="w", padx=5)
        route_date_label = ttk.Label(top_frame, text="", width=20)
        route_date_label.grid(row=0, column=3, padx=5)

        self._route_prev_btn = ttk.Button(top_frame, text="⬅️ السابق", command=self._prev_route_day)
        self._route_prev_btn.grid(row=0, column=8, padx=5)
        self._route_next_btn = ttk.Button(top_frame, text="التالي ➡️", command=self._next_route_day)
        self._route_next_btn.grid(row=0, column=9, padx=5)

        ttk.Label(top_frame, text="🚗 السائق:").grid(row=0, column=4, sticky="w", padx=5)
        current_route_day = self.route_days[0]
        driver_combo = ttk.Combobox(top_frame, values=self.get_driver_names(current_route_day), state="readonly", width=20)
        driver_combo.grid(row=0, column=5, padx=5)

        ttk.Label(top_frame, text="🕗 بداية العمل:").grid(row=0, column=6, sticky="w", padx=5)
        start_hour_combo = ttk.Combobox(
            top_frame,
            values=[f"{h:02}:{m:02}" for h in range(6, 17) for m in (0, 30)],
            state="readonly",
            width=10
        )
        start_hour_combo.grid(row=0, column=7, padx=5)

        doctor_input_frame = tb.LabelFrame(win, text="🏥 إضافة مخبر إلى Route", padding=10)
        doctor_input_frame.pack(fill="x", padx=10, pady=(5, 10))
        self._doctor_lab_checks_frame = tb.Frame(doctor_input_frame)
        self._doctor_lab_checks_frame.pack(fill="x", pady=(10, 5))
        self._doctor_lab_vars = {}

        canvas_frame = tb.Frame(win)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.route_preview_canvas = tb.Canvas(canvas_frame, bg="white", width=1100, height=400)
        self.route_preview_canvas.pack(fill="both", expand=True)

        button_frame = tb.Frame(win)
        button_frame.pack(fill="x", pady=(10, 10), padx=10)

        left_btns = tb.Frame(button_frame)
        left_btns.pack(side="left")
        ttk.Button(left_btns, text="➕ إضافة صف يدوي", command=self._add_manual_route_row).pack(side="left", padx=5)
        ttk.Button(left_btns, text="🔁 إعادة تحميل اليوم", command=self._reload_route_day_data).pack(side="left", padx=5)
        ttk.Button(left_btns, text="⬆️ للأعلى", command=self._move_route_row_up).pack(side="left", padx=5)
        ttk.Button(left_btns, text="⬇️ للأسفل", command=self._move_route_row_down).pack(side="left", padx=5)
        ttk.Button(left_btns, text="🗑 حذف الصف المحدد", command=self._delete_selected_route_row).pack(side="left", padx=5)

        right_btns = tb.Frame(button_frame)
        right_btns.pack(side="right")
        ttk.Button(right_btns, text="💾 تطبيق", command=lambda: self._save_full_route(apply_only=True)).pack(side="left", padx=5)
        ttk.Button(right_btns, text="💾 حفظ", command=self._save_full_route).pack(side="left", padx=5)
        ttk.Button(right_btns, text="❌ إغلاق", command=self._confirm_close_route_popup).pack(side="left", padx=5)
        ttk.Button(right_btns, text="🖨️ طباعة", command=self._print_route_pdf).pack(side="left", padx=5)

        self._route_inputs = {
            "window": win,
            "popup": win,
            "name_entry": route_name_entry,
            "driver_combo": driver_combo,
            "date_label": route_date_label,
            "start_hour_combo": start_hour_combo
        }

        if editing_route_id is not None:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("SELECT name FROM routes WHERE id=?", (editing_route_id,))
            row = c.fetchone()
            if row:
                route_name = row[0]
                route_name_entry.delete(0, "end")
                route_name_entry.insert(0, route_name)
            conn.close()

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("SELECT day, data FROM route_days WHERE route_id=?", (editing_route_id,))
            for day_str, data_json in c.fetchall():
                try:
                    data = json.loads(data_json)
                    start = data.get("start", "").strip()
                    driver = data.get("driver", "").strip()
                    if start:
                        self.route_start_hours[day_str] = start
                    if driver:
                        self.route_driver_names[day_str] = driver
                except:
                    continue
            conn.close()
        except Exception as e:
            print("⚠️ فشل تحميل بيانات start_hour/driver:", e)

        if self.route_days:
            first_day_key = self.route_days[0].strftime("%Y-%m-%d")
            driver_for_day = self.route_driver_names.get(first_day_key, "")
            if driver_for_day:
                driver_combo.set(driver_for_day)
            start_hour = self.route_start_hours.get(first_day_key, "")
            if start_hour:
                start_hour_combo.set(start_hour)

        if not getattr(self, "_suppress_autoload", False):
            self._load_route_day()

        def update_driver_and_time(*_):
            if self.route_days:
                day = self.route_days[self.current_route_index]
                day_key = day.strftime("%Y-%m-%d")
                self._route_inputs["driver_combo"]["values"] = self.get_driver_names(day)
                self.route_driver_names[day_key] = driver_combo.get().strip()
                self.route_start_hours[day_key] = start_hour_combo.get().strip()
                self._draw_route_preview()

        driver_combo.bind("<<ComboboxSelected>>", update_driver_and_time)
        start_hour_combo.bind("<<ComboboxSelected>>", update_driver_and_time)
        driver_combo.bind("<FocusOut>", update_driver_and_time)
        start_hour_combo.bind("<FocusOut>", update_driver_and_time)

        def on_popup_close():
            if hasattr(self, "_editing_route_id"):
                self._editing_route_id = None
            self._update_add_edit_route_btn()
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_popup_close)

    def _confirm_close_route_popup(self):
        self.show_message(
            "confirm",
            "هل أنت متأكد أنك تريد الخروج بدون حفظ؟",
            confirm_callback=lambda: self._route_popup.destroy()
        )

    # 🧠 فلترة ذكية
    def _update_doctor_checkbuttons(self, search_text=""):
        for widget in self._doctor_lab_checks_frame.winfo_children():
            widget.destroy()

        # إنشاء إطارين منفصلين للأطباء والمخابر
        doctors_frame = tb.Frame(self._doctor_lab_checks_frame)
        doctors_frame.pack(fill="x", anchor="w")
    
        labs_frame = tb.Frame(self._doctor_lab_checks_frame)
        labs_frame.pack(fill="x", anchor="w", pady=(5, 0))  # سطر جديد للمخابر

        for label, var in self._doctor_lab_vars.items():
            if search_text.lower() in label.lower():
                if label.startswith("🧪"):  # المخابر
                    parent = labs_frame
                else:  # الأطباء
                    parent = doctors_frame
                    
                chk = ttk.Checkbutton(parent, text=label, variable=var,
                                      command=lambda l=label: self._on_doctor_lab_toggle(l))
                chk.pack(side="left", padx=5, pady=5, anchor="n")

    def _load_route_day(self):
        import sqlite3
        from datetime import datetime

        current_date = self.route_days[self.current_route_index]
        weekday_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        weekday_name = weekday_names[current_date.weekday()]
        readable_date = current_date.strftime("%Y-%m-%d")

        self._route_inputs["date_label"].config(text=f"{weekday_name} - {readable_date}")

        weekday_key = ["mon", "tue", "wed", "thu", "fri"][current_date.weekday()]
        day_key = current_date.strftime("%Y-%m-%d")

        # ✅ تحميل البيانات المؤقتة فقط إن لم تكن موجودة
        if day_key not in self.route_temp_data:
            doctors = self.get_doctors_by_weekday(weekday_key, current_date)
            new_rows = []
            for doctor in doctors:
                row = (
                    doctor["name"],
                    doctor["time"],
                    doctor["lab"],
                    doctor["materials"],
                    doctor["address"],
                    doctor["notes"] or ""
                )
                new_rows.append(row)
            self.route_temp_data[day_key] = new_rows

        # ✅ تحميل الصفوف من الذاكرة
        rows = self.route_temp_data.get(day_key, [])
    
        # ✅ تحميل السائق من الذاكرة إذا متاح
        driver_name = self.route_driver_names.get(day_key, "")
        self._route_inputs["driver_combo"].set(driver_name)

        # ✅ تحديث قائمة السائقين حسب اليوم الحالي
        self._route_inputs["driver_combo"]["values"] = self.get_driver_names(current_date)

        # ✅ التحقق من إجازة السائق الحالي
        def continue_with_driver():
            self._route_inputs["driver_combo"].set(driver_name)
            self._draw_route_preview()

        if driver_name and self.is_on_vacation(driver_name, current_date, "سائق"):
            self.show_message(
                "confirm",
                f"السائق '{driver_name}' في إجازة يوم {weekday_name} ({readable_date}).\n"
                f"هل ترغب في متابعة هذا اليوم بنفس السائق؟",
                parent=self._route_popup,
                confirm_callback=continue_with_driver
            )
            self._route_inputs["driver_combo"].set("")

        # ✅ تحميل بداية العمل من الذاكرة
        start_hour = self.route_start_hours.get(day_key, "")
        self._route_inputs["start_hour_combo"].set(start_hour)

        # ✅ تحديث المعاينة
        self._draw_route_preview()

        # ✅ إعداد قائمة اختيار الأطباء والمخابر
        available_doctors = self.get_doctors_by_weekday(weekday_key, current_date)
        all_labs = self.get_all_lab_names()

        doctor_lab_items = [f"🧪 {lab}" for lab in all_labs]
        self._available_doctors_today = {
            f"{doc['name']} 🔗 {doc['lab'].replace(chr(10), ' / ').strip()}": doc
            for doc in available_doctors
        }

        self._doctor_lab_vars.clear()
        for widget in self._doctor_lab_checks_frame.winfo_children():
            widget.destroy()

        for label in doctor_lab_items:
            var = tk.BooleanVar()
            var.trace_add("write", lambda *_args, l=label: self._on_doctor_lab_toggle(l))
            self._doctor_lab_vars[label] = var

        self._update_doctor_checkbuttons("")

    def _on_doctor_lab_toggle(self, label):
        day_key = self.route_days[self.current_route_index].strftime("%Y-%m-%d")

        if label.startswith("🧑‍⚕️ "):
            # طبيب
            content = label.replace("🧑‍⚕️ ", "")
            name_part = content.split(" 🔗 ")[0].strip()
            doctor = None
            for key, doc in self._available_doctors_today.items():
                if key.startswith(name_part):
                    doctor = doc
                    break
            if not doctor:
                return

            row = (
                doctor["name"],
                doctor["time"],
                doctor["lab"],
                doctor["materials"],
                doctor["address"],
                doctor["notes"] or ""
            )

        elif label.startswith("🧪 "):
            # مخبر
            lab_name = label.replace("🧪 ", "").strip()
            address = self.get_lab_address_by_name(lab_name)
            row = (lab_name, "", "", "", address,  "")                
        else:
            return

        # إدراج أو إزالة
        existing = self.route_temp_data.get(day_key, [])
        row = list(row)
        if self._doctor_lab_vars[label].get():
            if row in existing:
                return  # 🚫 الصف مكرر، لا حاجة لإضافته

            self.route_temp_data[day_key].append(row)

        else:
            self.route_temp_data[day_key] = [r for r in existing if r != row]

        # ترتيب الأطباء حسب الوقت
        def time_key(r):
            try:
                return int(r[1].split(":")[0]) * 60 + int(r[1].split(":")[1])
            except:
                return 9999
        self.route_temp_data[day_key].sort(key=time_key)

        self._draw_route_preview()

    def _update_doctor_fields(self):
        name = self._route_inputs["doctor_combo"].get()
        doctor = self._available_doctors_today.get(name)
        if not doctor:
            return

        # تحديث الحقول
        labs = doctor["lab"].splitlines() if "\n" in doctor["lab"] else [doctor["lab"]]
        self._route_inputs["lab_combo"]["values"] = labs
        self._route_inputs["lab_combo"].set(labs[0] if labs else "")

        self._route_inputs["materials_entry"].delete(0, "end")
        self._route_inputs["materials_entry"].insert(0, doctor["notes"])

    def _handle_doctor_or_lab_selection(self):
        selected = self._route_inputs["doctor_combo"].get()

        # 🧑‍⚕️ د. أحمد 🔗 Alpha
        if selected.startswith("🧑‍⚕️ "):
            content = selected.replace("🧑‍⚕️ ", "")
            name_part = content.split(" 🔗 ")[0].strip()
            doctor = None

            # البحث عن الطبيب بالمفتاح المطابق
            for key, doc in self._available_doctors_today.items():
                if key.startswith(name_part):
                    doctor = doc
                    break

            if not doctor:
                return

            # ✅ بناء سطر الطبيب
            row = (
                doctor["name"],
                doctor["time"],
                doctor["lab"],
                doctor["materials"],
                doctor["address"],
                doctor["notes"] or ""
            )

            day_key = self.route_days[self.current_route_index].strftime("%Y-%m-%d")
            self.route_temp_data[day_key].append(row)

            # ✅ إعادة ترتيب الصفوف حسب الوقت
            def get_time_sort_key(row):
                time_str = row[1]
                try:
                    return int(time_str.split(":")[0]) * 60 + int(time_str.split(":")[1])
                except:
                    return 9999

            self.route_temp_data[day_key].sort(key=get_time_sort_key)
            self._draw_route_preview()

        elif selected.startswith("🧪 "):
            lab_name = selected.replace("🧪 ", "").strip()
            address = self.get_lab_address_by_name(lab_name)

            row = (lab_name, "", "", "", address, "")

            day_key = self.route_days[self.current_route_index].strftime("%Y-%m-%d")
            self.route_temp_data[day_key].append(row)
            self._draw_route_preview()

        # ✅ تفريغ الحقل بعد الإدراج لتسهيل تكرار الإدخال
        self._route_inputs["doctor_combo"].set("")

    def _next_route_day(self):
        self._update_route_start_hour()
        self._update_notes_from_widgets()
        if self.current_route_index + 1 < len(self.route_days):
            self.current_route_index += 1
            self._route_prev_btn["state"] = "normal"
            if self.current_route_index + 1 == len(self.route_days):
                self._route_next_btn["state"] = "disabled"
                self.show_message("info", "🗓️ هذا هو آخر يوم في الأسبوع. يمكنك الآن مراجعة وإدخال البيانات أو حفظ Route.")
            self._load_route_day()

    def _prev_route_day(self):
        self._update_route_start_hour()
        self._update_notes_from_widgets()
        if self.current_route_index > 0:
            self.current_route_index -= 1
            self._route_next_btn["state"] = "normal"
            if self.current_route_index == 0:
                self._route_prev_btn["state"] = "disabled"
            self._load_route_day()

    def _load_prev_route_day(self):
        if not hasattr(self, "route_days") or not hasattr(self, "current_route_index"):
            return
        if self.current_route_index > 0:
            self.current_route_index -= 1
            self._refresh_route_day_display()
            self._update_route_nav_buttons()

    def _load_next_route_day(self):
        if not hasattr(self, "route_days") or not hasattr(self, "current_route_index"):
            return
        if self.current_route_index + 1 < len(self.route_days):
            self.current_route_index += 1
            self._refresh_route_day_display()
            self._update_route_nav_buttons()

    def _refresh_route_day_display(self):
        if not hasattr(self, "route_days") or not hasattr(self, "current_route_index"):
            return

        if not self.route_days or self.current_route_index >= len(self.route_days):
            return  # ✅ حماية إضافية في حال تم مسح الأيام

        if hasattr(self, "route_main_canvas") and self.route_main_canvas.winfo_exists():
            self._draw_route_main_canvas()
        else:
            self._load_route_day()

        # 💡 تحديث عناصر الواجهة فقط إذا كنا في نافذة التعديل/الإضافة
        if hasattr(self, "_route_inputs"):
            day_key = self.route_days[self.current_route_index].strftime("%Y-%m-%d")
            if "start_hour_combo" in self._route_inputs:
                combo = self._route_inputs["start_hour_combo"]
                if combo.winfo_exists():  # ✅ حماية من استدعاء عنصر تم تدميره
                    combo.set(self.route_start_hours.get(day_key, ""))

    def _update_route_nav_buttons(self):
        """تحديث حالة أزرار التنقل حسب موقع اليوم الحالي"""
        if not hasattr(self, "route_days") or not self.route_days:
            return

        if self.current_route_index <= 0:
            self.route_main_prev_btn.config(state="disabled")
        else:
            self.route_main_prev_btn.config(state="normal")

        if self.current_route_index >= len(self.route_days) - 1:
            self.route_main_next_btn.config(state="disabled")
        else:
            self.route_main_next_btn.config(state="normal")

    def _get_route_name(self, route_id):
        import sqlite3
        if not route_id:
            return None
        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()
            c.execute("SELECT name FROM routes WHERE id = ?", (route_id,))
            row = c.fetchone()
            conn.close()
            return row[0] if row else None
        except:
            return None

    def _add_manual_route_row(self):
        import tkinter as tk
        from tkinter import ttk

        popup = tk.Toplevel(self)
        popup.title("➕ إضافة صف يدوي")

        # احصل على إحداثيات نافذة Route الحالية
        parent = self._route_popup
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        popup_width = 300
        popup_height = 160
        x = parent_x + (parent_width // 2) - (popup_width // 2)
        y = parent_y + (parent_height // 2) - (popup_height // 2)

        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup.transient(parent)
        popup.grab_set()

        row_type = tk.StringVar(value="normal")

        ttk.Label(popup, text="نوع الصف:", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5))
        ttk.Radiobutton(popup, text="🔹 صف متعدد الأعمدة", variable=row_type, value="normal").pack(anchor="w", padx=20)
        ttk.Radiobutton(popup, text="📝 صف ملاحظات عامة (ممتد)", variable=row_type, value="note_only").pack(anchor="w", padx=20)

        def add_row():
            current_date = self.route_days[self.current_route_index]
            day_key = current_date.strftime("%Y-%m-%d")
            if day_key not in self.route_temp_data:
                self.route_temp_data[day_key] = []

            if row_type.get() == "note_only":
                # 🟢 لا نتحقق من التكرار — نسمح بإضافة أكثر من صف ملاحظات عامة
                row = ["", "", "", "", "", "__note_only__"]
                self.route_temp_data[day_key].append(row)
            else:
                row = ["", "", "", "", "", ""]
                self.route_temp_data[day_key].append(row)

            popup.destroy()
            self._draw_route_preview()

        ttk.Button(popup, text="✔️ إضافة", command=add_row).pack(pady=15)

    def _add_selected_doctor_to_table(self):
        # 🔄 نحصل على أول عنصر مفعّل من Checkbuttons
        selected = next((name for name, var in self._doctor_lab_vars.items() if var.get()), None)

        if not selected:
            self.show_message("warning", "❌ لم يتم تحديد طبيب أو مخبر.")
            return

        if selected.startswith("🧑‍⚕️ "):
            name = selected.replace("🧑‍⚕️ ", "")
            doctor = self._available_doctors_today.get(name)
            if not doctor:
                self.show_message("warning", "❌ طبيب غير موجود.")
                return

            row = (
                doctor["name"],
                doctor["time"],
                doctor["lab"],
                doctor["materials"],
                doctor["address"],
                doctor["notes"] or ""
            )

        elif selected.startswith("🧪 "):
            name = selected.replace("🧪 ", "")
            row = (
                name,     # اسم المخبر
                "",       # الوقت
                "",       # المخبر
                "",       # المواد
                self.get_lab_address_by_name(name),
                ""        # ملاحظات
            )

        else:
            self.show_message("warning", "❌ يرجى اختيار طبيب أو مخبر من القائمة.")
            return

        day_key = self.route_days[self.current_route_index].strftime("%Y-%m-%d")

        # ✅ منع التكرار
        existing = self.route_temp_data.get(day_key, [])
        if any(r[0] == row[0] for r in existing):
            self.show_message("warning", f"⚠️ '{row[0]}' موجود بالفعل في الجدول بنفس الوقت.")
            return

        self.route_temp_data.setdefault(day_key, []).append(row)
        self.route_temp_data[day_key].sort(key=lambda row: self._extract_sort_time(row[1]))
        self._draw_route_preview()

    def get_lab_address_by_name(self, name):
        import sqlite3
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT address FROM labs WHERE name = ?", (name,))
            row = c.fetchone()
            if row:
                return row[0]
            return ""

    def _reload_route_day_data(self):
        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")
        weekday_key = ["mon", "tue", "wed", "thu", "fri"][current_date.weekday()]

        # 🧹 احتفظ بالصفوف اليدوية فقط (أي التي آخر حقل فيها غير فارغ)
        existing = self.route_temp_data.get(day_key, [])
        manual_rows = [row for row in existing if row[-1].strip() != ""]

        # تحميل أطباء اليوم
        doctors = self.get_doctors_by_weekday(weekday_key, current_date)
        new_rows = []
        for doctor in doctors:
            new_rows.append((
                doctor["name"],
                doctor["time"],
                doctor["lab"],
                doctor["desc"],
                doctor["address"],
                doctor["notes"] or ""
            ))

        # تحميل المخابر
        labs = self.get_lab_transfers_by_weekday(weekday_key, current_date)
        for lab in labs:
            new_rows.append((lab["name"], "", "", "", lab["address"], ""))

        # حفظ اليوم وتحديث المعاينة
        self.route_temp_data[day_key] = new_rows + manual_rows
        self._draw_route_preview()

    def _move_route_row_up(self):
        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")
        rows = self.route_temp_data.get(day_key, [])

        idx = getattr(self, "_selected_route_row_index", None)
        if idx is None or idx <= 0 or idx >= len(rows):
            return

        # تبادل الصف المحدد مع الصف الذي قبله
        rows[idx - 1], rows[idx] = rows[idx], rows[idx - 1]
        self._selected_route_row_index -= 1  # تحديث المؤشر للصف الجديد

        self._draw_route_preview()

    def _move_route_row_down(self):
        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")
        rows = self.route_temp_data.get(day_key, [])

        idx = getattr(self, "_selected_route_row_index", None)
        if idx is None or idx >= len(rows) - 1:
            return

        # تبادل الصف المحدد مع الصف التالي
        rows[idx + 1], rows[idx] = rows[idx], rows[idx + 1]
        self._selected_route_row_index += 1  # تحديث المؤشر للصف الجديد

        self._draw_route_preview()

    def _delete_selected_route_row(self):
        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")
        rows = self.route_temp_data.get(day_key, [])

        idx = getattr(self, "_selected_route_row_index", None)
        if idx is None or not (0 <= idx < len(rows)):
            return

        # ✅ إضافة رسالة تأكيد مخصصة
        def do_delete():
            del rows[idx]
            self._selected_route_row_index = None
            self._draw_route_preview()

        self.show_message(
            kind="confirm",
            message="⚠️ هل أنت متأكد أنك تريد حذف هذا الصف؟",
            confirm_callback=do_delete
        )

    def is_note_row(self, row):
        row = (list(row) + [""] * 6)[:6]
        result = all(not str(c).strip() for c in row[:5]) and str(row[5]).strip().startswith("__note_only__")
        return result

    def _make_note_edit_callback(self, row_index):
        return lambda e: self._edit_note_only_row(row_index)

    def _draw_route_preview(self):
        import tkinter as tk
        import tkinter.font as tkfont

        canvas = self.route_preview_canvas
        canvas.delete("all")

        if not self.route_days:
            return

        day = self.route_days[self.current_route_index]
        day_key = day.strftime("%Y-%m-%d")
        rows = self.route_temp_data.get(day_key, [])

        for i in range(len(rows)):
            rows[i] = (list(rows[i]) + [""] * 6)[:6]
        self.route_temp_data[day_key] = rows

        weekday_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        weekday_name = weekday_names[day.weekday()]
        readable_date = f"{weekday_name} - {day.strftime('%Y-%m-%d')}"

        driver = self._route_inputs["driver_combo"].get().strip()
        start_hour = self._route_inputs["start_hour_combo"].get().strip()

        headers = ["الطبيب / المخبر", "Zeit", "المخبر", "Beschreibung", "العنوان", "ملاحظات/مواد"]
        column_ratios = [1.5, 1.2, 0.9, 1.5, 2, 2.6]
        total_ratio = sum(column_ratios)

        canvas.update_idletasks()
        canvas_width = 1200
        col_widths = [int(canvas_width * (r / total_ratio)) for r in column_ratios]

        x_positions = [30]  # ← مساحة مخصصة لزر التحديد خارج الأعمدة
        for w in col_widths[:-1]:
            x_positions.append(x_positions[-1] + w)

        total_width = sum(col_widths) + 30
        default_row_height = 30
        y = 20

        canvas.create_text(10, y, anchor="nw", text=f"🕗 بداية العمل: {start_hour}", font=("Segoe UI", 10, "bold"))
        canvas.create_text(total_width // 2, y, anchor="n", text=f"📅 التاريخ: {readable_date}", font=("Segoe UI", 10, "bold"))
        canvas.create_text(total_width - 10, y, anchor="ne", text=f"🚗 السائق: {driver}", font=("Segoe UI", 10, "bold"))
        y += 30

        canvas.create_text(15, y + default_row_height // 2, anchor="center", text="📍", font=("Segoe UI", 10, "bold"))
        for i, header in enumerate(headers):
            x = x_positions[i]
            canvas.create_rectangle(x, y, x + col_widths[i], y + default_row_height, fill="#dddddd")
            canvas.create_text(x + col_widths[i] // 2, y + default_row_height // 2, anchor="center", text=header, font=("Segoe UI", 10, "bold"))

        y += default_row_height
        self._notes_vars = []

        font_conf = ("Segoe UI", 9)
        font_obj = tkfont.Font(font=font_conf)

        self._x_positions = x_positions
        self._col_widths = col_widths
        self._font_obj = font_obj
        self._font_conf = font_conf
        self._start_table_y = y
        self._row_y_positions = []

        for row_index in range(len(rows)):
            row_data = self.route_temp_data[day_key][row_index]
            self._row_y_positions.append(y)

            if self.is_note_row(row_data):
                line_height = self._font_obj.metrics("linespace")
                note_text = row_data[5].replace("__note_only__", "").lstrip()
                note_lines = note_text.split("\n") if note_text.strip() else [""]
                row_height = max(line_height, len(note_lines) * line_height) + 18
            else:
                cell_heights = []
                for i in range(len(self._col_widths)):
                    text = str(row_data[i])
                    width_limit = max(self._col_widths[i] - 8, 30)
                    words = text.split()
                    lines = []
                    current_line = ""
                    for word in words:
                        test_line = current_line + " " + word if current_line else word
                        if self._font_obj.measure(test_line) <= width_limit:
                            current_line = test_line
                        else:
                            lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                    est_height = len(lines) * self._font_obj.metrics("linespace") + 8
                    cell_heights.append(est_height)
                row_height = max(cell_heights)
                row_height = max(row_height, 34)

            # 🟡 رسم خلفية الصف المحدد
            if getattr(self, "_selected_route_row_index", None) == row_index:
                canvas.create_rectangle(
                    0, y, sum(self._col_widths) + 30, y + row_height,
                    fill="#eeeeee", outline=""
                )

            # ثم نرسم محتوى الصف بعد الخلفية
            if self.is_note_row(row_data):
                y = self._draw_note_row(canvas, row_index, y)
            else:
                row_height = self._draw_route_row(
                    canvas, row_index, self._x_positions, self._col_widths,
                    self._font_obj, self._font_conf, y
                )
                icon = "✅" if getattr(self, "_selected_route_row_index", None) == row_index else "🔘"
                canvas.create_text(15, y + row_height // 2, anchor="center", text=icon, font=("Segoe UI", 11, "bold"))

                for x in self._x_positions:
                    canvas.create_line(x, y, x, y + row_height, fill="#000000")
                y += row_height

        canvas.create_line(0, y, total_width, y, fill="#000000")
        canvas.config(scrollregion=(0, 0, total_width, y + 20))
        # canvas.config(width=min(total_width, 1250))
        canvas.config(xscrollincrement=1)

        def on_canvas_click(event):
            ex, ey = event.x, event.y
            print(f"[DEBUG] on_canvas_click: x={ex}, y={ey}")

            for row_index, y_top in enumerate(self._row_y_positions):
                row_data = list(self.route_temp_data[self.route_days[self.current_route_index].strftime("%Y-%m-%d")][row_index])

                if hasattr(self, "is_note_row") and self.is_note_row(row_data):
                    # صف ملاحظة عامة
                    line_height = self._font_obj.metrics("linespace")
                    text = row_data[5].replace("__note_only__", "").lstrip()
                    lines = text.split("\n") if text.strip() else [""]
                    row_height = max(line_height, len(lines) * line_height) + 18

                    # ✅ السماح بالتحديد فقط من العمود الأيسر
                    if y_top <= ey <= y_top + row_height and 0 <= ex <= 30:
                        print(f"[DEBUG] on_canvas_click: selected note row={row_index}")
                        if getattr(self, "_selected_route_row_index", None) == row_index:
                            self._selected_route_row_index = None
                        else:
                            self._selected_route_row_index = row_index
                        self._draw_route_preview()
                        return
    
                    continue  # لا ننفذ أي شيء آخر على صف الملاحظات
    
                else:
                    # صف عادي
                    cell_heights = []
                    for i in range(len(self._col_widths)):
                        text = str(row_data[i])
                        width_limit = max(self._col_widths[i] - 8, 30)
                        words = text.split()
                        lines = []
                        current_line = ""
                        for word in words:
                            test_line = current_line + " " + word if current_line else word
                            if self._font_obj.measure(test_line) <= width_limit:
                                current_line = test_line
                            else:
                                lines.append(current_line)
                                current_line = word
                        if current_line:
                            lines.append(current_line)
                        est_height = len(lines) * self._font_obj.metrics("linespace") + 8
                        cell_heights.append(est_height)
                    row_height = max(cell_heights)

                if y_top <= ey <= y_top + row_height:
                    if 0 <= ex <= 30:
                        print(f"[DEBUG] on_canvas_click: select row button row={row_index}")
                        # ✅ عمود التحديد
                        if getattr(self, "_selected_route_row_index", None) == row_index:
                            self._selected_route_row_index = None
                        else:
                            self._selected_route_row_index = row_index
                        self._draw_route_preview()
                        return

                    # ✅ باقي الأعمدة
                    x_positions = self._x_positions
                    if x_positions[0] <= ex <= x_positions[1]:
                        print(f"[DEBUG] on_canvas_click: doctor selector row={row_index}")
                        self._show_doctor_selector(row_index, x_positions[0], y_top)
                    elif x_positions[1] <= ex <= x_positions[2]:
                        print(f"[DEBUG] on_canvas_click: time selector row={row_index}")
                        self._show_time_selector(row_index, x_positions[1], y_top)
                    elif x_positions[2] <= ex <= x_positions[3]:
                        print(f"[DEBUG] on_canvas_click: lab selector row={row_index}")
                        self._show_lab_selector(row_index, x_positions[2], y_top)
                    elif x_positions[3] <= ex <= x_positions[4]:
                        print(f"[DEBUG] on_canvas_click: material selector row={row_index}")
                        self._show_material_selector(row_index, x_positions[3], y_top)
                    return

        if hasattr(self, "_preview_click_binding"):
            try:
                canvas.unbind("<Button-1>", self._preview_click_binding)
            except Exception:
                pass
            del self._preview_click_binding

        self._preview_click_binding = canvas.bind("<Button-1>", on_canvas_click)

    def _draw_route_main_canvas(self):
        if not hasattr(self, "route_days") or not self.route_days:
            return

        import tkinter.font as tkfont

        canvas = self.route_main_canvas
        canvas.delete("all")

        day = self.route_days[self.current_route_index]
        day_key = day.strftime("%Y-%m-%d")
        rows = self.route_temp_data.get(day_key, [])
        rows = [(list(row) + [""] * 6)[:6] for row in rows]
        self.route_temp_data[day_key] = rows

        route_name = self._get_route_name(self.selected_route_id) or "-"
        driver = self.route_driver_names.get(day_key, "-")
        start_hour = self.route_start_hours.get(day_key, "-")

        print("🎨 بدء رسم Canvas لـ Route:", route_name)
        print("🧭 التاريخ الحالي:", day)
        print("📊 عدد الصفوف:", len(rows))

        weekday_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        readable_date = f"{weekday_names[day.weekday()]} - {day.strftime('%Y-%m-%d')}"

        headers = ["الطبيب / المخبر", "Zeit", "المخبر", "Beschreibung", "العنوان", "ملاحظات/مواد"]
        column_ratios = [1.5, 1.2, 0.9, 1.5, 2, 2.6]
        total_ratio = sum(column_ratios)
    
        canvas_width = canvas.winfo_width() or 1200
        col_widths = [int(canvas_width * (r / total_ratio)) for r in column_ratios]
        x_positions = [0]
        for w in col_widths[:-1]:
            x_positions.append(x_positions[-1] + w)
        total_width = sum(col_widths) + 30

        y = 20
        canvas.create_text(10, y, anchor="nw", text=f"🕗 بداية العمل: {start_hour}", font=("Segoe UI", 10, "bold"))
        canvas.create_text(total_width // 2, y, anchor="n", text=f"📅 التاريخ: {readable_date}", font=("Segoe UI", 10, "bold"))
        canvas.create_text(canvas_width - 10, y, anchor="ne", text=f"🚗 السائق: {driver}", font=("Segoe UI", 10, "bold"))
        y += 30

        for i, header in enumerate(headers):
            x = x_positions[i]
            canvas.create_rectangle(x, y, x + col_widths[i], y + 30, fill="#dddddd")
            canvas.create_text(x + col_widths[i] // 2, y + 15, anchor="center", text=header, font=("Segoe UI", 10, "bold"))
        y += 30

        font_conf = ("Segoe UI", 9)
        font_obj = tkfont.Font(font=font_conf)

        for row_data in rows:
            if self.is_note_row(row_data):
                text = row_data[5].replace("__note_only__", "").lstrip()
                lines = text.split("\n") if text.strip() else [""]
                row_height = max(font_obj.metrics("linespace"), len(lines) * font_obj.metrics("linespace")) + 18
                note_font = ("Segoe UI", 10, "bold")
                note_text = "\n".join(lines)

                canvas.create_rectangle(x_positions[0], y, x_positions[-1] + col_widths[-1], y + row_height, fill="#ffffff", outline="#cccccc")
                canvas.create_text(total_width // 2, y + row_height // 2, anchor="c", text=note_text, font=note_font, fill="#000000")
                y += row_height
            else:
                cell_heights = []
                for i in range(len(col_widths)):
                    text = str(row_data[i])
                    width_limit = max(col_widths[i] - 8, 30)
                    words = text.split()
                    lines = []
                    current_line = ""
                    for word in words:
                        test_line = current_line + " " + word if current_line else word
                        if font_obj.measure(test_line) <= width_limit:
                            current_line = test_line
                        else:
                            lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                    est_height = len(lines) * font_obj.metrics("linespace") + 8
                    cell_heights.append(est_height)
                row_height = max(max(cell_heights), 34)
    
                for i in range(len(headers)):
                    x = x_positions[i]
                    canvas.create_rectangle(x, y, x + col_widths[i], y + row_height, fill="#ffffff", outline="#cccccc")
                    canvas.create_text(x + 5, y + 5, anchor="nw", text=str(row_data[i]), font=font_conf, fill="#000000")
                y += row_height

        canvas.config(scrollregion=(0, 0, total_width, y + 20))

    def _edit_note_only_row(self, row_index):
        import tkinter as tk

        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")
        row = (list(self.route_temp_data[day_key][row_index]) + [""] * 6)[:6]

        current_value = row[5]

        parent = self._route_popup
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        popup_width = 420
        popup_height = 240
        x = parent_x + (parent_width // 2) - (popup_width // 2)
        y = parent_y + (parent_height // 2) - (popup_height // 2)

        top = tk.Toplevel(self)
        top.title("✏️ تعديل الملاحظات")
        top.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        top.transient(parent)
        top.grab_set()

        content_frame = tk.Frame(top)
        content_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        text = tk.Text(content_frame, font=("Segoe UI", 10), height=6)
        text.pack(fill="both", expand=True)
        text.insert("1.0", current_value.replace("__note_only__", "").lstrip())

        button_frame = tk.Frame(top)
        button_frame.pack(fill="x", pady=(0, 10))

        def save_note():
            new_note = text.get("1.0", "end").strip()
            row = self.route_temp_data[day_key][row_index]
            if not new_note.strip():
                new_note = ""
            row[5] = f"__note_only__\n{new_note.strip()}"

            row = self.route_temp_data[day_key][row_index]
            while len(row) < 6:
                row.append("")
            for i in range(5):
                row[i] = ""
            row[5] = f"__note_only__\n{new_note.strip()}" if new_note.strip() else "__note_only__"

            self._draw_route_preview()
            top.destroy()

        save_button = tk.Button(button_frame, text="💾 حفظ", font=("Segoe UI", 10, "bold"), command=save_note)
        save_button.pack(anchor="center", pady=5)

    def _draw_route_row(self, canvas, row_index, x_positions, col_widths, font_obj, font_conf, start_y):
        day = self.route_days[self.current_route_index]
        day_key = day.strftime("%Y-%m-%d")
        row_data = list(self.route_temp_data[day_key][row_index])
        headers = ["الطبيب / المخبر", "Zeit", "المخبر", "Beschreibung", "العنوان", "ملاحظات/مواد"]

        cell_heights = []
        for i in range(len(headers)):
            text = str(row_data[i])
            width_limit = max(col_widths[i] - (30 if i == len(headers) - 1 else 8), 30)
            lines = []
            for raw_line in text.split("\n"):
                words = raw_line.split()
                current_line = ""
                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    if font_obj.measure(test_line) <= width_limit:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
            line_height = font_obj.metrics("linespace")
            total_height = len(lines) * line_height + 8
            cell_heights.append(total_height)

        row_height = max(cell_heights)
        row_height = max(row_height, 34)
        if row_index < len(self._row_y_positions):
            y = self._row_y_positions[row_index]
        else:
            y = start_y

        for i in range(len(headers)):
            x = x_positions[i]
            cell_tag = f"cell_{row_index}_{i}"
            canvas.create_rectangle(x, y, x + col_widths[i], y + row_height, fill="#ffffff", tags=(cell_tag,))

            text = str(row_data[i])
            width_limit = max(col_widths[i] - (30 if i == len(headers) - 1 else 8), 30)

            lines = []
            for raw_line in text.split("\n"):
                words = raw_line.split()
                current_line = ""
                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    if font_obj.measure(test_line) <= width_limit:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
            line_height = font_obj.metrics("linespace")
            total_height = len(lines) * line_height

            text_y_offset = max((row_height - total_height) // 2, 4)

            if i == len(headers) - 1:
                note_cell_tag = f"note_cell_{row_index}"
                canvas.create_text(
                    x + 4, y + text_y_offset,
                    anchor="nw",
                    text=text,
                    font=font_conf,
                    width=max(col_widths[i] - 36, 20),
                    justify="right",
                    fill="red",
                    tags=(note_cell_tag,)
                )
    
                if col_widths[i] >= 40:
                    icon_y = y + row_height // 2
                    canvas.create_text(
                        x + col_widths[i] - 4, icon_y,
                        anchor="e",
                        text="✏️",
                        font=("Segoe UI", 12, "bold"),
                        tags=(note_cell_tag,)
                    )

                canvas.tag_bind(
                    note_cell_tag, "<Button-1>",
                    lambda e, rx=row_index, xx=x, yy=y, ww=col_widths[i]:
                        (print(f"[DEBUG] Clicked ملاحظات/مواد row={rx} x={xx} y={yy}"), self._edit_notes_in_cell(rx, xx, yy, ww))
                )
            else:
                canvas.create_text(
                    x + 4, y + text_y_offset,
                    anchor="nw",
                    text=text,
                    font=font_conf,
                    width=col_widths[i] - 8,
                    justify="right",
                    tags=(cell_tag,)
                )
                if i == 0:
                    canvas.tag_bind(
                        cell_tag, "<Button-1>",
                        lambda e, rx=row_index, xx=x, yy=y:
                            (print(f"[DEBUG] Clicked الطبيب/المخبر row={rx} x={xx} y={yy}"), self._show_doctor_selector(rx, xx, yy))
                    )
                elif i == 1:
                    canvas.tag_bind(
                        cell_tag, "<Button-1>",
                        lambda e, rx=row_index, xx=x, yy=y:
                            (print(f"[DEBUG] Clicked Zeit row={rx} x={xx} y={yy}"), self._show_time_selector(rx, xx, yy))
                    )
                elif i == 2:
                    canvas.tag_bind(
                        cell_tag, "<Button-1>",
                        lambda e, rx=row_index, xx=x, yy=y:
                            (print(f"[DEBUG] Clicked المخبر row={rx} x={xx} y={yy}"), self._show_lab_selector(rx, xx, yy))
                    )
                elif i == 3:
                    canvas.tag_bind(
                        cell_tag, "<Button-1>",
                        lambda e, rx=row_index, xx=x, yy=y:
                            (print(f"[DEBUG] Clicked Beschreibung row={rx} x={xx} y={yy}"), self._show_material_selector(rx, xx, yy))
                    )

        return row_height

    def _draw_note_row(self, canvas, row_index, y):
        day = self.route_days[self.current_route_index]
        day_key = day.strftime("%Y-%m-%d")
        row_data = list(self.route_temp_data[day_key][row_index])

        font_conf = self._font_conf
        font_obj = self._font_obj
        total_width = sum(self._col_widths) + 30  # نضيف مساحة العمود الأول الخاص بأيقونة التحديد

        # ضمان وجود __note_only__
        if not str(row_data[5]).startswith("__note_only__"):
            row_data[5] = f"__note_only__\n{row_data[5]}"
            self.route_temp_data[day_key][row_index] = ["", "", "", "", "", row_data[5]]

        text_content = row_data[5].replace("__note_only__", "").lstrip()
        lines = text_content.split("\n") if text_content.strip() else [""]

        line_height = font_obj.metrics("linespace")
        padding = 18
        row_height = max(line_height, len(lines) * line_height) + padding

        note_tag = f"note_cell_{row_index}"

        # ارسم المستطيل للصف بالكامل
        canvas.create_rectangle(30, y, total_width, y + row_height, fill="#ffffff", tags=(note_tag,))

        # ✅ زر التحديد في أقصى اليسار (خارج الجدول)
        x0 = 15  # مسافة اليسار
        icon = "✅" if getattr(self, "_selected_route_row_index", None) == row_index else "🔘"
        canvas.create_text(x0, y + row_height // 2, anchor="center", text=icon, font=("Segoe UI", 11))

        # 📝 نص الملاحظة
        text_start_y = y + (padding // 2)
        canvas.create_text(
            30, text_start_y,
            anchor="nw",
            text=text_content,
            font=font_conf,
            width=total_width - 60,
            justify="right",
            fill="black",
            tags=(note_tag,)
        )

        # ✏️ أيقونة التحرير
        canvas.create_text(
            total_width - 20, text_start_y,
            anchor="ne",
            text="✏️",
            font=("Segoe UI", 12, "bold"),
            tags=(note_tag,)
        )

        canvas.tag_bind(note_tag, "<Button-1>", self._make_note_edit_callback(row_index))

        return y + row_height

    def _edit_notes_in_cell(self, row_index, x, y, width):
        import tkinter as tk
        from tkinter import ttk

        canvas = self.route_preview_canvas
        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")
        current_value = str(self.route_temp_data[day_key][row_index][-1])

        # ✅ إنشاء نافذة تابعة لنافذة البرنامج الرئيسية (ليست فوق كل شيء)
        popup = tk.Toplevel(canvas)
        popup.transient(canvas.winfo_toplevel())  # ✅ اجعلها تابعة لنافذة البرنامج
        popup.wm_title("تحرير الملاحظات")
        popup.geometry(f"{width-10}x200+{canvas.winfo_rootx()+x}+{canvas.winfo_rooty()+y+40}")
        popup.grab_set()

        # === إطار النص مع التمرير ===
        frame = tk.Frame(popup)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        text_area = tk.Text(frame, font=("Segoe UI", 9), wrap="char")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        text_area.pack(side="left", fill="both", expand=True)
        text_area.insert("1.0", current_value)
        text_area.focus_set()

        # === أزرار حفظ / إلغاء ===
        btn_frame = tk.Frame(popup)
        btn_frame.pack(fill="x", pady=5)

        def save_and_close():
            new_value = text_area.get("1.0", "end-1c").strip()
            updated_row = list(self.route_temp_data[day_key][row_index])
            updated_row[-1] = new_value
            self.route_temp_data[day_key][row_index] = tuple(updated_row)
            popup.destroy()
            self._draw_route_preview()

        ttk.Button(btn_frame, text="💾 حفظ", command=save_and_close).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=popup.destroy).pack(side="left", padx=5)

        # اختصارات لوحة المفاتيح
        text_area.bind("<Control-Return>", lambda e: save_and_close())
        text_area.bind("<Escape>", lambda e: popup.destroy())

        # تحديث الارتفاع تلقائيًا
        def auto_resize(event=None):
            lines = text_area.get("1.0", "end-1c").count('\n') + 1
            text_area.configure(height=min(max(3, lines), 15))

        text_area.bind("<KeyRelease>", auto_resize)
        auto_resize()

    def _close_all_selectors(self):
        # Doctor
        if hasattr(self, "_active_doctor_widget"):
            try:
                self.route_preview_canvas.delete(self._active_doctor_window_id)
            except Exception:
                pass
            del self._active_doctor_widget
            del self._active_doctor_window_id
        if hasattr(self, "_doctor_selector_binding"):
            try:
                self.route_preview_canvas.unbind("<Button-1>", self._doctor_selector_binding)
            except Exception:
                pass
            del self._doctor_selector_binding
        # Time
        if hasattr(self, "_active_time_selector"):
            try:
                self.route_preview_canvas.delete(self._active_time_window_id)
            except Exception:
                pass
            del self._active_time_selector
            del self._active_time_window_id
        if hasattr(self, "_time_selector_binding"):
            try:
                self.route_preview_canvas.unbind("<Button-1>", self._time_selector_binding)
            except Exception:
                pass
            del self._time_selector_binding
        # Lab
        if hasattr(self, "_active_lab_selector"):
            try:
                self.route_preview_canvas.delete(self._active_lab_window_id)
            except Exception:
                pass
            del self._active_lab_selector
            del self._active_lab_window_id
        if hasattr(self, "_lab_selector_binding"):
            try:
                self.route_preview_canvas.unbind("<Button-1>", self._lab_selector_binding)
            except Exception:
                pass
            del self._lab_selector_binding
        # Material
        if hasattr(self, "_active_material_selector"):
            try:
                self.route_preview_canvas.delete(self._active_material_window_id)
            except Exception:
                pass
            del self._active_material_selector
            del self._active_material_window_id
        if hasattr(self, "_material_selector_binding"):
            try:
                self.route_preview_canvas.unbind("<Button-1>", self._material_selector_binding)
            except Exception:
                pass
            del self._material_selector_binding

    def _show_doctor_selector(self, row_index, x, y):
        self._close_all_selectors()
        print(f"[DEBUG] _show_doctor_selector called row_index={row_index}, x={x}, y={y}")
        import tkinter as tk

        canvas = self.route_preview_canvas

        # 🧹 تنظيف أي حدث نقر مرتبط بـ binding سابق (من أي قائمة أخرى)
        for attr in [
            "_doctor_selector_binding",
            "_time_selector_binding",
            "_lab_selector_binding",
            "_material_selector_binding"
        ]:
            if hasattr(self, attr):
                try:
                    canvas.unbind("<Button-1>", getattr(self, attr))
                except Exception:
                    pass
                delattr(self, attr)

        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")

        # حذف أي قائمة سابقة
        if hasattr(self, "_active_doctor_widget"):
            canvas.delete(self._active_doctor_window_id)
            del self._active_doctor_widget
            del self._active_doctor_window_id

        # جلب كل الأطباء والمخابر
        all_doctors = self.get_all_doctor_names()
        all_labs = self.get_all_lab_names()
        doctor_items = [f"🧑‍⚕️ {name}" for name in all_doctors]
        lab_items = [f"🧪 {lab}" for lab in all_labs]
        special_delete_option = "🗑️ حذف هذا السطر"
        all_items = [special_delete_option] + doctor_items + lab_items

        # حساب العرض
        canvas.update_idletasks()
        canvas_width = canvas.winfo_width() or 1000
        column_ratios = [1.4, 0.8, 0.8, 1.4, 2, 2.6]
        total_ratio = sum(column_ratios)
        col_widths = [int(canvas_width * (r / total_ratio)) for r in column_ratios]
        doctor_col_width = col_widths[0]

        # الحاوية
        container = tk.Frame(canvas)
        widget_id = canvas.create_window(x + 2, y + 2, anchor="nw", window=container, width=doctor_col_width - 4)

        entry_var = tk.StringVar()
        entry = tk.Entry(container, textvariable=entry_var, font=("Segoe UI", 9))
        entry.pack(fill="x")

        listbox_frame = tk.Frame(container)
        listbox = tk.Listbox(listbox_frame, height=8, font=("Segoe UI", 9))
        scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
        listbox.config(yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        listbox_frame.pack(fill="both", expand=True)

        def update_listbox(*_):
            typed = entry_var.get().lower()
            listbox.delete(0, "end")
            for item in all_items:
                if typed in item.lower():
                    listbox.insert("end", item)

        entry_var.trace_add("write", update_listbox)
        update_listbox()

        # إغلاق عند النقر خارجًا
        def close_on_click_outside(event):
            print("[DEBUG] close_on_click_outside from doctor selector")
            if hasattr(self, "_active_doctor_widget") and hasattr(self, "_active_doctor_window_id"):
                x_click, y_click = event.x, event.y
                bbox = canvas.bbox(self._active_doctor_window_id)
                if bbox:
                    x1, y1, x2, y2 = bbox
                    if x1 <= x_click <= x2 and y1 <= y_click <= y2:
                        return  # النقر داخل النافذة
                canvas.delete(self._active_doctor_window_id)
                del self._active_doctor_widget
                del self._active_doctor_window_id
                self._draw_route_preview()
                # فك الربط بعد الإغلاق
                if hasattr(self, "_doctor_selector_binding"):
                    try:
                        canvas.unbind("<Button-1>", self._doctor_selector_binding)
                    except Exception:
                        pass
                    del self._doctor_selector_binding

        # canvas.bind("<Button-1>", close_on_click_outside, add="+")
    
        def on_select(event=None):
            selected = listbox.get("anchor").strip()
            print(f"[DEBUG] doctor selector selected: {selected}")
            if not selected:
                return
            elif selected == special_delete_option:
                del self.route_temp_data[day_key][row_index]
            elif selected.startswith("🧑‍⚕️ "):
                name = selected.replace("🧑‍⚕️ ", "")
                doctor = self.get_doctor_by_name(name)
                if doctor:
                    row = (
                        doctor["name"],
                        doctor["time"],
                        doctor["lab"],
                        "",
                        doctor["address"],
                        ""
                    )
                    self.route_temp_data[day_key][row_index] = row
            elif selected.startswith("🧪 "):
                lab_name = selected.replace("🧪 ", "")
                address = self.get_lab_address_by_name(lab_name)
                row = (lab_name, "", "", "", address, "")
                self.route_temp_data[day_key][row_index] = row

            canvas.delete(self._active_doctor_window_id)
            del self._active_doctor_widget
            del self._active_doctor_window_id
            self._draw_route_preview()
            if hasattr(self, "_doctor_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._doctor_selector_binding)
                except Exception:
                    pass
                del self._doctor_selector_binding

        listbox.bind("<Return>", on_select)
        listbox.bind("<Double-Button-1>", on_select)
        entry.bind("<Down>", lambda e: listbox.focus_set())
        entry.focus_set()

        self._active_doctor_widget = container
        self._active_doctor_window_id = widget_id
        # 🔁 فك الربط السابق إن وُجد
        def bind_close():
            if hasattr(self, "_doctor_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._doctor_selector_binding)
                except Exception:
                    pass
                del self._doctor_selector_binding
            self._doctor_selector_binding = canvas.bind("<Button-1>", close_on_click_outside)
        canvas.after(10, bind_close)

    def _show_time_selector(self, row_index, x, y):
        self._close_all_selectors()
        print(f"[DEBUG] _show_time_selector called row_index={row_index}, x={x}, y={y}")
        import tkinter as tk
        from tkinter import messagebox

        canvas = self.route_preview_canvas
    
        # 🧹 تنظيف أي حدث نقر مرتبط بـ binding سابق (من أي قائمة أخرى)
        for attr in [
            "_doctor_selector_binding",
            "_time_selector_binding",
            "_lab_selector_binding",
            "_material_selector_binding"
        ]:
            if hasattr(self, attr):
                try:
                    canvas.unbind("<Button-1>", getattr(self, attr))
                except Exception:
                    pass
                delattr(self, attr)

        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")

        if hasattr(self, "_active_time_selector"):
            canvas.delete(self._active_time_window_id)
            del self._active_time_selector
            del self._active_time_window_id

        options = ["bis", "von - bis", "ab", "nach Anruf", "Anschl."]
        time_values = self.get_all_doctor_times()

        canvas.update_idletasks()
        canvas_width = canvas.winfo_width() or 1000
        column_ratios = [1.4, 1.2, 0.8, 1.4, 2, 2.6]
        total_ratio = sum(column_ratios)
        col_widths = [int(canvas_width * (r / total_ratio)) for r in column_ratios]
        time_col_width = col_widths[1]

        frame = tk.Frame(canvas, bd=1, relief="solid", bg="white")
        window_id = canvas.create_window(x + 2, y + 2, anchor="nw", window=frame, width=time_col_width - 4)
        self._active_time_selector = frame
        self._active_time_window_id = window_id

        selected_option = tk.StringVar(value=options[0])
        selected_time_from = tk.StringVar(value=time_values[0] if time_values else "")
        selected_time_to = tk.StringVar(value=time_values[1] if len(time_values) > 1 else "")

        input_frame = tk.Frame(frame, bg="white")
        input_frame.pack(fill="both", expand=True)

        type_menu = tk.OptionMenu(input_frame, selected_option, *options)
        type_menu.config(font=("Segoe UI", 9), bg="white", activebackground="white", fg="black", activeforeground="black")
        type_menu.pack(fill="x")

        time_menu_from = tk.OptionMenu(input_frame, selected_time_from, selected_time_from.get(), *time_values)
        time_menu_from.config(font=("Segoe UI", 9), bg="white", activebackground="white", fg="black", activeforeground="black")

        time_menu_to = tk.OptionMenu(input_frame, selected_time_to, selected_time_to.get(), *time_values)
        time_menu_to.config(font=("Segoe UI", 9), bg="white", activebackground="white", fg="black", activeforeground="black")

        def update_ui(*_):
            for widget in (time_menu_from, time_menu_to):
                widget.pack_forget()
            if selected_option.get() == "von - bis":
                time_menu_from.pack(fill="x")
                time_menu_to.pack(fill="x")
            elif selected_option.get() in ("bis", "ab"):
                time_menu_from.pack(fill="x")

        selected_option.trace_add("write", update_ui)
        update_ui()

        button_frame = tk.Frame(frame, bg="white")
        button_frame.pack(fill="x", pady=4)

        def close_on_click_outside(event):
            print("[DEBUG] close_on_click_outside from time selector")
            if hasattr(self, "_active_time_window_id"):
                bbox = canvas.bbox(self._active_time_window_id)
                if bbox:
                    x1, y1, x2, y2 = bbox
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                        return  # النقر داخل النافذة
                canvas.delete(self._active_time_window_id)
                del self._active_time_selector
                del self._active_time_window_id
                self._draw_route_preview()
                # فك الربط بعد الإغلاق
                if hasattr(self, "_time_selector_binding"):
                    try:
                        canvas.unbind("<Button-1>", self._time_selector_binding)
                    except Exception:
                        pass
                    del self._time_selector_binding

        def apply_time():
            print(f"[DEBUG] apply_time called row_index={row_index}")
            prefix = selected_option.get()
            parent_window = canvas.winfo_toplevel()

            if prefix == "von - bis":
                t1 = selected_time_from.get()
                t2 = selected_time_to.get()
                try:
                    h1, m1 = map(int, t1.split(":"))
                    h2, m2 = map(int, t2.split(":"))
                    if (h2, m2) <= (h1, m1):
                        self.route_preview_canvas.update_idletasks()
                        messagebox.showerror("خطأ في الوقت", "يجب أن يكون bis بعد von.", parent=parent_window)
                        return
                except:
                    messagebox.showerror("خطأ في التنسيق", "صيغة الوقت غير صحيحة.", parent=parent_window)
                    return
                suffix = f"{t1} - {t2}"
            elif prefix == "nach Anruf":
                doctor_name = self.route_temp_data[day_key][row_index][0].strip()
                doctor = self.get_doctor_by_name(doctor_name) if doctor_name else {}
                phone = doctor.get("phone", "").strip()
                suffix = f"nach Anruf 📞 {phone}" if phone else "nach Anruf"
            elif prefix in ("bis", "ab"):
                suffix = selected_time_from.get()
            else:
                suffix = ""

            value = f"{prefix} {suffix}".strip()
            current_row = list(self.route_temp_data[day_key][row_index])
            current_row[1] = value
            self.route_temp_data[day_key][row_index] = tuple(current_row)

            # ✅ إعادة الترتيب حسب الوقت
            self.route_temp_data[day_key].sort(key=lambda row: self._extract_sort_time(row[1]))

            # ✅ إلغاء التحديد اليدوي
            self._selected_route_row_index = None

            # إغلاق نافذة الوقت وإعادة رسم الجدول
            canvas.delete(window_id)
            del self._active_time_selector
            del self._active_time_window_id
            self._draw_route_preview()

            if hasattr(self, "_time_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._time_selector_binding)
                except Exception:
                    pass
                del self._time_selector_binding

        tk.Button(button_frame, text="✔️ تم", command=apply_time, bg="white").pack()

        # ✅ فك الربط السابق إن وُجد
        if hasattr(self, "_time_selector_binding"):
            try:
                canvas.unbind("<Button-1>", self._time_selector_binding)
            except Exception:
                pass
            del self._time_selector_binding

        def bind_close():
            if hasattr(self, "_time_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._time_selector_binding)
                except Exception:
                    pass
                del self._time_selector_binding
            self._time_selector_binding = canvas.bind("<Button-1>", close_on_click_outside)
        canvas.after(10, bind_close)

    def _show_lab_selector(self, row_index, x, y):
        self._close_all_selectors()
        print(f"[DEBUG] _show_lab_selector called row_index={row_index}, x={x}, y={y}")
        import tkinter as tk

        canvas = self.route_preview_canvas
    
        # 🧹 تنظيف أي حدث نقر مرتبط بـ binding سابق (من أي قائمة أخرى)
        for attr in [
            "_doctor_selector_binding",
            "_time_selector_binding",
            "_lab_selector_binding",
            "_material_selector_binding"
        ]:
            if hasattr(self, attr):
                try:
                    canvas.unbind("<Button-1>", getattr(self, attr))
                except Exception:
                    pass
                delattr(self, attr)

        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")

        # حذف أي قائمة سابقة
        if hasattr(self, "_active_lab_selector"):
            canvas.delete(self._active_lab_window_id)
            del self._active_lab_selector
            del self._active_lab_window_id

        # جلب المخابر من التبويب
        lab_items = self.get_all_lab_names()

        # حساب عرض العمود الثالث (المخبر)
        canvas.update_idletasks()
        canvas_width = canvas.winfo_width() or 1000
        column_ratios = [1.4, 0.8, 0.8, 1.4, 2, 2.6]
        total_ratio = sum(column_ratios)
        col_widths = [int(canvas_width * (r / total_ratio)) for r in column_ratios]
        lab_col_width = col_widths[2]

        # الحاوية
        frame = tk.Frame(canvas, bd=1, relief="solid", bg="white")
        window_id = canvas.create_window(x + 2, y + 2, anchor="nw", window=frame, width=lab_col_width - 4)

        # حقل إدخال
        entry_var = tk.StringVar()
        entry = tk.Entry(frame, textvariable=entry_var, font=("Segoe UI", 9))
        entry.pack(fill="x", padx=2, pady=(2, 0))
        entry.focus_set()

        # Listbox مع Scrollbar
        listbox_frame = tk.Frame(frame)
        listbox_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        listbox = tk.Listbox(listbox_frame, height=8, font=("Segoe UI", 9))
        scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
        listbox.config(yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # فلترة القائمة
        def update_listbox(*_):
            typed = entry_var.get().strip().lower()
            listbox.delete(0, "end")
            for item in lab_items:
                if typed in item.lower():
                    listbox.insert("end", item)

        entry_var.trace_add("write", update_listbox)
        update_listbox()

        # عند الاختيار
        def on_select(event=None):
            print(f"[DEBUG] lab selector selected: {listbox.curselection()}")
            if not listbox.curselection():
                return
            selected_lab = listbox.get(listbox.curselection())
            current_row = list(self.route_temp_data[day_key][row_index])
            current_row[2] = selected_lab  # العمود الثالث = المخبر
            self.route_temp_data[day_key][row_index] = tuple(current_row)
            canvas.delete(window_id)
            del self._active_lab_selector
            del self._active_lab_window_id
            self._draw_route_preview()
            # فك الربط بعد الإغلاق
            if hasattr(self, "_lab_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._lab_selector_binding)
                except Exception:
                    pass
                del self._lab_selector_binding

        listbox.bind("<Double-Button-1>", on_select)
        listbox.bind("<Return>", on_select)

        # إغلاق عند النقر خارجًا
        def close_on_click_outside(event):
            print("[DEBUG] close_on_click_outside from lab selector")
            if hasattr(self, "_active_lab_window_id"):
                bbox = canvas.bbox(self._active_lab_window_id)
                if bbox:
                    x1, y1, x2, y2 = bbox
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                        return  # النقر داخل النافذة
                canvas.delete(self._active_lab_window_id)
                del self._active_lab_selector
                del self._active_lab_window_id
                self._draw_route_preview()
                # فك الربط بعد الإغلاق
                if hasattr(self, "_lab_selector_binding"):
                    try:
                        canvas.unbind("<Button-1>", self._lab_selector_binding)
                    except Exception:
                        pass
                    del self._lab_selector_binding

        # canvas.bind("<Button-1>", close_if_click_outside, add="+")

        self._active_lab_selector = frame
        self._active_lab_window_id = window_id
    
        # ✅ فك الربط السابق إن وُجد
        if hasattr(self, "_lab_selector_binding"):
            try:
                canvas.unbind("<Button-1>", self._lab_selector_binding)
            except Exception:
                pass
            del self._lab_selector_binding
    
        # ✅ ربط مباشر بدون تأخير
        def bind_close():
            if hasattr(self, "_lab_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._lab_selector_binding)
                except Exception:
                    pass
                del self._lab_selector_binding
            self._lab_selector_binding = canvas.bind("<Button-1>", close_on_click_outside)
        canvas.after(10, bind_close)        

    def _show_material_selector(self, row_index, x, y):
        self._close_all_selectors()
        print(f"[DEBUG] _show_material_selector called row_index={row_index}, x={x}, y={y}")
        import tkinter as tk

        canvas = self.route_preview_canvas

        # 🧹 تنظيف أي حدث نقر مرتبط بـ binding سابق (من أي قائمة أخرى)
        for attr in [
            "_doctor_selector_binding",
            "_time_selector_binding",
            "_lab_selector_binding",
            "_material_selector_binding"
        ]:
            if hasattr(self, attr):
                try:
                    canvas.unbind("<Button-1>", getattr(self, attr))
                except Exception:
                    pass
                delattr(self, attr)

        current_date = self.route_days[self.current_route_index]
        day_key = current_date.strftime("%Y-%m-%d")

        # حذف أي نافذة سابقة
        if hasattr(self, "_active_material_selector"):
            canvas.delete(self._active_material_window_id)
            del self._active_material_selector
            del self._active_material_window_id

        # ✅ المواد المتاحة دائمًا
        material_options = [
            "BOX", "BAK-Dose", "Schachtel", "Befunde", "Rote Box", "Ständer", "Kiste"
        ]

        # اسم الطبيب
        doctor_name = self.route_temp_data[day_key][row_index][0].strip()
        doctor = self.get_doctor_by_name(doctor_name) if doctor_name else {}

        # ✅ المواد المحددة مسبقًا
        selected = doctor.get("materials", "").split(",") if doctor else []
        selected = [m.strip() for m in selected if m.strip()]

        # الحاوية
        frame = tk.Frame(canvas, bd=1, relief="solid", bg="white")
        window_id = canvas.create_window(x + 2, y + 2, anchor="nw", window=frame)
        self._active_material_selector = frame
        self._active_material_window_id = window_id

        vars = []
        for item in material_options:
            var = tk.BooleanVar(value=item in selected)
            chk = tk.Checkbutton(frame, text=item, variable=var, font=("Segoe UI", 9), bg="white")
            chk.pack(anchor="w")
            vars.append((item, var))

        def apply_selection():
            print(f"[DEBUG] apply_selection in material selector row_index={row_index}")
            selected_items = [item for item, var in vars if var.get()]
            current_row = list(self.route_temp_data[day_key][row_index])
            current_row[3] = ", ".join(selected_items)
            self.route_temp_data[day_key][row_index] = tuple(current_row)
            canvas.delete(window_id)
            del self._active_material_selector
            del self._active_material_window_id
            self._draw_route_preview()
    
            if hasattr(self, "_material_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._material_selector_binding)
                except Exception:
                    pass
                del self._material_selector_binding

        btn = tk.Button(frame, text="✔️ تم", command=apply_selection, bg="white")
        btn.pack(pady=4)

        def close_on_click_outside(event):
            print("[DEBUG] close_on_click_outside from material selector")
            if hasattr(self, "_active_material_window_id"):
                bbox = canvas.bbox(self._active_material_window_id)
                if bbox:
                    x1, y1, x2, y2 = bbox
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                        return  # النقر داخل النافذة
                canvas.delete(self._active_material_window_id)
                del self._active_material_selector
                del self._active_material_window_id
                self._draw_route_preview()
                # فك الربط بعد الإغلاق
                if hasattr(self, "_material_selector_binding"):
                    try:
                        canvas.unbind("<Button-1>", self._material_selector_binding)
                    except Exception:
                        pass
                    del self._material_selector_binding

        # canvas.bind("<Button-1>", close_if_click_outside, add="+")

        # ✅ فك الربط السابق إن وُجد
        if hasattr(self, "_material_selector_binding"):
            try:
                canvas.unbind("<Button-1>", self._material_selector_binding)
            except Exception:
                pass
            del self._material_selector_binding

        # ✅ ربط مباشر بدون تأخير
        def bind_close():
            if hasattr(self, "_material_selector_binding"):
                try:
                    canvas.unbind("<Button-1>", self._material_selector_binding)
                except Exception:
                    pass
                del self._material_selector_binding
            self._material_selector_binding = canvas.bind("<Button-1>", close_on_click_outside)
        canvas.after(10, bind_close)
    
    def _extract_sort_time(self, time_str):
        import re
        if not time_str or not isinstance(time_str, str):
            return (99, 99)  # ضع غير المحددين في النهاية

        match = re.search(r"(\d{2}):(\d{2})", time_str)
        if match:
            return tuple(map(int, match.groups()))
        return (99, 99)

    def get_all_doctor_names(self):
        import sqlite3
        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM doctors")
                return [row[0] for row in c.fetchall()]
        except Exception as e:
            self.show_message("error", f"فشل جلب أسماء الأطباء: {e}")
            return []

    def get_doctor_by_name(self, name):
        import sqlite3
        import json
        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT name, weekday_times, visit_type, labs, materials,
                           street, city, zip_code, phone
                    FROM doctors WHERE name = ?
                """, (name,))
                row = c.fetchone()
                if row:
                    full_address = f"{row[7]} {row[6]}, {row[5]}"
                    materials_text = row[4]
                    if materials_text and materials_text.strip().startswith("["):
                        try:
                            materials_list = json.loads(materials_text)
                            materials_text = ", ".join(materials_list)
                        except:
                            pass
                    return {
                        "name": row[0],
                        "time": row[1],
                        "desc": row[2],
                        "lab": row[3],
                        "materials": materials_text,
                        "notes": "",
                        "address": full_address,
                        "phone": row[8] or ""
                    }
        except Exception as e:
            self.show_message("error", f"فشل جلب بيانات الطبيب '{name}': {e}")
            return None

    def get_all_doctor_times(self):
        times = []
        for hour in range(7, 18):  # من 7 إلى 17 (يشمل)
            times.append(f"{hour:02d}:00")
            times.append(f"{hour:02d}:30")
        return times

    def _update_notes_from_widgets(self):
        """تحديث عمود الملاحظات من Text widgets إلى self.route_temp_data"""
        day = self.route_days[self.current_route_index]
        day_key = day.strftime("%Y-%m-%d")

        if day_key not in self.route_temp_data:
            return

        rows = self.route_temp_data[day_key]
        for row_index, (text_widget, _) in enumerate(self._notes_vars):  # ✅ استخراج Text فقط
            if row_index < len(rows):
                notes_text = text_widget.get("1.0", "end-1c").strip()
                rows[row_index] = list(rows[row_index])
                rows[row_index][-1] = notes_text

    def _update_route_start_hour(self):
        if not hasattr(self, "_route_inputs") or not hasattr(self, "route_days") or not hasattr(self, "current_route_index"):
            return

        combo = self._route_inputs.get("start_hour_combo")
        if not combo:
            return

        day_key = self.route_days[self.current_route_index].strftime("%Y-%m-%d")
        self.route_start_hours[day_key] = combo.get().strip()

    def _save_full_route(self, apply_only=False):
        import sqlite3
        import json

        name = self._route_inputs["name_entry"].get().strip()
        driver = self._route_inputs["driver_combo"].get().strip()

        if not name:
            self.show_message("warning", "❌ يرجى إدخال اسم Route.")
            return

        if not hasattr(self, "route_driver_names") or not hasattr(self, "route_start_hours"):
            self.show_message("error", "❌ بيانات السائق أو بداية العمل غير متوفرة.")
            return

        has_data = any(self.route_temp_data.get(day.strftime("%Y-%m-%d"), []) for day in self.route_days)
        if not has_data:
            self.show_message("warning", "❌ لا توجد بيانات لحفظ Route.")
            return

        editing_mode = hasattr(self, "_editing_route_id") and self._editing_route_id is not None
        self._update_notes_from_widgets()
        self._update_route_start_hour()

        # ✅ تحقق من أن جميع الأيام تحتوي على بداية عمل وسائق
        for date in self.route_days:
            day_key = date.strftime("%Y-%m-%d")
            rows = self.route_temp_data.get(day_key, [])
            if not rows:
                continue

            start_hour = self.route_start_hours.get(day_key, "").strip()
            if not start_hour:
                self.show_message("warning", f"❌ يرجى تحديد بداية العمل ليوم {day_key}.")
                return

            driver_name = self.route_driver_names.get(day_key, "").strip()
            if not driver_name:
                self.show_message("warning", f"❌ يرجى اختيار السائق ليوم {day_key}.")
                return

        # ✅ فحص اكتمال الأيام غير العطل (لحفظ فقط)
        if not apply_only:
            missing_days = []
            for date in self.route_days:
                day_key = date.strftime("%Y-%m-%d")
                rows = self.route_temp_data.get(day_key, [])
                if not rows and date.weekday() not in (5, 6):  # استثناء السبت والأحد
                    missing_days.append(day_key)

            if missing_days:
                self.show_message("warning", "⚠️ الأيام التالية لا تحتوي على بيانات:\n" + "\n".join(missing_days))
                return

            # ✅ تأكيد الحفظ
            msg = "هل أنت متأكد أنك تريد تعديل هذا الـ Route؟" if editing_mode else "هل أنت متأكد أنك تريد حفظ هذا الـ Route؟"
            if not self.show_custom_confirm("تأكيد الحفظ", msg):
                return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()

                if editing_mode:
                    c.execute("DELETE FROM routes WHERE id = ?", (self._editing_route_id,))
                    c.execute("DELETE FROM route_days WHERE route_id = ?", (self._editing_route_id,))
                    c.execute("DELETE FROM route_tasks WHERE route_name = ? AND driver = ?", (name, driver))
                    route_id = self._editing_route_id
                else:
                    c.execute("DELETE FROM routes WHERE name = ? AND driver = ?", (name, driver))
                    c.execute("DELETE FROM route_tasks WHERE route_name = ? AND driver = ?", (name, driver))
                    first_date = self.route_days[0].strftime("%Y-%m-%d")
                    c.execute("""
                        INSERT INTO routes (name, date, driver)
                        VALUES (?, ?, ?)
                    """, (name, first_date, driver))
                    route_id = c.lastrowid

                for date in self.route_days:
                    day_key = date.strftime("%Y-%m-%d")
                    rows = self.route_temp_data.get(day_key, [])
                    if not rows:
                        continue

                    start_hour = self.route_start_hours.get(day_key, "").strip()
                    driver_name = self.route_driver_names.get(day_key, "").strip()

                    day_data = {
                        "rows": rows,
                        "driver": driver_name,
                        "start": start_hour
                    }
                    c.execute("""
                        INSERT INTO route_days (route_id, day, data)
                        VALUES (?, ?, ?)
                    """, (route_id, day_key, json.dumps(day_data, ensure_ascii=False)))

                    for row in rows:
                        doctor, time, lab, desc, address, notes = row
                        if isinstance(notes, list):
                            notes = ", ".join(notes)
                        elif isinstance(notes, str) and notes.startswith("[") and notes.endswith("]"):
                            try:
                                notes_list = json.loads(notes)
                                if isinstance(notes_list, list):
                                    notes = ", ".join(str(item) for item in notes_list)
                            except:
                                pass
                        c.execute("""
                            INSERT INTO route_tasks (route_name, date, driver, name, time, lab, description, address, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (name, day_key, driver_name, doctor, time, lab, desc, address, notes))

                conn.commit()

            if editing_mode and not apply_only:
                del self._editing_route_id

            if not apply_only:
                self._route_popup.destroy()
                self._update_add_edit_route_btn()
                self._refresh_route_cards()
                self.show_message("success", "✅ تم حفظ Route بنجاح.")
            else:
                self._refresh_route_cards()
                self.show_message("info", "✅ تم تطبيق التغييرات.\nيمكنك المتابعة أو الضغط على 'حفظ' لاحقًا.")

        except Exception as e:
            self.show_message("error", f"حدث خطأ أثناء الحفظ:\n{e}")

    def _print_route_pdf(self):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        import tempfile, os

        if not self.route_days:
            self.show_message("info", "🚫 لا توجد بيانات Route للطباعة.")
            return

        self._update_notes_from_widgets()

        styles = getSampleStyleSheet()
        wrapped_style = ParagraphStyle(name='Wrapped', fontName='Helvetica', fontSize=9, wordWrap='CJK', leading=12)
        red_style = ParagraphStyle(name='Red', fontName='Helvetica', fontSize=9, textColor=colors.red, wordWrap='CJK', leading=13, spaceAfter=2,)

        headers = ["الطبيب / المخبر", "Zeit", "المخبر", "Beschreibung", "العنوان", "ملاحظات/مواد"]
        all_data = []

        for day in self.route_days:
            day_key = day.strftime("%Y-%m-%d")
            rows = self.route_temp_data.get(day_key, [])
            if not rows:
                continue

            try:
                driver = self.route_driver_names.get(day_key, self._route_inputs["driver_combo"].get())
                start_hour = self.route_start_hours.get(day_key, self._route_inputs["start_hour_combo"].get())
            except:
                driver = self.route_driver_names.get(day_key, "-")
                start_hour = self.route_start_hours.get(day_key, "-")

            weekday_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
            readable_date = f"{weekday_names[day.weekday()]} - {day.strftime('%d-%m-%Y')}"

            table_data = [headers]
            for row in rows:
                formatted_row = []
                for i, cell in enumerate(row):
                    style = red_style if i == 5 else wrapped_style

                    cell = str(cell)
                    if i == 5 and cell.startswith("__note_only__"):
                        cell = cell.replace("__note_only__", "").lstrip()

                    cell = cell.replace("\n", "<br/>")
                    if not cell.strip():
                        cell = "&nbsp;"
                    para = Paragraph(cell, style)
                    formatted_row.append(para)
                table_data.append(formatted_row)

            all_data.append({
                "date": readable_date,
                "driver": driver,
                "start": start_hour,
                "table": table_data
            })

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        doc = SimpleDocTemplate(temp_file.name, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=50, bottomMargin=30)
        elements = []

        for entry in all_data:
            header_table = Table([
                [
                    Paragraph(f"📅 {entry['date']}", styles["Normal"]),
                    Paragraph(f"🕘 بداية العمل: {entry['start']}", styles["Normal"]),
                    Paragraph(f"🚗 السائق: {entry['driver']}", styles["Normal"])
                ]
            ], colWidths=[200, 350, 200])
            header_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 12))

            t = Table(entry["table"], repeatRows=1, colWidths='*')
            style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),  # ✅ توسيط أسماء الأعمدة أفقيًا
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),  # ✅ توسيط أسماء الأعمدة عموديًا
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ])
            t.setStyle(style)
            elements.append(t)
            elements.append(Spacer(1, 30))

        doc.build(elements)
        os.startfile(temp_file.name)

    def _main_preview_load_driver(self):
        import sqlite3
        from datetime import datetime, timedelta

        driver = self.main_driver_combo.get().strip()
        if not driver:
            return

        self.main_preview_driver = driver
        self.main_preview_days = []

        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday())  # الإثنين

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()

            for i in range(5):  # من الإثنين إلى الجمعة
                current_date = start_of_week + timedelta(days=i)
                date_str = current_date.strftime("%Y-%m-%d")

                # تحقق من العطل العامة
                c.execute("SELECT 1 FROM holidays WHERE date = ?", (date_str,))
                if c.fetchone():
                    continue

                # تحقق من عطلة السائق
                c.execute("""
                    SELECT 1 FROM vacations
                    WHERE name = ? AND ? BETWEEN from_date AND to_date
                """, (driver, date_str))
                if c.fetchone():
                    continue

                # تحقق من عطلة الطبيب لأي مهمة في ذلك اليوم
                c.execute("""
                    SELECT doctor FROM driver_tasks
                    WHERE driver = ? AND date = ?
                """, (driver, date_str))
                doctors = c.fetchall()
    
                skip_day = False
                for (doc_name,) in doctors:
                    c.execute("""
                        SELECT 1 FROM vacations
                        WHERE name = ? AND ? BETWEEN from_date AND to_date
                    """, (doc_name, date_str))
                    if c.fetchone():
                        skip_day = True
                        break

                if skip_day:
                    continue

                # إذا وصلنا هنا، نضيف هذا اليوم
                self.main_preview_days.append(current_date)

        self.main_preview_index = 0
        self._main_preview_draw_day()

    def _main_preview_draw_day(self):
        from datetime import datetime
        import sqlite3

        self.preview_canvas.delete("all")

        if not self.main_preview_days or self.main_preview_index >= len(self.main_preview_days):
            self.day_label.config(text="❌ لا توجد أيام")
            return

        date = self.main_preview_days[self.main_preview_index]
        date_str = date.strftime("%Y-%m-%d")

        weekday_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        weekday_name = weekday_names[date.weekday()]
        readable_date = date.strftime("%d/%m/%Y")
        self.day_label.config(text=f"{weekday_name} - {readable_date}")


        # ==== تحميل المهام من قاعدة البيانات ====
        tasks = []
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT doctor, lab, time, materials, address
                FROM driver_tasks
                WHERE driver = ? AND date = ?
                ORDER BY time
            """, (self.main_preview_driver, date_str))
            tasks = c.fetchall()

        # ==== إعدادات الرسم ====
        canvas = self.preview_canvas
        canvas_width = 595
        canvas_height = 842

        x0 = 20
        y0 = 60
        row_height = 30
        col_widths = [100, 70, 130, 100, 120, 130]

        headers = ["اسم الطبيب", "Zeit", "Beschreibung", "المخبر", "العنوان", "المواد / ملاحظات"]

        # ==== رأس الصفحة ====
        canvas.create_text(50, 30, text=f"🚗 السائق: {self.main_preview_driver}", anchor="w", font=("Arial", 10, "bold"))
        canvas.create_text(canvas_width - 50, 30, text=f"{weekday_name} - {readable_date}", anchor="e", font=("Arial", 10, "bold"))
        canvas.create_text(canvas_width // 2, 50, text="🕓 ساعة بداية العمل: ____________", font=("Arial", 10))

        # ==== رسم رؤوس الأعمدة ====
        x = x0
        y = y0
        for i, header in enumerate(headers):
            canvas.create_rectangle(x, y, x + col_widths[i], y + row_height, fill="#ddd")
            canvas.create_text(x + 4, y + row_height // 2, text=header, anchor="w", font=("Arial", 9, "bold"))
            x += col_widths[i]

        # ==== رسم الصفوف ====
        y += row_height
        for task in tasks:
            x = x0
            for i, item in enumerate(task):
                text = str(item) if item else ""
                canvas.create_rectangle(x, y, x + col_widths[i], y + row_height)
                canvas.create_text(x + 4, y + row_height // 2, text=text, anchor="w", font=("Arial", 9))
                x += col_widths[i]
            y += row_height

    def _main_preview_prev_day(self):
        if self.main_preview_index > 0:
            self.main_preview_index -= 1
            self._main_preview_draw_day()

    def _main_preview_next_day(self):
        if self.main_preview_index < len(self.main_preview_days) - 1:
            self.main_preview_index += 1
            self._main_preview_draw_day()

    def _retire_selected_car(self):
        plate = self.retire_plate_combo.get().strip()
        retire_date = self.retire_date_picker.get().strip()
        extra_note = self.retire_notes_entry.get().strip()

        if not plate or not retire_date:
            self.show_message("warning", "يرجى اختيار رقم اللوحة وتاريخ إخراج السيارة من الخدمة.")
            return

        try:
            retire_dt = datetime.strptime(retire_date, "%Y-%m-%d")
        except ValueError:
            self.show_message("error", "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.")
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

        self.show_message("success", f"✅ تم إخراج السيارة عن الخدمة {plate} من الخدمة بتاريخ {retire_date}")

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
        form_frame.columnconfigure(1, weight=1)

        # رقم اللوحة
        ttk.Label(form_frame, text="رقم اللوحة:").grid(row=0, column=0, sticky="e", pady=4, padx=5)
        license_plate_entry = tb.Entry(form_frame, width=20)  # ← عرض أصغر
        license_plate_entry.grid(row=0, column=1, sticky="w", pady=4, padx=5)  # ← بدون تمدد
        self.car_entries.append(license_plate_entry)

        # Autobahn Pickerl من
        ttk.Label(form_frame, text="Autobahn Pickerl من:").grid(row=1, column=0, sticky="e", pady=4, padx=5)
        from_autobahn = CustomDatePicker(form_frame)
        from_autobahn.grid(row=1, column=1, sticky="ew", pady=4, padx=5)
        self.car_entries.append(from_autobahn.entry)

        # Autobahn Pickerl إلى
        ttk.Label(form_frame, text="Autobahn Pickerl إلى:").grid(row=2, column=0, sticky="e", pady=4, padx=5)
        to_autobahn = CustomDatePicker(form_frame)
        to_autobahn.grid(row=2, column=1, sticky="ew", pady=4, padx=5)
        self.car_entries.append(to_autobahn.entry)

        # Jährlich Pickerl حتى
        ttk.Label(form_frame, text="Jährlich Pickerl حتى:").grid(row=3, column=0, sticky="e", pady=4, padx=5)
        yearly_pickerl = CustomDatePicker(form_frame)
        yearly_pickerl.grid(row=3, column=1, sticky="ew", pady=4, padx=5)
        self.car_entries.append(yearly_pickerl.entry)

        # ملاحظات
        ttk.Label(form_frame, text="ملاحظات:").grid(row=4, column=0, sticky="ne", pady=4, padx=5)
        notes_entry = tb.Entry(form_frame)
        notes_entry.grid(row=4, column=1, sticky="ew", pady=4, padx=5)
        self.car_entries.append(notes_entry)

        # زر الحفظ
        ttk.Button(form_frame, text="💾 حفظ بيانات السيارة", style="Green.TButton", command=self.save_car_data).grid(row=5, column=0, columnspan=2, pady=15)

        # === إطار "📅 إضافة موعد" ===
        appointment_frame = ttk.LabelFrame(top_container, text="📅 إضافة موعد", padding=15)
        appointment_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        appointment_frame.columnconfigure(1, weight=1)

        # رقم اللوحة
        ttk.Label(appointment_frame, text="رقم اللوحة:").grid(row=0, column=0, sticky="e", pady=4, padx=5)
        self.car_plate_combo = ttk.Combobox(appointment_frame, values=self.get_all_license_plates(), state="readonly", width=20)
        self.car_plate_combo.grid(row=0, column=1, sticky="w", pady=4, padx=5)

        # تاريخ الموعد ← أولاً
        ttk.Label(appointment_frame, text="تاريخ الموعد:").grid(row=1, column=0, sticky="e", pady=4, padx=5)
        self.appointment_date_picker = CustomDatePicker(appointment_frame)
        self.appointment_date_picker.grid(row=1, column=1, sticky="ew", pady=4, padx=5)

        # نوع الموعد ← تحته مباشرة
        ttk.Label(appointment_frame, text="نوع الموعد:").grid(row=2, column=0, sticky="e", pady=4, padx=5)
        self.appointment_type_entry = tb.Entry(appointment_frame)
        self.appointment_type_entry.grid(row=2, column=1, sticky="ew", pady=4, padx=5)

        # زر الإضافة
        ttk.Button(appointment_frame, text="💾 إضافة الموعد", style="Green.TButton", command=self._add_appointment).grid(row=3, column=0, columnspan=2, pady=15)

        # === إطار "📤 إخراج السيارة" ===
        retire_frame = ttk.LabelFrame(top_container, text="📤 إخراج السيارة", padding=15)
        retire_frame.grid(row=0, column=2, sticky="nsew")
        retire_frame.columnconfigure(1, weight=1)

        # اختر السيارة
        ttk.Label(retire_frame, text="رقم اللوحة:").grid(row=0, column=0, sticky="e", pady=4, padx=5)
        self.retire_plate_combo = ttk.Combobox(retire_frame, values=self.get_all_license_plates(), state="readonly", width=20)
        self.retire_plate_combo.grid(row=0, column=1, sticky="w", pady=4, padx=5)

        # تاريخ الإخراج
        ttk.Label(retire_frame, text="تاريخ الإخراج:").grid(row=1, column=0, sticky="e", pady=4, padx=5)
        self.retire_date_picker = CustomDatePicker(retire_frame)
        self.retire_date_picker.grid(row=1, column=1, sticky="ew", pady=4, padx=5)

        # ملاحظات إضافية
        ttk.Label(retire_frame, text="ملاحظات إضافية:").grid(row=2, column=0, sticky="ne", pady=4, padx=5)
        self.retire_notes_entry = tb.Entry(retire_frame)
        self.retire_notes_entry.grid(row=2, column=1, sticky="ew", pady=4, padx=5)

        # زر موافق
        ttk.Button(retire_frame, text="💾 موافق", style="Red.TButton", command=self._retire_selected_car).grid(row=3, column=0, columnspan=2, pady=15)

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

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.car_table.yview, style="TScrollbar")
        vsb.pack(side="right", fill="y")
        self.car_table.configure(yscrollcommand=vsb.set)

        self.configure_tree_columns(self.car_table, labels)
        self.apply_alternate_row_colors(self.car_table)

        bottom_controls = tb.Frame(table_frame)
        bottom_controls.pack(fill="x", pady=(10, 10))

        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.car_table)

        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)

        ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton", command=lambda: self._print_car_table("current")).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="📁 عرض السيارات المؤرشفة", style="info.TButton", command=self._toggle_archived_cars_window).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="📝 تعديل السيارة", style="Purple.TButton", command=self._edit_car_record).pack(side="left", padx=10)

        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

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

        # تحميل السيارات المؤرشفة من قاعدة البيانات
        def load_archived_cars(tree):
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

        self.build_table_window_with_search(
            title="📁 السيارات المؤرشفة",
            width=1000,
            height=500,
            columns=columns,
            column_labels=labels,
            reload_callback=load_archived_cars,
            export_title="السيارات المؤرشفة"
        )

        self.archived_cars_window = self.winfo_children()[-1]

    def _save_main_task(self):
        import sqlite3
        from tkinter import messagebox

        values = [e.get().strip() if hasattr(e, 'get') else e.get() for e in self.main_entries]
        if not all(values[:5]):
            self.show_message("warning", "يرجى ملء الحقول الأساسية (الطبيب، المخبر، السائق، التاريخ، Zeit)")
            return

        doctor, lab, driver, date_str, time, materials, address = values

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO driver_tasks (doctor, lab, driver, date, time, materials, address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (doctor, lab, driver, date_str, time, materials, address))
                conn.commit()
        except Exception as e:
            self.show_message("error", f"حدث خطأ أثناء حفظ المهمة:\n{e}")
            return

        self.show_message("info", "✅ تم حفظ المهمة بنجاح.")

        # تحديث المعاينة مباشرةً إذا كانت المهمة للسائق نفسه واليوم المعروض
        if driver == self.main_preview_driver:
            if any(d.strftime("%Y-%m-%d") == date_str for d in self.main_preview_days):
                self._main_preview_draw_day()

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
                self.show_message("warning", f"الرجاء إدخال {label} (حقل إلزامي).")
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
            self.show_message("success", f"✅ تم حفظ السيارة: {data[0]}")
            self.check_warnings()
            self._check_alerts()
            self._check_appointments()
            self.car_plate_combo['values'] = self.get_all_license_plates()
            self.retire_plate_combo['values'] = self.get_all_license_plates()

        except Exception as e:
            self.show_message("error", f"فشل الحفظ:\n{e}")
            return

        for e in self.car_entries:
            e.delete(0, tb.END)

    def _add_appointment(self):
        plate = self.car_plate_combo.get().strip()
        appt_type = self.appointment_type_entry.get().strip()
        appt_date = self.appointment_date_picker.get().strip()

        if not plate or not appt_type or not appt_date:
            self.show_message("warning", "يرجى إدخال كافة الحقول.")
            return

        # تحقق من تنسيق التاريخ
        try:
            datetime.strptime(appt_date, "%Y-%m-%d")
        except ValueError:
            self.show_message("error", "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.")
            return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO car_appointments (license_plate, appointment_type, appointment_date)
                    VALUES (?, ?, ?)
                """, (plate, appt_type, appt_date))
                conn.commit()

            self.show_message("success", f"✅ تم حفظ الموعد لرقم اللوحة: {plate}")
    
            # إعادة تعيين الحقول
            self.car_plate_combo.set("")
            self.appointment_type_entry.delete(0, tb.END)
            self.appointment_date_picker.entry.delete(0, tb.END)
            self._check_appointments()

        except Exception as e:
            self.show_message("error", f"فشل الحفظ:\n{e}")

    def _edit_car_record(self):
        selected = self.car_table.selection()
        if not selected:
            self.show_message("warning", "يرجى اختيار سيارة أولاً.")
            return

        values = self.car_table.item(selected[0], "values")
        car_id = values[0]
        original_values = values[1:]  # بدون id

        edit_win = self.build_centered_popup("📝 تعديل السيارة", 600, 350)

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
                    self.show_message("warning", f"يرجى ملء الحقل: {labels[idx]}")
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
                        self.show_message("error", "تعذر العثور على السجل الأصلي.")
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
                self.show_message("success", "✅ تم تعديل بيانات السيارة بنجاح.")
                self.check_warnings()
                self._check_alerts()

            except Exception as e:
                self.show_message("error", f"فشل التعديل:\n{e}")

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
                self.show_message("success", "✅ تم حذف السيارة بنجاح.")
            except Exception as e:
                self.show_message("error", f"فشل الحذف:\n{e}")

        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=len(labels), column=0, columnspan=2, pady=15)

        # زر حفظ التعديلات
        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_car_edit_changes)\
            .pack(side="left", padx=5, ipadx=10)

        # زر الإغلاق الأحمر
        ttk.Button(btn_frame, text="❌ إغلاق", style="danger.TButton", command=edit_win.destroy)\
            .pack(side="left", padx=5, ipadx=10)

        main_frame.columnconfigure(1, weight=1)

    def _build_doctor_tab(self):
        import json

        frame = tb.Frame(self.content_frame, padding=20)
        self.doctor_entries = {}

        # === الإطار الموحد لإدخال طبيب جديد ===
        container = ttk.LabelFrame(frame, text="👨‍⚕️ بيانات الطبيب الجديد", padding=15)
        container.pack(fill="x", padx=10, pady=10)

        # تقسيم الحقول إلى 3 أعمدة
        left_col = tb.Frame(container)
        left_col.grid(row=0, column=0, sticky="n")

        weekday_col = tb.Frame(container)
        # weekday_col.grid(row=0, column=1, sticky="n", padx=20)

        right_col = tb.Frame(container)
        weekday_col.grid(row=0, column=1, sticky="n", padx=(70, 30))
        right_col = tb.Frame(container)
        right_col.grid(row=0, column=2, sticky="n", padx=(40, 0))

        # === الحقول الأساسية ===
        row = 0
        def add_entry_block(parent, label, required=False):
            nonlocal row
            label_frame = tb.Frame(parent)
            label_frame.grid(row=row, column=0, sticky="e", pady=5)
            ttk.Label(label_frame, text=label).pack(side="left")
            if required:
                ttk.Label(label_frame, text="*", foreground="red").pack(side="left")
            entry = tb.Entry(parent, width=25)
            entry.grid(row=row, column=1, sticky="w", pady=5)
            row += 1
            return entry

        self.doctor_entries["name"] = add_entry_block(left_col, "👨‍⚕️ اسم الطبيب:", required=True)
        self.doctor_entries["street"] = add_entry_block(left_col, "🏠 الشارع ورقم المنزل:", required=True)
        self.doctor_entries["city"] = add_entry_block(left_col, "🌍 المدينة:", required=True)
        self.doctor_entries["zip_code"] = add_entry_block(left_col, "🏷 Zip Code:", required=True)
        self.doctor_entries["phone"] = add_entry_block(left_col, "📞 رقم الهاتف:")

        # === الوقت حسب أيام الأسبوع في العمود الأوسط ===
        label_frame = tb.Frame(weekday_col)
        label_frame.pack(anchor="w", pady=(0, 5))
        ttk.Label(label_frame, text="🗕 Zeit:").pack(side="left")
        ttk.Label(label_frame, text="*", foreground="red").pack(side="left")

        self.doctor_weekday_vars = {}
        weekday_labels = {
            "mon": "الإثنين", "tue": "الثلاثاء", "wed": "الأربعاء",
            "thu": "الخميس", "fri": "الجمعة"
        }
        time_options = ["bis", "von - bis", "ab", "nach Anruf", "Anschl."]
        half_hour_slots = [f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)]

        for key, label in weekday_labels.items():
            day_var = tk.BooleanVar()
            type_var = tk.StringVar(value="")
            from_var = tk.StringVar()
            to_var = tk.StringVar()

            type_cb, from_cb, to_cb = self.create_dynamic_time_row(
                weekday_col, label, day_var, type_var, from_var, to_var, self.doctor_entries["phone"]
            )

            # تخزين المتغيرات
            self.doctor_weekday_vars[key] = (day_var, type_var, from_var, to_var, from_cb, to_cb)

            def update_state(*args, d=day_var, t=type_var, fc=from_cb, tc=to_cb, cb=type_cb, fv=from_var, tv=to_var):
                is_active = d.get()
                cb.config(state="readonly" if is_active else "disabled")
                fc.config(state="normal" if is_active and t.get() in ["von - bis", "bis", "ab"] else "disabled")
                tc.config(state="normal" if is_active and t.get() == "von - bis" else "disabled")
                if not is_active:
                    t.set("")
                    fv.set("")
                    tv.set("")

            # ربط تغيير حالة اليوم
            day_var.trace_add("write", update_state)

            # ربط تغيير نوع الوقت بشرط أن يكون اليوم مفعلاً
            def on_type_change(*_, d=day_var, t=type_var, fc=from_cb, tc=to_cb):
                if d.get():
                    self.update_time_fields(t, fc, tc, self.doctor_entries["phone"])
            type_var.trace_add("write", on_type_change)

            # تهيئة الحالة الابتدائية
            update_state()

        # === المواد والمخابر والسعر في العمود الأيمن ===
        right_row = 0

        material_field_frame = tb.Frame(right_col)
        material_field_frame.grid(row=right_row, column=0, sticky="w", pady=5)
        material_field_frame.grid_columnconfigure(0, minsize=130)
        label_frame = tb.Frame(material_field_frame)
        label_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(label_frame, text="📦 Beschreibung:").pack(side="left")
        ttk.Label(label_frame, text="*", foreground="red").pack(side="left")
        material_frame = tb.Frame(material_field_frame)
        material_frame.grid(row=1, column=0, sticky="w")
        material_options = ["BOX", "BAK-Dose", "Schachtel", "Befunde", "Rote Box", "Ständer", "Kiste"]
        self.material_vars = {}
        for i, mat in enumerate(material_options):
            var = tk.BooleanVar()
            ttk.Checkbutton(material_frame, text=mat, variable=var).grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="w")
            self.material_vars[mat] = var
        right_row += 1

        lab_field_frame = tb.Frame(right_col)
        lab_field_frame.grid(row=right_row, column=0, sticky="w", pady=5)
        lab_field_frame.grid_columnconfigure(0, minsize=130)
        label_frame = tb.Frame(lab_field_frame)
        label_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(label_frame, text="🧪 Labore:").pack(side="left")
        ttk.Label(label_frame, text="*", foreground="red").pack(side="left")
        lab_frame = tb.Frame(lab_field_frame)
        lab_frame.grid(row=1, column=0, sticky="w")
        self.lab_vars_container = lab_frame
        self.lab_vars = {}
        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM labs ORDER BY name ASC")
                labs = [r[0] for r in c.fetchall()]
        except:
            labs = []
        for i, lab in enumerate(labs):
            var = tk.BooleanVar()
            ttk.Checkbutton(lab_frame, text=lab, variable=var).grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="w")
            self.lab_vars[lab] = var
        right_row += 1

        price_field_frame = tb.Frame(right_col)
        price_field_frame.grid(row=right_row, column=0, sticky="w", pady=5)
        ttk.Label(price_field_frame, text="💶 Honorare (€):").pack(anchor="w")
        price_entry = tb.Entry(price_field_frame, width=25)
        price_entry.pack(anchor="w")
        self.doctor_entries["price_per_trip"] = price_entry

        ttk.Button(
            container, text="📂 حفظ", style="Green.TButton",
            command=self._save_doctor
        ).grid(row=1, column=0, columnspan=3, pady=10)

        # === جدول قائمة الأطباء ===
        table_container = ttk.LabelFrame(frame, text="📄 قائمة الأطباء")
        table_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # الجدول نفسه
        table_frame = tb.Frame(table_container)
        table_frame.pack(fill="both", expand=True)

        columns = ("id", "name", "street", "city", "phone", "materials", "labs", "price_per_trip", "weekdays", "weekday_times")
        labels = ("", "👨‍⚕️ اسم الطبيب", "🏠 الشارع", "🌍 المدينة", "📞 الهاتف", "Beschreibung 📦", "🧪 Labor:", "💶 Honorare (€)", "🗓 الأيام", "⏰ Zeit")

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, labels)
        self.doctor_tree = tree

        # الشريط السفلي
        bottom_controls = tb.Frame(table_container)
        bottom_controls.pack(fill="x", pady=(10, 10))

        # البحث في اليسار
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.doctor_tree)

        # الحاوية الوسطى للأزرار
        buttons_frame = tb.Frame(bottom_controls)
        buttons_frame.pack(side="left", expand=True)

        # الأزرار نفسها
        inner_buttons = tb.Frame(buttons_frame)
        inner_buttons.pack(anchor="center", padx=(0, 300))

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self.export_table_to_pdf(self.doctor_tree, "📄 قائمة الأطباء")).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📝 تعديل الطبيب", style="Primary.TButton",
                   command=self._edit_doctor).pack(side="left", padx=10)

        ttk.Button(inner_buttons, text="📊 Honorare", style="info.TButton",
                   command=self._show_doctor_honorare).pack(side="left", padx=10)

        self.doctor_list_container = table_container
        self._reload_doctor_list()
        return frame

    def create_dynamic_time_row(self, parent, label, day_var, type_var, from_var, to_var, phone_entry=None):
        frame = tb.Frame(parent)
        frame.pack(anchor="w", pady=2)

        # تخصيص الأعمدة
        frame.grid_columnconfigure(0, minsize=85)   # اسم اليوم
        frame.grid_columnconfigure(1, minsize=140)  # نوع الوقت
        frame.grid_columnconfigure(2, minsize=80)   # من الساعة
        frame.grid_columnconfigure(3, minsize=80)   # إلى الساعة

        ttk.Checkbutton(frame, text=label, variable=day_var).grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        type_var.set("")

        type_cb = ttk.Combobox(frame, values=[
            "bis", "von - bis", "ab", "nach Anruf", "Anschl."
        ], textvariable=type_var, state="readonly", width=15)
        type_cb.grid(row=0, column=1, sticky="w", padx=(0, 5))

        from_cb = ttk.Combobox(frame, values=[
            f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)
        ], textvariable=from_var, state="readonly", width=7)
        from_cb.grid(row=0, column=2, sticky="w", padx=(0, 5))

        to_cb = ttk.Combobox(frame, values=[
            f"{h:02d}:{m:02d}" for h in range(6, 21) for m in (0, 30)
        ], textvariable=to_var, state="readonly", width=7)
        to_cb.grid(row=0, column=3, sticky="w")

        def update_time_fields(*_):
            t = type_var.get().strip()
            if not t:
                from_cb.configure(state="disabled")
                to_cb.configure(state="disabled")
                return
            if t == "von - bis":
                from_cb.configure(state="readonly")
                to_cb.configure(state="readonly")
            elif t in ["bis", "ab"]:
                from_cb.configure(state="readonly")
                to_cb.configure(state="disabled")
            else:
                from_cb.configure(state="disabled")
                to_cb.configure(state="disabled")

            if t == "nach Anruf" and phone_entry and not phone_entry.get().strip():
                phone_entry.focus_set()

        def toggle_time_fields(*_):
            enabled = day_var.get()
            state = "readonly" if enabled else "disabled"
            type_cb.configure(state=state)
            self.update_time_fields(type_var, from_cb, to_cb, phone_entry if enabled else None)

        day_var.trace_add("write", toggle_time_fields)
        toggle_time_fields()

        type_var.trace_add("write", lambda *_: self.update_time_fields(type_var, from_cb, to_cb, phone_entry))
        # self.update_time_fields(type_var, from_cb, to_cb, phone_entry)
        
        return type_cb, from_cb, to_cb

    def update_time_fields(self, type_var, from_cb, to_cb, phone_entry=None):
        t = type_var.get()
        if t == "von - bis":
            from_cb.configure(state="readonly")
            to_cb.configure(state="readonly")
        elif t in ["bis", "ab"]:
            from_cb.configure(state="readonly")
            to_cb.configure(state="disabled")
        else:
            from_cb.configure(state="disabled")
            to_cb.configure(state="disabled")

        if t == "nach Anruf" and phone_entry and not phone_entry.get().strip():
            phone_entry.focus_set()

    def _edit_doctor(self):
        selected = self.doctor_tree.selection()
        if not selected:
            self.show_message("warning", "يرجى تحديد طبيب أولاً من الجدول.")
            return

        item = self.doctor_tree.item(selected[0])
        doctor_id = item["values"][0]  # أول عمود هو ID
        self._edit_doctor_popup(doctor_id)

    def _filter_doctor_table(self, query):
        query = query.strip().lower()
        for row in self.doctor_tree.get_children():
            self.doctor_tree.delete(row)

        if not hasattr(self.doctor_tree, "_original_items"):
            return

        matched_rows = []
        for values in self.doctor_tree._original_items:
            values_text = [str(v).lower() for v in values[1:]]  # تجاهل ID أثناء البحث
            if any(query in v for v in values_text):
                matched_rows.append(values)

        if not matched_rows:
            self.doctor_tree.insert("", "end", values=("", "🔍 لا توجد نتائج مطابقة", "", "", "", "", "", "", ""))
            return

        for i, row in enumerate(matched_rows):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.doctor_tree.insert("", "end", values=row, tags=(tag,))

        if hasattr(self, "apply_alternate_row_colors"):
            self.apply_alternate_row_colors(self.doctor_tree)

    def _save_doctor(self):
        import json

        name = self.doctor_entries["name"].get().strip()
        phone = self.doctor_entries["phone"].get().strip()
        street = self.doctor_entries["street"].get().strip()
        city = self.doctor_entries["city"].get().strip()
        zip_code = self.doctor_entries["zip_code"].get().strip()
        price_text = self.doctor_entries["price_per_trip"].get().strip()

        # ✅ التحقق من الحقول الإلزامية
        missing_fields = []
        if not name:
            missing_fields.append("اسم الطبيب")
        if not street or not city or not zip_code:
            missing_fields.append("العنوان الكامل")
        if not any(var[0].get() for var in self.doctor_weekday_vars.values()):
            missing_fields.append("Zeit")
        if not any(var.get() for var in self.material_vars.values()):
            missing_fields.append("المواد")
        if not any(var.get() for var in self.lab_vars.values()):
            missing_fields.append("المخابر")

        if missing_fields:
            msg = "⚠️ الحقول التالية مطلوبة:\n" + "\n".join(f"• {field}" for field in missing_fields)
            self.show_message("warning", msg)
            return

        # ✅ معالجة السعر
        try:
            price_per_trip = float(price_text) if price_text else None
        except ValueError:
            self.show_message("warning", "⚠️ السعر غير صالح.")
            return

        # ✅ المواد والمخابر بصيغة JSON
        selected_materials = [mat for mat, var in self.material_vars.items() if var.get()]
        materials_json = json.dumps(selected_materials, ensure_ascii=False)

        selected_labs = [lab for lab, var in self.lab_vars.items() if var.get()]
        labs_json = json.dumps(selected_labs, ensure_ascii=False)

        # ✅ تجهيز الأيام والأوقات
        selected_days = []
        selected_times = []

        for key, (day_var, type_var, from_var, to_var, from_cb, to_cb) in self.doctor_weekday_vars.items():
            if not day_var.get():
                continue

            label = {
                "mon": "الإثنين", "tue": "الثلاثاء", "wed": "الأربعاء",
                "thu": "الخميس", "fri": "الجمعة"
            }.get(key, key)

            selected_days.append(label)

            typ = type_var.get().strip()
            f = from_var.get().strip()
            t = to_var.get().strip()

            if not typ:
                self.show_message("warning", f"❗ يجب اختيار نوع الوقت ليوم {label}.")
                return

            # تحقق دقيق حسب النوع المحدد
            if typ == "von - bis":
                if not f or not t:
                    self.show_message("warning", f"❗ يرجى تحديد الوقت من وإلى ليوم {label}.")
                    return
                if f >= t:
                    self.show_message("warning", f"❗ الوقت 'إلى' يجب أن يكون بعد 'من' في يوم {label}.")
                    return
                selected_times.append(f"{typ} {f} - {t}")
            elif typ in ["bis", "ab"]:
                if not f:
                    self.show_message("warning", f"❗ يرجى تحديد الساعة ليوم {label}.")
                    return
                selected_times.append(f"{typ} {f}")
            elif typ == "nach Anruf":
                if not phone:
                    self.show_message("warning", f"❗ يرجى إدخال رقم الهاتف ليوم {label}.")
                    return
                selected_times.append(f"{typ} ({phone})")
            else:
                selected_times.append(typ)

        if len(selected_days) != len(selected_times):
            self.show_message("error", "❗ تعارض بين الأيام والأوقات. تأكد من إكمال جميع الحقول.")
            return

        # ✅ إنشاء قائمة أوقات الأيام المنفصلة (mon_time .. fri_time)
        weekday_updates = []
        for key in ["mon", "tue", "wed", "thu", "fri"]:
            _, type_var, from_var, to_var, _, _ = self.doctor_weekday_vars[key]
            typ = type_var.get().strip()
            f = from_var.get().strip()
            t = to_var.get().strip()

            if not typ:
                weekday_updates.append(None)
            elif typ == "von - bis" and f and t:
                weekday_updates.append(f"{typ} {f} - {t}")
            elif typ in ["bis", "ab"] and f:
                weekday_updates.append(f"{typ} {f}")
            elif typ == "nach Anruf":
                weekday_updates.append(f"{typ} ({phone})")
            else:
                weekday_updates.append(typ)

        # ✅ الإدخال في قاعدة البيانات
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO doctors 
                (name, phone, street, city, zip_code, materials, labs, price_per_trip,
                 mon_time, tue_time, wed_time, thu_time, fri_time,
                 weekdays, weekday_times)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, phone, street, city, zip_code,
                materials_json, labs_json, price_per_trip,
                *weekday_updates,  # قائمة فيها 5 عناصر: mon_time .. fri_time
                "\n".join(selected_days),
                "\n".join(selected_times)
            ))
            conn.commit()

        # ✅ تفريغ الحقول بعد الحفظ
        for entry in self.doctor_entries.values():
            if isinstance(entry, tb.Entry):
                entry.delete(0, tk.END)

        for var in self.material_vars.values():
            var.set(False)

        for var in self.lab_vars.values():
            var.set(False)

        for key, (day_var, type_var, from_var, to_var, from_cb, to_cb) in self.doctor_weekday_vars.items():
            day_var.set(False)
            type_var.set("")
            from_var.set("")
            to_var.set("")
            self.update_time_fields(type_var, from_cb, to_cb, self.doctor_entries["phone"])

        self._reload_doctor_list()

        today = datetime.today().date().isoformat()

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT price_per_trip FROM doctors WHERE name = ?", (name,))
            old_result = c.fetchone()
            old_price = old_result[0] if old_result else None

            if str(old_price) != price_text:
                # أدخل السعر الجديد فقط إذا لم يكن مسجلاً لنفس اليوم
                c.execute("""
                    SELECT 1 FROM doctor_price_history
                    WHERE doctor_name = ? AND effective_date = ?
                """, (name, today))

                if not c.fetchone():
                    c.execute("""
                        INSERT INTO doctor_price_history (doctor_name, effective_date, price)
                        VALUES (?, ?, ?)
                    """, (name, today, float(price_text)))
                    conn.commit()

        self.show_message("success", f"✅ تم حفظ الطبيب: {name}")
        self._refresh_main_comboboxes()

    def _reload_doctor_tab(self):
        # ابحث عن كل التبويبات وامسح أي تبويب اسمه "الأطباء"
        found = False
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == "الأطباء":
                self.notebook.forget(tab_id)
                found = True

        # دمر الـFrame القديم لو موجود
        old_frame = self.tab_frames.get("الأطباء")
        if old_frame is not None:
            try:
                old_frame.destroy()
            except Exception as e:
                print("خطأ أثناء التدمير:", e)

        # ابني التبويب الجديد
        new_frame = self._build_doctor_tab()
        self.tab_frames["الأطباء"] = new_frame
        self.notebook.insert(1, new_frame, text="الأطباء")

    def _reload_doctor_list(self):
        # 🧹 تنظيف محتوى الجدول (Treeview)
        for row in self.doctor_tree.get_children():
            self.doctor_tree.delete(row)

        # 📥 جلب الأطباء من قاعدة البيانات
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, name, street, city, phone, materials, labs, price_per_trip,
                       weekdays, weekday_times
                FROM doctors ORDER BY name ASC
            """)
            doctors = c.fetchall()

            # 🧠 تحميل أسماء المخابر الحديثة
            c.execute("SELECT name FROM labs ORDER BY name ASC")
            lab_names_set = set(name for (name,) in c.fetchall())

        if not doctors:
            self.doctor_tree.insert("", "end", values=("", "🚫 لا يوجد أطباء", "", "", "", "", "", "", "", ""))
            return

        import json
        for i, (doctor_id, name, street, city, phone, materials, labs, price, weekdays, weekday_times) in enumerate(doctors):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'

            # ✅ المخابر (عرض مرتب)
            try:
                labs_list = json.loads(labs)
                labs_display = ", ".join([lab for lab in labs_list if lab in lab_names_set])
            except:
                labs_display = ""

            self.doctor_tree.insert(
                "", "end",
                values=(doctor_id, name, street, city, phone, materials, labs_display, price, weekdays, weekday_times),
                tags=(tag,)
            )

        # ✅ ألوان الصفوف بالتناوب
        if hasattr(self, "apply_alternate_row_colors"):
            self.apply_alternate_row_colors(self.doctor_tree)

        # ✅ دعم البحث
        self.doctor_tree._original_items = [
            (doctor_id, name, street, city, phone, materials, labs_display, price, weekdays, weekday_times)
            for (doctor_id, name, street, city, phone, materials, labs, price, weekdays, weekday_times) in doctors
        ]

        # ✅ تفعيل Tooltip لعرض النص الكامل عند المرور على الخلايا الطويلة
        self._attach_tooltip_to_tree(self.doctor_tree)

    def _edit_doctor_popup(self, doctor_id):
        import json
        import sqlite3
        import tkinter as tk

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("""
                SELECT name, phone, street, city, zip_code,
                    materials, labs, price_per_trip,
                    mon_time, tue_time, wed_time, thu_time, fri_time,
                    weekdays, weekday_times
                FROM doctors WHERE id = ?
            """, (doctor_id,))
            row = c.fetchone()

        if not row:
            self.show_message("error", "لم يتم العثور على بيانات الطبيب.")
            return

        (name, phone, street, city, zip_code,
         materials_json, labs_json, price_per_trip,
         mon_time, tue_time, wed_time, thu_time, fri_time,
         weekdays_text, weekday_times_text) = row

        weekday_data = {
            "mon": mon_time, "tue": tue_time, "wed": wed_time,
            "thu": thu_time, "fri": fri_time
        }

        win = self.build_centered_popup("✏️ تعديل بيانات الطبيب", 980, 500)
        frame = tb.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)

        container = ttk.LabelFrame(frame, text="📋 تعديل بيانات الطبيب", padding=15)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        entries = {}

        left_col = tb.Frame(container)
        left_col.grid(row=0, column=0, sticky="n")
        center_col = tb.Frame(container)
        center_col.grid(row=0, column=1, sticky="n", padx=(30, 30))
        right_col = tb.Frame(container)
        right_col.grid(row=0, column=2, sticky="n")

        def add_entry_block(parent, label, value):
            block = tb.Frame(parent)
            block.pack(anchor="w", pady=4)
            ttk.Label(block, text=label).pack(side="left")
            entry = tb.Entry(parent, width=30)
            entry.insert(0, value or "")
            entry.pack(anchor="w")
            return entry

        entries["name"] = add_entry_block(left_col, "👨‍⚕️ اسم الطبيب:", name)
        entries["street"] = add_entry_block(left_col, "🏠 الشارع ورقم المنزل:", street)
        entries["city"] = add_entry_block(left_col, "🏙 المدينة:", city)
        entries["zip_code"] = add_entry_block(left_col, "🏷 Zip Code:", zip_code)
        entries["phone"] = add_entry_block(left_col, "📞 رقم الهاتف:", phone)

        tb.Label(center_col, text="📅 Zeit:").pack(anchor="w", pady=(0, 5))
        self.edit_doctor_weekday_vars = {}
        time_options = ["bis", "von - bis", "ab", "nach Anruf", "Anschl."]
        half_hour_slots = [
            "06:00", "06:30", "07:00", "07:30", "08:00", "08:30",
            "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
            "15:00", "15:30", "16:00", "16:30", "17:00", "17:30",
            "18:00", "18:30", "19:00", "19:30", "20:00"
        ]

        if weekdays_text and weekday_times_text:
            days = weekdays_text.strip().splitlines()
            times = weekday_times_text.strip().splitlines()
            label_to_key = {
                "الإثنين": "mon", "الثلاثاء": "tue", "الأربعاء": "wed",
                "الخميس": "thu", "الجمعة": "fri"
            }
            for day, time in zip(days, times):
                key = label_to_key.get(day.strip())
                if key:
                    weekday_data[key] = time

            for key, label in [("mon", "الإثنين"), ("tue", "الثلاثاء"), ("wed", "الأربعاء"), ("thu", "الخميس"), ("fri", "الجمعة")]:
                raw_value = weekday_data[key] or ""
                has_time = bool(raw_value.strip())
                day_var = tk.BooleanVar(value=has_time)

                # استخراج نوع الوقت وباقي الحقول
                initial_type, from_time, to_time = "", "", ""
                opt = best_match_option(raw_value)
                initial_type = opt if opt else ""
                if opt and super_normalize(raw_value).startswith(super_normalize(opt)):
                    initial_type = opt
                    rest = raw_value[len(opt):].strip()
                    if opt == "von - bis" and " - " in rest:
                        from_time, to_time = map(str.strip, rest.split(" - ", 1))
                    elif opt in ["bis", "ab"]:
                        from_time = rest

                # إنشاء المتغيرات
                type_var = tk.StringVar()
                from_var = tk.StringVar()
                to_var = tk.StringVar()
                from_var.set(from_time.strip())
                to_var.set(to_time.strip())

                # إنشاء الكمبوبوكسات مرة واحدة فقط!
                type_cb, from_cb, to_cb = self.create_dynamic_time_row(
                    center_col, label, day_var, type_var, from_var, to_var, entries["phone"]
                )

                # تعيين القيمة المرجعية الصحيحة (مباشرة بعد البناء)
                target = None
                for v in type_cb['values']:
                    if super_normalize(v) == super_normalize(initial_type):
                        target = v
                        break
                if target:
                    type_var.set(target)
                else:
                    type_var.set(super_normalize(initial_type))

                # تخزين المتغيرات
                self.edit_doctor_weekday_vars[key] = (day_var, type_var, from_var, to_var, from_cb, to_cb)

                def update_state(*args, d=day_var, t=type_var, fc=from_cb, tc=to_cb, cb=type_cb, fv=from_var, tv=to_var):
                    is_active = d.get()
                    cb.config(state="readonly" if is_active else "disabled")
                    fc.config(state="normal" if is_active and t.get() in ["von - bis", "bis", "ab"] else "disabled")
                    tc.config(state="normal" if is_active and t.get() == "von - bis" else "disabled")
                    if not is_active:
                        t.set("")
                        fv.set("")
                        tv.set("")

                day_var.trace_add("write", update_state)

                # ربط تغيير نوع الوقت، لكن فقط إن كان اليوم مفعلاً
                def on_type_change(*_):
                    if day_var.get():
                        self.update_time_fields(type_var, from_cb, to_cb, entries["phone"])
                type_var.trace_add("write", on_type_change)

                # تفعيل الحقول بناءً على حالة البداية
                update_state()
                
        tb.Label(right_col, text="📦 Beschreibung:").pack(anchor="w")
        material_frame = tb.Frame(right_col)
        material_frame.pack(anchor="w")
        material_options = ["BOX", "BAK-Dose", "Schachtel", "Befunde", "Rote Box", "Ständer", "Kiste"]
        selected_materials = json.loads(materials_json or "[]")
        material_vars = {}
        for i, mat in enumerate(material_options):
            var = tk.BooleanVar(value=mat in selected_materials)
            ttk.Checkbutton(material_frame, text=mat, variable=var).grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="w")
            material_vars[mat] = var

        tb.Label(right_col, text="🧪 Labore:").pack(anchor="w", pady=(8, 0))
        lab_frame = tb.Frame(right_col)
        lab_frame.pack(anchor="w")
        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM labs")
                all_labs = [r[0] for r in c.fetchall()]
        except:
            all_labs = []
        selected_labs = json.loads(labs_json or "[]")
        lab_vars = {}
        for i, lab in enumerate(all_labs):
            var = tk.BooleanVar(value=lab in selected_labs)
            ttk.Checkbutton(lab_frame, text=lab, variable=var).grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="w")
            lab_vars[lab] = var

        entries["price_per_trip"] = add_entry_block(right_col, "💶 Honorare (€):", price_per_trip or "")

        def save_changes():
            new_values = {
                "name": entries["name"].get().strip(),
                "phone": entries["phone"].get().strip(),
                "street": entries["street"].get().strip(),
                "city": entries["city"].get().strip(),
                "zip_code": entries["zip_code"].get().strip(),
                "materials": json.dumps([m for m, v in material_vars.items() if v.get()], ensure_ascii=False),
                "labs": json.dumps([l for l, v in lab_vars.items() if v.get()], ensure_ascii=False),
                "price_per_trip": float(entries["price_per_trip"].get().strip() or 0)
            }

            weekday_updates = []
            weekday_labels = {
                "mon": "الإثنين", "tue": "الثلاثاء", "wed": "الأربعاء", "thu": "الخميس", "fri": "الجمعة"
            }

            # تحقق من صلاحية التحديدات ثم جهّز النصوص
            for key in ["mon", "tue", "wed", "thu", "fri"]:
                active, typ, from_val, to_val, from_cb, to_cb = self.edit_doctor_weekday_vars[key]
                
                if active.get():
                    if not typ.get().strip():
                        self.show_message("warning", f"❗ يجب اختيار نوع الوقت ليوم {weekday_labels[key]}.")
                        return

                    if typ.get() == "von - bis":
                        if from_val.get() and to_val.get():
                            weekday_updates.append(f"{typ.get()} {from_val.get()} - {to_val.get()}")
                        else:
                            weekday_updates.append(typ.get())  # قد ترغب بمنع هذا أيضًا
                    elif typ.get() in ["bis", "ab"]:
                        if from_val.get():
                            weekday_updates.append(f"{typ.get()} {from_val.get()}")
                        else:
                            weekday_updates.append(typ.get())  # قد ترغب أيضًا بتحذير هنا
                    elif typ.get() == "nach Anruf":
                        weekday_updates.append(f"{typ.get()} ({entries['phone'].get().strip()})")
                    else:
                        weekday_updates.append(typ.get())
                else:
                    weekday_updates.append("")  # يوم غير مفعل

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                # تجهيز الأعمدة الجديدة
                weekday_labels = {
                    "mon": "الإثنين", "tue": "الثلاثاء", "wed": "الأربعاء", "thu": "الخميس", "fri": "الجمعة"
                }
                selected_days = []
                selected_times = []
                for key, (active, typ, from_val, to_val, _, _) in self.edit_doctor_weekday_vars.items():
                    if active.get():
                        label = weekday_labels.get(key, key)
                        selected_days.append(label)
                        if typ.get() == "von - bis":
                            selected_times.append(f"{typ.get()} {from_val.get()} - {to_val.get()}")
                        elif typ.get() in ["bis", "ab"]:
                            selected_times.append(f"{typ.get()} {from_val.get()}")
                        elif typ.get() == "nach Anruf":
                            selected_times.append(f"{typ.get()} ({entries['phone'].get().strip()})")
                        else:
                            selected_times.append(typ.get())

                # تحديث شامل
                c.execute("""
                    UPDATE doctors SET
                        name=?, phone=?, street=?, city=?, zip_code=?,
                        materials=?, labs=?, price_per_trip=?,
                        mon_time=?, tue_time=?, wed_time=?, thu_time=?, fri_time=?,
                        weekdays=?, weekday_times=?
                    WHERE id=?
                """, (
                    new_values["name"], new_values["phone"], new_values["street"],
                    new_values["city"], new_values["zip_code"],
                    new_values["materials"], new_values["labs"],
                    new_values["price_per_trip"],
                    *weekday_updates,
                    "\n".join(selected_days),
                    "\n".join(selected_times),
                    doctor_id
                ))
                conn.commit()

            win.destroy()
            self._reload_doctor_list()
            self._refresh_main_comboboxes()
            self.show_message("success", f"✅ تم تعديل بيانات الطبيب: {new_values['name']}")

        def delete_doctor():
            if not self.show_custom_confirm("تأكيد الحذف", f"⚠️ هل تريد حذف الطبيب '{name}'؟"):
                return

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
                conn.commit()

            self._reload_doctor_list()
            win.destroy()
            self._refresh_main_comboboxes()
            self.show_message("success", f"🗑 تم حذف الطبيب: {name}")

        btns = tb.Frame(frame)
        btns.pack(fill="x", pady=20)
        center_buttons = tb.Frame(btns)
        center_buttons.pack(anchor="center")
        ttk.Button(center_buttons, text="💾 حفظ", style="Green.TButton", command=save_changes).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="🗑 حذف", style="warning.TButton", command=delete_doctor).pack(side="left", padx=10)
        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton", command=win.destroy).pack(side="left", padx=10)

    def _build_lab_tab(self):
        frame = tb.Frame(self.content_frame, padding=20)

        # ===== إطار بيانات الإدخال =====
        form_frame = ttk.LabelFrame(frame, text="📋 إضافة مخبر جديد", padding=15)
        form_frame.pack(fill="x", padx=10, pady=(0, 15))

        labels = ["اسم المخبر:", "عنوان المخبر:"]
        self.lab_entries = []

        for i, text in enumerate(labels):
            ttk.Label(form_frame, text=text).grid(row=i, column=0, sticky="e", pady=6, padx=(5, 5))
            entry = tb.Entry(form_frame, width=60)
            entry.grid(row=i, column=1, pady=6, padx=(0, 10), sticky="w")
            self.lab_entries.append(entry)

        # زر الحفظ
        ttk.Button(
            form_frame,
            text="💾 حفظ",
            style="Green.TButton",
            command=self._save_lab
        ).grid(row=2, column=0, columnspan=2, pady=10)

        # ===== قائمة المخابر =====
        self.lab_list_container = ttk.LabelFrame(frame, text="🧪 المخابر المسجلة", padding=15)
        self.lab_list_container.pack(fill="both", expand=True, padx=10, pady=10)

        self._reload_lab_list()

        return frame

    def _reload_lab_list(self):
        for widget in self.lab_list_container.winfo_children():
            widget.destroy()

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, address FROM labs ORDER BY name ASC")
            labs = c.fetchall()

        if not labs:
            ttk.Label(self.lab_list_container, text="🚫 لا توجد مخابر مسجلة حالياً.").pack()
            return

        for lab_id, name, address in labs:
            card = tb.Frame(self.lab_list_container, padding=10, style="custom.light.TFrame")
            card.pack(fill="x", pady=5, padx=5)

            label_text = f"🔬 {name}\n📍 {address}"
            ttk.Label(card, text=label_text, justify="right", anchor="w", font=("Segoe UI", 10)).pack(side="left", expand=True, fill="x")

            ttk.Button(card, text="✏️ تعديل", style="Primary.TButton",
                       command=lambda lid=lab_id: self._edit_lab_popup(lid)).pack(side="right", padx=5)

    def _edit_lab_popup(self, lab_id):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT name, address FROM labs WHERE id = ?", (lab_id,))
            row = c.fetchone()

        if not row:
            self.show_message("error", "تعذر العثور على بيانات المخبر.")
            return

        old_name, old_address = row
    
        win = self.build_centered_popup("✏️ تعديل بيانات المخبر", 400, 220)

        frame = tb.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="اسم المخبر:").grid(row=0, column=0, sticky="e", padx=5, pady=10)
        name_entry = tb.Entry(frame, width=40)
        name_entry.insert(0, old_name)
        name_entry.grid(row=0, column=1, pady=10)

        ttk.Label(frame, text="العنوان:").grid(row=1, column=0, sticky="e", padx=5, pady=10)
        address_entry = tb.Entry(frame, width=40)
        address_entry.insert(0, old_address)
        address_entry.grid(row=1, column=1, pady=10)

        def save_changes():
            import json

            new_name = name_entry.get().strip()
            new_address = address_entry.get().strip()

            if not new_name:
                self.show_message("warning", "يرجى إدخال اسم المخبر.")
                return

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()

                if new_name != old_name:
                    # تحقق من عدم تكرار الاسم الجديد
                    c.execute("SELECT COUNT(*) FROM labs WHERE name = ?", (new_name,))
                    if c.fetchone()[0] > 0:
                        self.show_message("warning", f"⚠️ يوجد مخبر بهذا الاسم مسبقًا: {new_name}")
                        return

                    # ✅ استبدال الاسم القديم بالجديد في جميع الأطباء
                    c.execute("SELECT id, labs FROM doctors")
                    for doc_id, labs_json in c.fetchall():
                        try:
                            labs_list = json.loads(labs_json or "[]")
                            if old_name in labs_list:
                                updated_labs = [new_name if lab == old_name else lab for lab in labs_list]
                                c.execute("UPDATE doctors SET labs = ? WHERE id = ?",
                                          (json.dumps(updated_labs, ensure_ascii=False), doc_id))
                        except Exception as e:
                            print("⚠️ خطأ أثناء استبدال اسم المخبر:", e)

                # ✅ تحديث المخبر نفسه
                c.execute("UPDATE labs SET name = ?, address = ? WHERE id = ?", (new_name, new_address, lab_id))
                conn.commit()

            win.destroy()
            self._reload_lab_list()
            if hasattr(self, 'tab_frames') and "الأطباء" in self.tab_frames:
                self._reload_doctor_tab()
            elif hasattr(self, '_update_lab_checkbuttons'):
                self._update_lab_checkbuttons()
            self.show_message("success", "✅ تم تعديل بيانات المخبر بنجاح.")

        def delete_lab():
            import json

            if not self.show_custom_confirm("تأكيد الحذف", f"⚠️ هل تريد حذف المخبر '{old_name}'؟"):
                return

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT id, name, labs FROM doctors")
                linked_doctors = []
                for doc_id, doc_name, labs_json in c.fetchall():
                    try:
                        labs_list = json.loads(labs_json or "[]")
                        if old_name in labs_list:
                            linked_doctors.append((doc_id, doc_name, labs_json))
                    except:
                        continue

            if linked_doctors:
                # ✅ عرض الخيارات الثلاثة
                response = self.ask_choice_dialog(
                    "❗ مخبر مرتبط",
                    f"🔬 المخبر '{old_name}' مرتبط بـ {len(linked_doctors)} طبيب/أطباء.\nكيف تريد المتابعة؟",
                    ["❌ إلغاء", "🗑 حذف من الأطباء", "🔁 استبداله بمخبر آخر"]
                )

                if response == "❌ إلغاء":
                    return

                elif response == "🗑 حذف من الأطباء":
                    with sqlite3.connect("medicaltrans.db") as conn:
                        c = conn.cursor()
                        for doc_id, _, labs_json in linked_doctors:
                            try:
                                labs_list = json.loads(labs_json)
                                labs_list = [lab for lab in labs_list if lab != old_name]
                                c.execute("UPDATE doctors SET labs = ? WHERE id = ?",
                                          (json.dumps(labs_list, ensure_ascii=False), doc_id))
                            except:
                                continue
                        conn.commit()

                elif response == "🔁 استبداله بمخبر آخر":
                        # جلب كل المخابر ما عدا المخبر المحذوف
                    with sqlite3.connect("medicaltrans.db") as conn:
                        c = conn.cursor()
                        c.execute("SELECT name FROM labs WHERE name != ?", (old_name,))
                        available_labs = [r[0] for r in c.fetchall()]

                    if not available_labs:
                        self.show_message("warning", "⚠️ لا يوجد مخبر بديل متاح للاستبدال.")
                        return

                    replacement = self.ask_choice_dialog(
                        "اختر المخبر البديل",
                        "يرجى اختيار مخبر بديل ليحل محل المخبر المحذوف:",
                        available_labs
                    )

                    if not replacement:
                        return

                    with sqlite3.connect("medicaltrans.db") as conn:
                        c = conn.cursor()
                        for doc_id, _, labs_json in linked_doctors:
                            try:
                                labs_list = json.loads(labs_json)
                                updated = [replacement if lab == old_name else lab for lab in labs_list]
                                c.execute("UPDATE doctors SET labs = ? WHERE id = ?",
                                          (json.dumps(updated, ensure_ascii=False), doc_id))
                            except:
                                continue
                        conn.commit()

            # ✅ حذف المخبر نهائيًا
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("DELETE FROM labs WHERE id = ?", (lab_id,))
                conn.commit()

            win.destroy()
            self._reload_lab_list()
            if hasattr(self, 'tab_frames') and "الأطباء" in self.tab_frames:
                self._reload_doctor_tab()
            elif hasattr(self, '_update_lab_checkbuttons'):
                self._update_lab_checkbuttons()
            self.show_message("success", "✅ تم حذف المخبر.")
            self._refresh_main_comboboxes()

        btns = tb.Frame(frame)
        btns.grid(row=2, column=0, columnspan=2, pady=15)

        # توسيط الأزرار
        center_buttons = tb.Frame(btns)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="💾 حفظ", style="Green.TButton", command=save_changes)\
            .pack(side="left", padx=10)

        ttk.Button(center_buttons, text="🗑 حذف", style="warning.TButton", command=delete_lab)\
            .pack(side="left", padx=10)

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton", command=win.destroy)\
            .pack(side="left", padx=10)

    def _save_lab(self):
        name, address = [e.get().strip() for e in self.lab_entries]
        if not name:
            self.show_message("warning", "يرجى إدخال اسم المخبر.")
            return

        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()

        # تحقق من تكرار الاسم
        c.execute("SELECT COUNT(*) FROM labs WHERE name = ?", (name,))
        if c.fetchone()[0] > 0:
            self.show_message("warning", f"⚠️ يوجد مخبر بهذا الاسم مسبقًا: {name}")
            conn.close()
            return

        c.execute("INSERT INTO labs (name, address) VALUES (?, ?)", (name, address))
        conn.commit()

        # ✅ تحديث تبويب الأطباء مباشرة إن وُجد
        if hasattr(self, 'tab_frames') and "الأطباء" in self.tab_frames:
            self._reload_doctor_tab()
        elif hasattr(self, '_update_lab_checkbuttons'):
            self._update_lab_checkbuttons()

        conn.close()
        for e in self.lab_entries:
            e.delete(0, tb.END)

        self.show_message("success", f"✅ تم حفظ المخبر: {name}")
        self._reload_lab_list()
        self._refresh_main_comboboxes()

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

    def _update_lab_checkbuttons(self):
        try:
            # إزالة المخابر القديمة
            for widget in self.lab_vars.values():
                if hasattr(widget, 'master'):
                    widget.master.destroy()

            self.lab_vars.clear()

            # جلب المخابر من قاعدة البيانات
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM labs ORDER BY name ASC")
                labs = [r[0] for r in c.fetchall()]

            # إعادة إنشاء checkbuttons
            row = 0
            lab_frame = self.lab_vars_container  # يجب أن تحفظ مكان الإطار في المتغير هذا عند البناء الأول
            for i, lab in enumerate(labs):
                var = tk.BooleanVar()
                cb = ttk.Checkbutton(lab_frame, text=lab, variable=var)
                cb.grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="w")
                self.lab_vars[lab] = var
        except Exception as e:
            print(f"حدث خطأ أثناء تحديث المخابر في تبويب الأطباء: {e}")

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
    
        # إضافة تخزين البيانات الأصلية
        tree._original_items = [list(row) for row in rows]
    
        # استبدال التعبئة اليدوية بالدالة المخصصة
        self.fill_treeview_with_rows(tree, rows)

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

        fuel_row = 0

        # --- اسم السائق ---
        ttk.Label(fuel_frame, text="اسم السائق:").grid(row=fuel_row, column=0, sticky="e", padx=(10, 5), pady=6)
        self.fuel_driver_combo = ttk.Combobox(fuel_frame, values=self.get_driver_names(), state="readonly", width=35)
        self.fuel_driver_combo.grid(row=fuel_row, column=1, sticky="w", pady=6)
        fuel_row += 1

        # --- التاريخ ---
        ttk.Label(fuel_frame, text="التاريخ:").grid(row=fuel_row, column=0, sticky="e", padx=(10, 5), pady=6)
        self.fuel_date_picker = CustomDatePicker(fuel_frame)
        self.fuel_date_picker.grid(row=fuel_row, column=1, sticky="w", pady=6)
        fuel_row += 1

        # --- المبلغ ---
        ttk.Label(fuel_frame, text="المبلغ (€):").grid(row=fuel_row, column=0, sticky="e", padx=(10, 5), pady=6)
        self.fuel_amount_entry = tb.Entry(fuel_frame, width=37)
        self.fuel_amount_entry.grid(row=fuel_row, column=1, sticky="w", pady=6)
        fuel_row += 1

        # --- أزرار ---
        fuel_buttons = tb.Frame(fuel_frame)
        fuel_buttons.grid(row=fuel_row, column=0, columnspan=2, pady=15)

        ttk.Button(fuel_buttons, text="💾 حفظ", style="Green.TButton", command=self._save_fuel_expense).pack(side="left", padx=10)
        ttk.Button(fuel_buttons, text="📊 عرض", style="info.TButton", command=self._show_fuel_expense_table).pack(side="left", padx=10)

        # --- بيانات السائق ---
        row = 0

        label_frame = tb.Frame(form_frame)
        label_frame.grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)

        ttk.Label(label_frame, text="اسم السائق:").pack(side="left")
        ttk.Label(label_frame, text="*", foreground="red").pack(side="left", padx=(3, 0))

        self.driver_name_entry = tb.Entry(form_frame, width=70)
        self.driver_name_entry.grid(row=row, column=1, sticky="w", pady=6)
        self.driver_entries.append(self.driver_name_entry)
        row += 1

        label_frame = tb.Frame(form_frame)
        label_frame.grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)

        ttk.Label(label_frame, text="من (بداية العمل):").pack(side="left")
        ttk.Label(label_frame, text="*", foreground="red").pack(side="left", padx=(3, 0))

        date_frame = tb.Frame(form_frame)
        date_frame.grid(row=row, column=1, sticky="w", pady=6)

        self.driver_from_picker = CustomDatePicker(date_frame)
        self.driver_from_picker.pack(side="left", padx=(0, 10))

        spacer = tb.Label(date_frame, text="", width=8) 
        spacer.pack(side="left")

        ttk.Label(date_frame, text="إلى (نهاية العمل):  ").pack(side="left", padx=(5, 5))
        self.driver_to_picker = CustomDatePicker(date_frame)
        self.driver_to_picker.pack(side="left")
        self.driver_entries.extend([self.driver_from_picker.entry, self.driver_to_picker.entry])
        row += 1

        ttk.Label(form_frame, text="عنوان السائق:   ").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)
        address_entry = tb.Entry(form_frame, width=70)
        address_entry.grid(row=row, column=1, sticky="w", pady=6)
        self.driver_entries.append(address_entry)
        row += 1

        ttk.Label(form_frame, text="رقم الهاتف:   ").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)
        phone_entry = tb.Entry(form_frame, width=70)
        phone_entry.grid(row=row, column=1, sticky="w", pady=6)
        self.driver_entries.append(phone_entry)
        row += 1

        label_frame = tb.Frame(form_frame)
        label_frame.grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)

        ttk.Label(label_frame, text="نوع العقد:").pack(side="left")
        ttk.Label(label_frame, text="*", foreground="red").pack(side="left", padx=(3, 0))

        self.contract_type_combo = ttk.Combobox(form_frame, values=["Vollzeit", "Teilzeit", "Geringfügig"], state="readonly", width=68)
        self.contract_type_combo.grid(row=row, column=1, sticky="w", pady=6)
        self.driver_entries.append(self.contract_type_combo)
        row += 1

        ttk.Label(form_frame, text="رقم اللوحة:   ").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)
        car_frame = tb.Frame(form_frame)
        car_frame.grid(row=row, column=1, sticky="w", pady=6)
        self.driver_car_plate_combo = ttk.Combobox(car_frame, values=self._get_available_cars_for_drivers(), state="readonly", width=10)
        self.driver_car_plate_combo.pack(side="left", padx=(0, 10))
        ttk.Label(car_frame, text="من: ").pack(side="left")
        self.driver_car_from_picker = CustomDatePicker(car_frame)
        self.driver_car_from_picker.pack(side="left", padx=(5, 10))
        ttk.Label(car_frame, text="إلى: ").pack(side="left")
        self.driver_car_to_picker = CustomDatePicker(car_frame)
        self.driver_car_to_picker.pack(side="left")
        self.driver_entries.extend([self.driver_car_plate_combo, self.driver_car_from_picker.entry, self.driver_car_to_picker.entry])
        row += 1

        ttk.Label(form_frame, text="ملاحظات:   ").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=6)
        notes_entry = tb.Entry(form_frame, width=70)
        notes_entry.grid(row=row, column=1, sticky="w", pady=6)
        self.driver_entries.append(notes_entry)
        row += 1

        buttons_frame = tb.Frame(form_frame)
        buttons_frame.grid(row=row, column=0, columnspan=2, pady=20)
        ttk.Button(buttons_frame, text="💾 حفظ", style="Green.TButton", command=self._save_driver).pack(ipadx=30)

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
            "",
            "اسم السائق", 
            "العنوان",
            "الهاتف",
            "من",
            "إلى",
            "نوع العقد",
            "رقم اللوحة",
            "تاريخ استلام السيارة",
            "تاريخ تسليم السيارة",
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

        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.driver_table)

        buttons_frame = tb.Frame(bottom_controls)
        buttons_frame.pack(side="left", expand=True)

        inner_buttons = tb.Frame(buttons_frame)
        inner_buttons.pack(anchor="center", padx=(0, 300))

        ttk.Button(inner_buttons, text="🖨️ طباعة", style="info.TButton", command=lambda: self._print_driver_table("current")).pack(side="left", padx=10)
        ttk.Button(inner_buttons, text="📁 عرض السائقين المؤرشفين", style="info.TButton", command=self._toggle_archived_drivers_window).pack(side="left", padx=10)
        ttk.Button(inner_buttons, text="📁 أرشيف قيادة السيارات", style="info.TButton", command=self._toggle_driver_car_assignments_archive).pack(side="left", padx=10)
        ttk.Button(inner_buttons, text="📝 تعديل السائق", style="Purple.TButton", command=self._edit_driver_record).pack(side="left", padx=10)

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
            self.show_message("warning", f"يرجى تعبئة الحقول التالية:\n- " + "\n- ".join(missing_fields))
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
                    self.show_message("warning", "تاريخ استلام السيارة يجب أن يكون في نفس يوم بداية العمل أو بعده.")
                    return
            except ValueError:
                pass  # تجاهل الخطأ إن كانت التواريخ غير صالحة

        # التحقق من أن السيارة وتاريخ من إجباريان
        if assigned_plate and not plate_from:
            self.show_message("warning", "يرجى إدخال تاريخ استلام السيارة.")
            return

        if plate_from and not assigned_plate:
            self.show_message("warning", "يرجى اختيار رقم اللوحة.")
            return

        if plate_from and plate_to:
            if not self.validate_date_range(plate_from, plate_to, context="السيارة"):
                return

        # لم نعد نستخدم license_plate
        if driver_from and driver_to:
            if not self.validate_date_range(driver_from, driver_to, context="العمل"):
                return

        if not driver_name:
            self.show_message("warning", "يرجى إدخال اسم السائق.")
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
                    self.show_message("warning", f"السائق '{driver_name}' لديه عقد حالي لم ينته بعد.")
                    return

                # حفظ السائق
                c.execute("""
                    INSERT INTO drivers (
                        name, address, phone,
                        car_received_date, employment_end_date,
                        contract_type,
                        issues,
                        assigned_plate, plate_from, plate_to
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    driver_name, 
                    data[3],  # العنوان الصحيح
                    data[4],  # الهاتف الصحيح
                    driver_from, 
                    driver_to,
                    self.contract_type_combo.get().strip(),  # نوع العقد من الكمبوبوكس مباشرة
                    data[9],  # الملاحظات الصحيحة
                    assigned_plate if assigned_plate else None,
                    plate_from if plate_from else None,
                    plate_to if plate_to else None
                ))
                conn.commit()

        except Exception as e:
            self.show_message("error", f"فشل الحفظ:\n{e}")
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
                self.show_message("error", f"⚠️ فشل أرشفة علاقة السيارة:\n{e}")

        self._load_driver_table_data()
        self.show_message("success", f"✅ تم حفظ السائق: {driver_name}")
        self._load_car_data()
        self._refresh_driver_comboboxes()
        self._refresh_driver_comboboxes()

    def _log_billing_record(self, doctor_name: str, lab_name: str, trip_date: str):
        import sqlite3

        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()

            # احسب عدد النقلات للطبيب في ذلك اليوم
            c.execute("""
                SELECT COUNT(*) FROM driver_tasks
                WHERE doctor = ? AND date = ?
            """, (doctor_name, trip_date))
            count = c.fetchone()[0]

            # السعر الفعلي وقت التنفيذ
            c.execute("""
                SELECT price FROM doctor_price_history
                WHERE doctor_name = ? AND date(effective_date) <= date(?)
                ORDER BY date(effective_date) DESC LIMIT 1
            """, (doctor_name, trip_date))
            res = c.fetchone()
            price = res[0] if res else 0

            total = count * price

            # حفظ في جدول billing_records
            c.execute("""
                INSERT INTO billing_records (doctor_name, trip_date, trip_count, price_at_time, total)
                VALUES (?, ?, ?, ?, ?)
            """, (doctor_name, trip_date, count, price, total))

            conn.commit()

    def _show_doctor_honorare(self):
        win = self.build_centered_popup("📊 حساب أجور الأطباء", 850, 500)

        # === الإطار العلوي للجدول ===
        tree_frame = tb.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(tree_frame, columns=("doctor", "trip_date", "trip_count", "price", "total"), show="headings", height=12)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, ["👨‍⚕️ الطبيب", "📅 التاريخ", "عدد النقلات", "💶 السعر عند التنفيذ", "💰 الإجمالي"])

        # === إطار الفلاتر ===
        filter_frame = tb.Frame(win)
        filter_frame.pack(fill="x", padx=10, pady=(0, 10))

        doctor_names = ["🔄 الكل"] + self.get_doctor_names()
        doctor_filter_combo = ttk.Combobox(filter_frame, values=doctor_names, width=25, state="readonly")
        doctor_filter_combo.set("🔄 الكل")
        doctor_filter_combo.pack(side="left", padx=(0, 15))

        ttk.Label(filter_frame, text="من:").pack(side="left")
        from_picker = CustomDatePicker(filter_frame)
        from_picker.pack(side="left", padx=(0, 10))

        ttk.Label(filter_frame, text="إلى:").pack(side="left")
        to_picker = CustomDatePicker(filter_frame)
        to_picker.pack(side="left", padx=(0, 10))

        def reload_data():
            selected_doctor = doctor_filter_combo.get()
            doctor_name = None if selected_doctor == "🔄 الكل" else selected_doctor
            from_date = from_picker.get().strip()
            to_date = to_picker.get().strip()

            try:
                query = """
                    SELECT doctor_name,
                           trip_date,
                           trip_count,
                           price_at_time,
                           total
                    FROM billing_records
                    WHERE 1=1
                """
                params = []
        
                if doctor_name:
                    query += " AND doctor_name = ?"
                    params.append(doctor_name)
                if from_date:
                    query += " AND date(trip_date) >= date(?)"
                    params.append(from_date)
                if to_date:
                    query += " AND date(trip_date) <= date(?)"
                    params.append(to_date)

                query += " ORDER BY doctor_name, trip_date"

                with sqlite3.connect("medicaltrans.db") as conn:
                    c = conn.cursor()
                    c.execute(query, params)
                    rows = c.fetchall()

                if not rows:
                    self.show_message("info", "❗ لا توجد بيانات لعرضها ضمن النطاق المحدد.")
                    return

            except Exception as e:
                self.show_message("error", f"خطأ في تحميل البيانات:\n{e}")
                return

            tree.delete(*tree.get_children())
            total_sum = 0.0

            for i, (doctor, trip_date, count, price, total) in enumerate(rows):
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                try:
                    total_val = float(total)
                    total_sum += total_val
                    tree.insert("", "end", values=(doctor, trip_date, count, f"{price:.2f} €", f"{total_val:.2f} €"), tags=(tag,))
                except Exception:
                    continue

            tree.insert("", "end", values=("", "", "", "📌 الإجمالي", f"{total_sum:.2f} €"), tags=("total",))
            tree.tag_configure("total", background="#e6e6e6", font=("Helvetica", 10, "bold"))
            self.apply_alternate_row_colors(tree)

        ttk.Button(filter_frame, text="عرض", style="info.TButton", command=reload_data).pack(side="left", padx=(10, 0))

        # === الأزرار السفلية ===
        controls_frame = tb.Frame(win)
        controls_frame.pack(fill="x", pady=10)

        center_buttons = tb.Frame(controls_frame)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self.export_table_to_pdf(tree, "📊 أجور الأطباء")).pack(side="left", padx=10)

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton", command=win.destroy).pack(side="left", padx=10)

        reload_data()

    def _get_last_driver_id(self):
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT MAX(id) FROM drivers")
            row = c.fetchone()
            return row[0] if row and row[0] else None

    def _edit_driver_record(self):
        selected = self.driver_table.selection()
        if not selected:
            self.show_message("warning", "يرجى اختيار سائق أولاً من الجدول.")
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

        edit_win = self.build_centered_popup("📝 تعديل بيانات السائق", 800, 450)
        main_frame = tb.Frame(edit_win, padding=15)
        main_frame.pack(fill="both", expand=True)

        # جعل الأعمدة متساوية في العرض
        main_frame.columnconfigure(0, weight=0, minsize=150)  # التسميات
        main_frame.columnconfigure(1, weight=1)  # حقول الإدخال

        entries = []

        # اسم السائق - نفس نمط باقي الحقول
        ttk.Label(main_frame, text="اسم السائق:").grid(row=0, column=0, sticky="e", padx=(10, 5), pady=6)
        name_entry = tb.Entry(main_frame, width=70)
        name_entry.insert(0, name)
        name_entry.grid(row=0, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(name_entry)
       
        # ===== من (بداية العمل) + إلى (نهاية العمل) بنفس التنسيق =====
        label_frame = tb.Frame(main_frame)
        label_frame.grid(row=1, column=0, sticky="e", padx=(10, 5), pady=6)

        ttk.Label(label_frame, text="من (بداية العمل):").pack(side="left")

        date_frame = tb.Frame(main_frame)
        date_frame.grid(row=1, column=1, sticky="w", pady=6)

        from_picker = CustomDatePicker(date_frame)
        from_picker.set(date_from)
        from_picker.pack(side="left", padx=(0, 10))

        spacer = tb.Label(date_frame, text="", width=8)
        spacer.pack(side="left")

        ttk.Label(date_frame, text="إلى (نهاية العمل):  ").pack(side="left", padx=(5, 5))
        to_picker = CustomDatePicker(date_frame)
        to_picker.set(date_to)
        to_picker.pack(side="left")

        # عنوان السائق
        ttk.Label(main_frame, text="عنوان السائق:").grid(row=2, column=0, sticky="e", padx=(10, 5), pady=6)
        address_entry = tb.Entry(main_frame, width=70)
        address_entry.insert(0, address)
        address_entry.grid(row=2, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(address_entry)

        # رقم الهاتف
        ttk.Label(main_frame, text="رقم الهاتف:").grid(row=3, column=0, sticky="e", padx=(10, 5), pady=6)
        phone_entry = tb.Entry(main_frame, width=70)
        phone_entry.insert(0, phone)
        phone_entry.grid(row=3, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(phone_entry)

        # نوع العقد
        ttk.Label(main_frame, text="نوع العقد:").grid(row=4, column=0, sticky="e", padx=(10, 5), pady=6)
        contract_combo = ttk.Combobox(main_frame, values=["Vollzeit", "Teilzeit", "Geringfügig"],
                                      state="readonly", width=68, justify="left")
        contract_combo.set(contract_type)
        contract_combo.grid(row=4, column=1, sticky="w", padx=(0, 5), pady=6)
        entries.append(contract_combo)

        # السيارة + من + إلى
        ttk.Label(main_frame, text="رقم اللوحة:").grid(row=5, column=0, sticky="e", padx=(10, 5), pady=6)
        car_row_frame = tb.Frame(main_frame)
        car_row_frame.grid(row=5, column=1, sticky="w", padx=(0, 5), pady=6)

        available_plates = ["🔓 بدون سيارة"]

        # ✅ إضافة السيارة الحالية للسائق إن وُجدت
        if assigned_plate and assigned_plate not in available_plates:
            available_plates.append(assigned_plate)

        # ✅ ثم إضافة باقي السيارات غير المرتبطة بسائقين آخرين
        for plate in self._get_available_cars_for_drivers():
            if plate != assigned_plate:
                available_plates.append(plate)

        plate_combo = ttk.Combobox(car_row_frame, values=available_plates, state="readonly", width=12)
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
        ttk.Label(main_frame, text="ملاحظات:").grid(row=6, column=0, sticky="e", padx=(10, 5), pady=6)
        notes_entry = tb.Entry(main_frame, width=70)
        notes_entry.insert(0, issues)
        notes_entry.grid(row=6, column=1, sticky="w", padx=(0, 5), pady=6)
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
                self.show_message("warning", "❗ يجب أولاً إنهاء استخدام السيارة (إدخال تاريخ 'إلى') قبل إنهاء عقد السائق.")
                return
            # ❗ التحقق من الشروط
            if not new_plate and (new_plate_from or new_plate_to):
                self.show_message("warning", "❗ لا يمكن إدخال تاريخ بدون اختيار سيارة.\nيرجى إما اختيار سيارة أو حذف التواريخ.")
                return
            if new_plate and new_plate_to and not new_plate_from:
                self.show_message("warning", "❗ لا يمكن إدخال تاريخ تسليم (إلى) بدون إدخال تاريخ استلام (من).")
                return
            if not new_data[0]:
                self.show_message("warning", "يرجى إدخال اسم السائق.")
                return
            if new_from and new_to:
                if not self.validate_date_range(new_from, new_to, context="مدة العمل"):
                    return
            if new_plate_from and not new_plate:
                self.show_message("warning", "يرجى اختيار رقم اللوحة.")
                return
            if new_plate and not new_plate_from:
                self.show_message("warning", "يرجى إدخال تاريخ استلام السيارة.")
                return
            if new_plate_from and new_plate_to:
                if not self.validate_date_range(new_plate_from, new_plate_to, context="السيارة"):
                    return
            if new_plate and new_to and not new_plate_to:
                new_plate_to = new_to
                self.show_message("info", "✅ تم استخدام تاريخ نهاية العمل كتاريخ تسليم السيارة، لأن حقل التسليم كان فارغًا.")
            if new_plate_from and new_from:
                try:
                    d_from = datetime.strptime(new_from, "%Y-%m-%d")
                    p_from = datetime.strptime(new_plate_from, "%Y-%m-%d")
                    if p_from < d_from:
                        self.show_message("warning", "تاريخ استلام السيارة يجب أن يكون في نفس يوم بداية العمل أو بعده.")
                        return
                except ValueError:
                    pass

            try:
                conn = sqlite3.connect("medicaltrans.db")
                c = conn.cursor()

                c.execute("SELECT assigned_plate, plate_to FROM drivers WHERE id = ?", (driver_id,))
                row = c.fetchone()
                original_plate = row[0] if row else ""
                original_plate_to = row[1] if row else ""

                # ✅ لا يسمح بتغيير السيارة دون إنهاء السابقة أولًا
                if original_plate and original_plate != new_plate and not original_plate_to:
                    self.show_message("warning", "❗ لا يمكن تغيير السيارة الحالية قبل إدخال تاريخ تسليم لها، أو إعادة اختيار نفس السيارة إن لم ترغب بتغييرها..")
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
                        self._refresh_main_comboboxes()

                        c.execute("""
                            UPDATE drivers SET
                                assigned_plate = NULL,
                                plate_from = NULL,
                                plate_to = NULL
                            WHERE id = ?
                        """, (driver_id,))
                        conn.commit()
                    except Exception as e:
                        self.show_message("warning", f"فشل أرشفة السيارة السابقة:\n{e}")
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
                    new_data[0],      # الاسم
                    new_data[1],      # العنوان
                    new_data[2],      # الهاتف
                    new_from,         # من (بداية العمل)
                    new_to,           # إلى (نهاية العمل)
                    new_plate or None,
                    new_plate_from or None,
                    new_plate_to or None,
                    new_data[4],      # الملاحظات (وليس new_data[4])
                    new_data[3],      # نوع العقد (وليس new_data[3])
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
                        self.show_message("warning", f"لم يتم أرشفة العلاقة:\n{archive_err}")

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
                            self.show_message("info", "✅ تم استخدام تاريخ نهاية العمل كتاريخ تسليم السيارة.")
                    except Exception as archive_err:
                        self.show_message("warning", f"فشل أرشفة العلاقة:\n{archive_err}")

                # ✅ التحديث النهائي وإغلاق النافذة
                self._load_driver_table_data()
                self.driver_table.reload_callback()
                self._load_car_data()
                self._refresh_driver_comboboxes()
                edit_win.destroy()
                message = "✅ تم تعديل بيانات السائق بنجاح."
                if extra_message:
                    message += f"\n{extra_message}"
                self.show_message("success", message)

            except Exception as e:
                self.show_message("error", f"فشل التعديل:\n{e}")

        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=7, column=0, columnspan=6, pady=20)  # تغيير الصف إلى 7

        # زر الحفظ
        tb.Button(btn_frame, text="💾 حفظ التعديلات", 
                 style="Green.TButton", 
                 command=lambda: save_driver_edit_changes(edit_win)).pack(side="left", padx=10, ipadx=10)
        
        # زر الإغلاق الجديد
        tb.Button(btn_frame, text="❌ إغلاق", 
                 style="danger.TButton", 
                 command=edit_win.destroy).pack(side="left", padx=10, ipadx=10)

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
                self.show_message("warning", "يرجى إدخال كافة الحقول.")
                return

            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                self.show_message("error", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
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
                    self.show_message("info", "لا توجد مهام لهذا الأسبوع.")
                    return

                filename = f"{driver_name}_schedule_{start_date}.pdf".replace(" ", "_")
                generate_weekly_schedule(driver_name, start_date, weekly_entries, filename)

                dialog.destroy()
                self.show_message("success", f"✅ تم توليد الملف:\n{filename}")

            except Exception as e:
                self.show_message("error", f"حدث خطأ أثناء التوليد:\n{e}")

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

        # ==== الحاوية العلوية (3 إطارات) ====
        top_row = tb.Frame(frame)
        top_row.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        for i in range(3):
            top_row.columnconfigure(i, weight=1, uniform="calendar")
        top_row.rowconfigure(0, weight=1)

        # ========== إطار إضافة حدث تقويمي ==========
        calendar_event_frame = tb.LabelFrame(top_row, text="إضافة حدث تقويمي", padding=10)
        calendar_event_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)

        # نوع الحدث
        ttk.Label(calendar_event_frame, text="نوع الحدث أو العطلة:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.event_type_combo = ttk.Combobox(
            calendar_event_frame, values=AUSTRIAN_HOLIDAYS, state="readonly", width=26, justify="left"
        )
        self.event_type_combo.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5, pady=2)

        # من + إلى (في نفس الصف)
        ttk.Label(calendar_event_frame, text="من:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.start_date_entry = CustomDatePicker(calendar_event_frame)
        self.start_date_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(calendar_event_frame, text="إلى:").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.end_date_entry = CustomDatePicker(calendar_event_frame)
        self.end_date_entry.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        # الملاحظات في صف مستقل
        ttk.Label(calendar_event_frame, text="الوصف / الملاحظات:").grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.event_desc_text = tb.Text(calendar_event_frame, width=36, height=1, wrap="word")
        self.event_desc_text.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=2)
        calendar_save_btn = ttk.Button(
            calendar_event_frame, text="💾 حفظ", style="Green.TButton", command=self._save_calendar_event
        )
        calendar_save_btn.grid(row=3, column=0, columnspan=4, pady=6)

        # ========== إطار إضافة إجازة ==========
        vacation_frame = tb.LabelFrame(top_row, text="إضافة إجازة", padding=10)
        vacation_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=0)
        # النوع + الاسم (نفس الصف)
        ttk.Label(vacation_frame, text="النوع:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.vac_type = ttk.Combobox(
            vacation_frame, values=["سائق", "طبيب"], state="readonly", width=13, justify="left"
        )
        self.vac_type.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.vac_type.bind("<<ComboboxSelected>>", self._load_vacation_names)
        ttk.Label(vacation_frame, text="الاسم:").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.vac_name = ttk.Combobox(
            vacation_frame, values=[""], state="readonly", width=26, justify="left"
        )
        self.vac_name.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        # من + إلى (نفس الصف)
        ttk.Label(vacation_frame, text="من:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.vac_start = CustomDatePicker(vacation_frame)
        self.vac_start.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(vacation_frame, text="إلى:").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.vac_end = CustomDatePicker(vacation_frame)
        self.vac_end.grid(row=1, column=3, sticky="w", padx=5, pady=2)
        # الملاحظات في صف مستقل
        ttk.Label(vacation_frame, text="الوصف / الملاحظات:").grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.vac_note_text = tb.Text(vacation_frame, width=36, height=1, wrap="word")
        self.vac_note_text.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=2)
        vac_save_btn = ttk.Button(
            vacation_frame, text="💾 حفظ", style="Orange.TButton", command=self._save_vacation
        )
        vac_save_btn.grid(row=3, column=0, columnspan=4, pady=6)

        # ========== إطار Extra Abholen ==========
        self._build_extra_abholen_frame(top_row)
        extra_abholen_frame = tb.LabelFrame(top_row, text="Extra Abholen", padding=10)
        extra_abholen_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=0)

        # اسم الطبيب: Combobox ببحث ذكي وفتح تلقائي عند الفوكس
        import sqlite3
        ttk.Label(extra_abholen_frame, text="اسم الطبيب:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM doctors WHERE (name IS NOT NULL AND name != '') ORDER BY name ASC")
            self.extra_all_doctors = [row[0] for row in c.fetchall()]

        self.extra_doctor_var = tk.StringVar()
        self.extra_doctor_entry = ttk.Entry(extra_abholen_frame, textvariable=self.extra_doctor_var, width=26)
        self.extra_doctor_entry.grid(row=0, column=1, columnspan=5, sticky="ew", padx=5, pady=2)
        self.extra_doctor_listbox = tk.Listbox(extra_abholen_frame, height=5)
        self.extra_doctor_listbox.grid_forget()

        def show_doctor_suggestions(event=None):
            typed = self.extra_doctor_var.get().strip().lower()
            filtered = [name for name in self.extra_all_doctors if typed in name.lower()] if typed else self.extra_all_doctors
            if not filtered:
                self.extra_doctor_listbox.grid_forget()
                return
            self.extra_doctor_listbox.delete(0, tk.END)
            for name in filtered:
                self.extra_doctor_listbox.insert(tk.END, name)
            row = self.extra_doctor_entry.grid_info()["row"]
            self.extra_doctor_listbox.grid(row=row+1, column=1, columnspan=5, sticky="ew", padx=5)
            self.extra_doctor_listbox.lift()

        def hide_doctor_suggestions(event=None):
            self.after(100, lambda: self.extra_doctor_listbox.grid_forget())

        def select_doctor_from_listbox(event=None):
            selection = self.extra_doctor_listbox.curselection()
            if selection:
                name = self.extra_doctor_listbox.get(selection[0])
                self.extra_doctor_var.set(name)
            self.extra_doctor_listbox.grid_forget()

        self.extra_doctor_entry.bind("<KeyRelease>", show_doctor_suggestions)
        self.extra_doctor_entry.bind("<FocusOut>", hide_doctor_suggestions)
        self.extra_doctor_listbox.bind("<ButtonRelease-1>", select_doctor_from_listbox)

        # الوقت + التاريخ في نفس الصف مع تقريب عناصر الوقت
        ttk.Label(extra_abholen_frame, text="Zeit:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        zeit_options = ["bis", "von - bis", "ab", "nach Anruf", "Anschl."]
        self.extra_time_combo = ttk.Combobox(
        extra_abholen_frame, values=zeit_options, state="readonly", width=8
        )
        self.extra_time_combo.grid(row=1, column=1, sticky="w", padx=(5, 1), pady=2)
        self.extra_time_combo.set(zeit_options[0])
        self.extra_time_from = ttk.Combobox(
            extra_abholen_frame,
            values=[f"{h:02d}:{m:02d}" for h in range(7, 18) for m in (0, 30)],
            width=7, state="readonly"
        )
        self.extra_time_from.grid(row=1, column=2, sticky="w", padx=(1, 1), pady=2)
        self.extra_time_from.set("10:00")
        self.extra_time_to = ttk.Combobox(
            extra_abholen_frame,
            values=[f"{h:02d}:{m:02d}" for h in range(7, 18) for m in (0, 30)],
            width=7, state="readonly"
        )
        self.extra_time_to.grid(row=1, column=3, sticky="w", padx=(1, 1), pady=2)
        self.extra_time_to.set("11:00")
        def _on_extra_time_change(event=None):
            typ = self.extra_time_combo.get()
            if typ == "von - bis":
                self.extra_time_from.grid()
                self.extra_time_to.grid()
            elif typ in ("bis", "ab"):
                self.extra_time_from.grid()
                self.extra_time_to.grid_remove()
            else:
                self.extra_time_from.grid_remove()
                self.extra_time_to.grid_remove()
        self.extra_time_combo.bind("<<ComboboxSelected>>", _on_extra_time_change)
        _on_extra_time_change()

        # التاريخ بجانب الوقت
        ttk.Label(extra_abholen_frame, text="التاريخ:").grid(row=1, column=4, sticky="w", padx=(5, 2), pady=2)
        self.extra_date_picker = CustomDatePicker(extra_abholen_frame)
        self.extra_date_picker.grid(row=1, column=5, sticky="w", padx=2, pady=2)

        # الملاحظات في صف مستقل
        ttk.Label(extra_abholen_frame, text="ملاحظات:").grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.extra_notes_text = tb.Text(extra_abholen_frame, width=36, height=1, wrap="word")
        self.extra_notes_text.grid(row=2, column=1, columnspan=5, sticky="ew", padx=5, pady=2)

        # زر الحفظ
        def _save_extra_abholen():
            doctor = self.extra_doctor_var.get().strip()
            time_type = self.extra_time_combo.get()
            date_str = self.extra_date_picker.get()
            notes = self.extra_notes_text.get("1.0", "end").strip()
            time_from = self.extra_time_from.get().strip() if self.extra_time_from.winfo_ismapped() else ""
            time_to = self.extra_time_to.get().strip() if self.extra_time_to.winfo_ismapped() else ""
            if time_type == "von - bis":
                zeit = f"{time_type} {time_from} - {time_to}"
            elif time_type in ("bis", "ab"):
                zeit = f"{time_type} {time_from}"
            else:
                zeit = time_type
            if not doctor or not date_str or not zeit:
                self.show_message("warning", "يرجى إدخال اسم الطبيب والتاريخ والوقت.")
                return
            title = f"Extra Abholen: {doctor}"
            description = f"Zeit: {zeit}\n{notes}".strip()
            start = end = date_str
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO calendar_events (title, description, start_date, end_date) VALUES (?, ?, ?, ?)",
                    (title, description, start, end),
                )
                conn.commit()
            self.show_message("success", f"✅ تم حفظ Extra Abholen للطبيب {doctor}.")
            self.extra_doctor_var.set("")
            self.extra_time_combo.set(zeit_options[0])
            _on_extra_time_change()
            self.extra_time_from.set("10:00")
            self.extra_time_to.set("11:00")
            self.extra_date_picker.set("")
            self.extra_notes_text.delete("1.0", "end")
            self._load_calendar_events()
        extra_save_btn = ttk.Button(
            extra_abholen_frame, text="💾 حفظ", style="Green.TButton", command=_save_extra_abholen
        )
        extra_save_btn.grid(row=3, column=0, columnspan=6, pady=6)

        # ===== جدول الأحداث المجدولة =====
        events_frame = tb.LabelFrame(frame, text="الأحداث المجدولة", padding=10)
        events_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        tree_frame = tb.Frame(events_frame)
        tree_frame.pack(fill="both", expand=True)
        columns = ("id", "title", "description", "start", "end")
        self.calendar_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=5)
        self.calendar_tree.column("id", width=0, stretch=False)
        self.calendar_tree.heading("id", text="")
        self.calendar_tree.reload_callback = self._load_calendar_events
        self._load_calendar_events()
        self.calendar_tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.calendar_tree.yview, style="TScrollbar")
        vsb.pack(side="right", fill="y")
        self.calendar_tree.configure(yscrollcommand=vsb.set)
        self.configure_tree_columns(self.calendar_tree, ["", "نوع الحدث", "ملاحظات", "من", "إلى"])
        bottom_controls = tb.Frame(events_frame)
        bottom_controls.pack(fill="x", pady=(10, 10))
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.calendar_tree, query_callback=self._load_calendar_events)
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)
        ttk.Button(
            center_buttons, text="🖨️ طباعة", style="info.TButton", command=lambda: self._print_calendar_table("current")
        ).pack(side="left", padx=10)
        ttk.Button(
            center_buttons, text="📁 عرض الأحداث المؤرشفة", style="info.TButton", command=self._toggle_archived_calendar_window
        ).pack(side="left", padx=10)
        ttk.Button(
            center_buttons, text="🗓️ تعديل العطلة", style="Purple.TButton", command=self._edit_selected_event
        ).pack(side="left", padx=10)
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        # ===== جدول الإجازات المباشر =====
        vac_table_frame = tb.LabelFrame(frame, text="الإجازات الحالية", padding=10)
        vac_table_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
        frame.rowconfigure(3, weight=1)
        tree_frame = tb.Frame(vac_table_frame)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        vac_table_frame.rowconfigure(0, weight=1)
        vac_table_frame.columnconfigure(0, weight=1)
        columns = ("id", "person_type", "name", "start", "end", "notes")
        self.vacation_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.vacation_tree.column("id", width=0, stretch=False)
        self.vacation_tree.heading("id", text="")
        self.vacation_tree.grid(row=0, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.vacation_tree.yview, style="TScrollbar")
        vsb.grid(row=0, column=1, sticky="ns")
        self.vacation_tree.configure(yscrollcommand=vsb.set)
        self.configure_tree_columns(self.vacation_tree, ["", "النوع", "الاسم", "من", "إلى", "ملاحظات"])
        self._load_vacations_inline = self._define_vac_load_func()
        self.vacation_tree.reload_callback = self._load_vacations_inline
        self._load_vacations_inline()
        self._load_original_data(
            self.vacation_tree,
            "SELECT id, person_type, name, start_date, end_date, notes FROM vacations WHERE end_date >= date('now') ORDER BY start_date ASC"
        )
        bottom_controls = tb.Frame(vac_table_frame)
        bottom_controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 10))
        search_frame = tb.Frame(bottom_controls)
        search_frame.pack(side="left", padx=(10, 0), anchor="w")
        self.attach_search_filter(search_frame, self.vacation_tree, query_callback=self._load_vacations_inline)
        center_buttons = tb.Frame(bottom_controls)
        center_buttons.pack(side="left", expand=True)
        ttk.Button(
            center_buttons, text="🖨️ طباعة", style="info.TButton", command=lambda: self._print_vacations_table("current")
        ).pack(side="left", padx=10)
        ttk.Button(
            center_buttons, text="📁 عرض الإجازات المؤرشفة", style="info.TButton", command=self._toggle_archived_vacations_window
        ).pack(side="left", padx=10)
        ttk.Button(
            center_buttons, text="📝 تعديل الإجازة", style="Purple.TButton", command=self._edit_selected_vacation_inline
        ).pack(side="left", padx=10)
        right_spacer = tb.Frame(bottom_controls)
        right_spacer.pack(side="left", expand=True)

        self._load_upcoming_calendar_events()
        frame.columnconfigure(0, weight=1)
        return frame

    def _edit_selected_vacation_inline(self):
        selected = self.vacation_tree.selection()
        if not selected:
            self.show_message("warning", "يرجى اختيار إجازة من الجدول لتعديلها.")
            return

        values = self.vacation_tree.item(selected[0])["values"]
        if len(values) < 6:
            self.show_message("error", "تعذر قراءة بيانات العطلة المحددة.")
            return

        vac_id, person_type, name, start_old, end_old, notes_old = values

        edit_win = self.build_centered_popup("✏️ تعديل الإجازة", 500, 320)

        main_frame = tb.Frame(edit_win)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # النوع
        ttk.Label(main_frame, text="النوع:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        ttk.Label(main_frame, text=person_type).grid(row=0, column=1, sticky="w", pady=5, padx=5)

        # الاسم
        ttk.Label(main_frame, text="الاسم:").grid(row=1, column=0, sticky="e", pady=5, padx=5)
        ttk.Label(main_frame, text=name).grid(row=1, column=1, sticky="w", pady=5, padx=5)

        # من تاريخ
        ttk.Label(main_frame, text="من تاريخ:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        start_picker = CustomDatePicker(main_frame)
        start_picker.set(start_old)
        start_picker.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        # إلى تاريخ
        ttk.Label(main_frame, text="إلى تاريخ:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        end_picker = CustomDatePicker(main_frame)
        end_picker.set(end_old)
        end_picker.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        # الوصف / الملاحظات
        ttk.Label(main_frame, text="الوصف / الملاحظات:").grid(row=4, column=0, sticky="ne", pady=5, padx=5)
        note_text = tb.Text(main_frame, height=3, wrap="word")
        note_text.grid(row=4, column=1, sticky="ew", pady=5, padx=5)
        note_text.insert("1.0", notes_old)
        note_text.tag_configure("left", justify="left")
        note_text.tag_add("left", "1.0", "end")

        def save_changes():
            new_start = start_picker.get().strip()
            new_end = end_picker.get().strip()

            if not new_start or not new_end:
                self.show_message("warning", "يرجى ملء كافة الحقول.")
                return

            if not self.validate_date_range(new_start, new_end, context="الإجازة"):
                return

            if not self.show_custom_confirm("تأكيد التعديل", "⚠️ هل تريد حفظ التعديلات؟"):
                return

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                new_notes = note_text.get("1.0", "end").strip()

                c.execute("""
                    UPDATE vacations SET start_date = ?, end_date = ?, notes = ? WHERE id = ?
                """, (new_start, new_end, new_notes, vac_id))
                conn.commit()

            self._load_vacations_inline()
            edit_win.destroy()
            self.show_message("success", "✅ تم تعديل العطلة بنجاح.")

        # زر الحفظ (نقل إلى صف جديد لتفادي التداخل)
        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_changes).pack(side="left", padx=10, ipadx=20)
        ttk.Button(btn_frame, text="❌ إغلاق", style="danger.TButton", command=edit_win.destroy).pack(side="left", padx=10, ipadx=20)

        main_frame.columnconfigure(1, weight=1)

    def _edit_selected_event(self):
        selected = self.calendar_tree.selection()
        if not selected:
            self.show_message("warning", "يرجى اختيار عطلة من الجدول لتعديلها.")
            return

        values = self.calendar_tree.item(selected[0])["values"]
        if len(values) < 5:
            self.show_message("error", "تعذر قراءة بيانات العطلة المحددة.")
            return

        event_id, title, desc, start_old, end_old = values

        edit_win = self.build_centered_popup("✏️ تعديل العطلة", 500, 300)

        main_frame = tb.Frame(edit_win)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
        ttk.Label(main_frame, text="نوع العطلة:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        title_combo = ttk.Combobox(main_frame, values=AUSTRIAN_HOLIDAYS, state="readonly", width=30, justify="left")
        title_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        title_combo.set(title)

        ttk.Label(main_frame, text="الوصف / الملاحظات:").grid(row=1, column=0, sticky="ne", pady=5, padx=5)
        desc_text = tb.Text(main_frame, width=40, height=3, wrap="word")
        desc_text.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        desc_text.insert("1.0", desc)

        ttk.Label(main_frame, text="من:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        start_picker = CustomDatePicker(main_frame)
        start_picker.set(start_old)
        start_picker.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(main_frame, text="إلى:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        end_picker = CustomDatePicker(main_frame)
        end_picker.set(end_old)
        end_picker.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        def save_changes():
            new_title = title_combo.get().strip()
            new_desc = desc_text.get("1.0", "end").strip()
            new_start = start_picker.get().strip()
            new_end = end_picker.get().strip()

            if not new_title or not new_start or not new_end:
                self.show_message("warning", "يرجى ملء جميع الحقول المطلوبة.")
                return

            if not self.validate_date_range(new_start, new_end, context="العطلة"):
                return

            if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حفظ التعديلات على العطلة؟"):
                return

            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    UPDATE calendar_events SET title = ?, description = ?, start_date = ?, end_date = ?
                    WHERE id = ?
                """, (new_title, new_desc, new_start, new_end, event_id))
                conn.commit()

            self._load_calendar_events()
            edit_win.destroy()
            self.show_message("success", "✅ تم تعديل العطلة بنجاح.")

        btn_frame = tb.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_changes).pack(side="left", padx=10, ipadx=20)
        ttk.Button(btn_frame, text="❌ إغلاق", style="danger.TButton", command=edit_win.destroy).pack(side="left", padx=10, ipadx=20)

        main_frame.columnconfigure(1, weight=1)

    def _define_vac_load_func(self):
        def _load_vacations_inline():
            self.load_table_from_db(
                self.vacation_tree,
                "SELECT id, person_type, name, start_date, end_date, notes FROM vacations WHERE end_date >= date('now') ORDER BY start_date ASC"
            )
        return _load_vacations_inline

    def _load_archived_vacations(self, treeview=None):
        today = datetime.today().strftime("%Y-%m-%d")
        tree = treeview or getattr(self, 'archived_vacations_tree', None)
        if not tree or not tree.winfo_exists():
            return
        self._load_original_data(
            tree,
            "SELECT id, person_type, name, start_date, end_date, notes FROM vacations WHERE end_date < ? ORDER BY end_date DESC",
            (today,)
        )

    def _toggle_archived_drivers_window(self):
        if self.archived_drivers_window is not None and self.archived_drivers_window.winfo_exists():
            self.archived_drivers_window.destroy()
            self.archived_drivers_window = None
            return

        # الأعمدة والعناوين
        columns = ("id", "name", "address", "phone", "car_received_date", "employment_end_date", "issues")
        labels = ["", "اسم السائق", "العنوان", "الهاتف", "من", "إلى", "ملاحظات"]

        # استخدام الدالة الموحدة
        self.build_table_window_with_search(
            title="📁 السائقين المؤرشفين",
            width=1000,
            height=500,
            columns=columns,
            column_labels=labels,
            reload_callback=self._load_archived_drivers,
            export_title="السائقين المؤرشفين"
        )

        # حفظ مرجع النافذة لأغراض التحكم لاحقًا
        self.archived_drivers_window = self.winfo_children()[-1]

    def _toggle_driver_car_assignments_archive(self):
        if hasattr(self, 'archived_driver_car_window') and self.archived_driver_car_window.winfo_exists():
            self.archived_driver_car_window.destroy()
            self.archived_driver_car_window = None
            return

        # تعيين الأعمدة والعناوين
        columns = (
            "id", "driver_id", "driver_name", "assigned_plate",
            "plate_from", "plate_to", "archived_at"
        )
        labels = [
            "", "", "اسم السائق", "رقم اللوحة",
            "من", "إلى", "تاريخ الأرشفة"
        ]

        # نافذة موحدة عبر الدالة الجديدة
        self.build_table_window_with_search(
            title="📁 أرشيف قيادة السيارات",
            width=1000,
            height=500,
            columns=columns,
            column_labels=labels,
            reload_callback=self._load_driver_car_archive,
            export_title="أرشيف قيادة السيارات"
        )

        # تخزين مرجع النافذة (مطلوب لإغلاقها لاحقًا)
        self.archived_driver_car_window = self.winfo_children()[-1]

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

        self.build_table_window_with_search(
            title="📁 الأحداث المؤرشفة",
            width=900,
            height=500,
            columns=columns,
            column_labels=labels,
            reload_callback=self._load_archived_calendar_events,
            extra_buttons=[
                ("🖨️ طباعة", lambda tree: self._print_calendar_table("archived", tree), "info.TButton")
            ]
        )

        self.archived_calendar_window = self.winfo_children()[-1]

    def _toggle_archived_vacations_window(self):
        if self.archived_vacations_window and self.archived_vacations_window.winfo_exists():
            self.archived_vacations_window.destroy()
            self.archived_vacations_window = None
            return

        columns = ("id", "person_type", "name", "start", "end", "notes")
        labels = ["", "النوع", "الاسم", "من", "إلى", "ملاحظات"]

        # تحميل حسب التاريخ الحالي
        today = datetime.today().strftime("%Y-%m-%d")

        def load_archived_vacations(tree):
            self._load_original_data(
                tree,
                "SELECT id, person_type, name, start_date, end_date, notes FROM vacations WHERE end_date < ? ORDER BY end_date DESC",
                (today,)
            )

        self.build_table_window_with_search(
            title="📁 الإجازات المؤرشفة",
            width=900,
            height=500,
            columns=columns,
            column_labels=labels,
            reload_callback=load_archived_vacations,
            export_title="الإجازات المؤرشفة"
        )

        self.archived_vacations_window = self.winfo_children()[-1]

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
                self.show_message("warning", "يرجى اختيار الحدث وتعبئة الحقول.")
                return

            if not self.show_custom_confirm("تأكيد الإجراء", "⚠️ هل أنت متأكد أنك تريد حفظ التعديلات على العطلة؟"):
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
            self.show_message("success", "✅ تم تعديل الحدث بنجاح.")

        def delete_event():
            if self._current_event_id is None:
                self.show_message("warning", "يرجى اختيار الحدث أولاً.")
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
            self.show_message("success", "✅ تم حذف الحدث بنجاح.")

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
            self.show_message("error", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return

        if not person_type or not name:
            self.show_message("warning", "يرجى اختيار النوع والاسم.")
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
        notes = self.vac_note_text.get("1.0", "end").strip()

        c.execute("""
            INSERT INTO vacations (person_type, name, start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (person_type, name, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), notes))
        conn.commit()
        conn.close()

        self.show_message("success", f"✅ تم حفظ الإجازة بنجاح لـ {name}.")

        # ✅ إعادة تعيين القوائم
        self.vac_type.set("")
        self.vac_name.set("")
        self.vac_start.entry.delete(0, tb.END)
        self.vac_end.entry.delete(0, tb.END)
        self.vac_note_text.delete("1.0", "end")

        if hasattr(self, '_load_vacations_inline'):
            self._load_vacations_inline()

    def is_holiday(self, date_obj):
        import sqlite3
        date_str = date_obj.strftime("%Y-%m-%d")
        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT 1 FROM calendar_events
                    WHERE ? BETWEEN start_date AND end_date
                """, (date_str,))
                return c.fetchone() is not None
        except Exception as e:
            print("خطأ التحقق من العطلة:", e)
            return False

    def _load_holidays_if_needed(self):
        if hasattr(self, "_holidays") and self._holidays:
            return
        self._holidays = set()
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT start_date, end_date FROM calendar_events")
            for start, end in c.fetchall():
                try:
                    start_date = datetime.strptime(start, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end, "%Y-%m-%d").date()
                    while start_date <= end_date:
                        self._holidays.add(start_date)
                        start_date += timedelta(days=1)
                except:
                    continue

    def get_doctor_names(self):
        import sqlite3
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM doctors ORDER BY name")
            return [row[0] for row in c.fetchall()]

    def get_driver_names(self, date_obj=None):
        import sqlite3
        from datetime import datetime

        if date_obj is None:
            date_obj = datetime.today()

        date_str = date_obj.strftime("%Y-%m-%d")

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

            drivers = []
            for (name,) in c.fetchall():
                # ✅ التحقق من الإجازة بناءً على التاريخ المحدد
                c.execute("""
                    SELECT 1 FROM vacations
                    WHERE person_type = 'سائق'
                    AND name = ?
                    AND ? BETWEEN start_date AND end_date
                """, (name, date_str))
                if not c.fetchone():  # فقط من ليس في إجازة
                    drivers.append(name)

            return drivers

    def get_doctors_by_weekday(self, weekday_key, target_date):
        import sqlite3
        from datetime import datetime

        today = datetime.today()
        results = []

        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()

            # استعلام بيانات الأطباء الذين يعملون في هذا اليوم
            c.execute("""
                SELECT id, name, visit_type, price_per_trip, materials, labs, street, city, zip_code,
                       weekday_times, weekdays
                FROM doctors
            """)
            doctors = c.fetchall()
    
            for row in doctors:
                (id_, name, visit_type, price, materials, labs, street, city, zip_code,
                 weekday_times, weekdays) = row

                # ✅ تحقق من الأيام والوقت
                if weekdays and weekday_times:
                    days = weekdays.strip().splitlines()
                    times = weekday_times.strip().splitlines()
                    label_to_key = {
                        "الإثنين": "mon", "الثلاثاء": "tue", "الأربعاء": "wed",
                        "الخميس": "thu", "الجمعة": "fri"
                    }
                    for i in range(len(days)):
                        label = days[i].strip().replace(" ", "")
                        expected_label = [k for k, v in label_to_key.items() if v == weekday_key]
                        if expected_label and label.replace(" ", "") == expected_label[0].replace(" ", ""):
                            time = times[i].strip()
                            break
                    else:
                        continue  # لم يتم التطابق
                else:
                    continue  # استبعاد الطبيب الذي لا يملك بيانات أيام

                # ✅ تحقق من الإجازة عبر calendar_events
                target_date_str = target_date.strftime("%Y-%m-%d")
                c.execute("""
                    SELECT 1 FROM vacations
                    WHERE ? BETWEEN start_date AND end_date
                    AND person_type = 'طبيب'
                    AND name = ?
                """, (target_date_str, name))
                if c.fetchone():
                    continue

                full_address = f"{zip_code} {city}, {street}"
                import json
                materials_text = materials
                if materials_text and materials_text.strip().startswith("["):
                    try:
                        materials_list = json.loads(materials_text)
                        materials_text = ", ".join(materials_list)
                    except:
                        pass
                labs_text = labs
                if labs_text and labs_text.strip().startswith("["):
                    try:
                        labs_list = json.loads(labs_text)
                        labs_text = ", ".join(labs_list)
                    except:
                        pass
                results.append({
                    "name": name,
                    "time": time,
                    "lab": labs_text,
                    "desc": visit_type,
                    "address": full_address,
                    "materials": materials_text,  # ✅ هذا هو العمود الصحيح الآن
                    "notes": ""                   # ✅ اتركه فارغًا كما اتفقنا
                })

            conn.close()
            return results

        except Exception as e:
            self.show_message("error", f"فشل تحميل بيانات الأطباء: {e}")
            return []

    def get_all_lab_names(self):
        import sqlite3
        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM labs")
                return [row[0] for row in c.fetchall()]
        except Exception as e:
            self.show_message("error", f"فشل جلب أسماء المخابر: {e}")
            return []

    def get_lab_transfers_by_weekday(self, weekday_key, target_date):
        import sqlite3

        results = []
        try:
            conn = sqlite3.connect("medicaltrans.db")
            c = conn.cursor()

            # ✅ استعلام الحقول المتاحة فقط
            c.execute("SELECT name, address FROM labs")
            labs = c.fetchall()

            for lab in labs:
                name, address = lab

                # ✅ بناء النتيجة مباشرة بدون الحاجة لتقسيم العنوان
                results.append({
                    "name": name,
                    "address": address
                })

            conn.close()
            return results

        except Exception as e:
            self.show_message("error", f"فشل تحميل المخابر: {e}")
            return []

    def _refresh_main_comboboxes(self):
        if not hasattr(self, "main_entries") or not hasattr(self, "main_driver_combo"):
            return  # لم يتم تحميل تبويب الرئيسية بعد

        doctor_names = self.get_doctor_names()
        lab_names = self.get_lab_names()
        driver_names = self.get_driver_names()

        if len(self.main_entries) >= 3:
            self.main_entries[0]["values"] = doctor_names      # الطبيب
            self.main_entries[1]["values"] = lab_names         # المخبر
            self.main_entries[2]["values"] = driver_names      # السائق

        self.main_driver_combo["values"] = driver_names

    def get_lab_names(self):
        import sqlite3
        with sqlite3.connect("medicaltrans.db") as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM labs ORDER BY name")
            return [row[0] for row in c.fetchall()]

    def _save_fuel_expense(self):
        name = self.fuel_driver_combo.get().strip()
        date = self.fuel_date_picker.get().strip()
        amount = self.fuel_amount_entry.get().strip()

        if not name or not date or not amount:
            self.show_message("warning", "يرجى ملء كل الحقول.")
            return

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.show_message("error", "صيغة المبلغ غير صحيحة. يجب أن يكون رقمًا موجبًا.")
            return

        try:
            with sqlite3.connect("medicaltrans.db") as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO fuel_expenses (driver_name, date, amount) VALUES (?, ?, ?)",
                    (name, date, amount)
                )
                conn.commit()

            self.show_message("success", "✅ تم حفظ مصروف الوقود.")
            self.fuel_driver_combo.set("")
            self.fuel_date_picker.entry.delete(0, tb.END)
            self.fuel_amount_entry.delete(0, tb.END)

        except Exception as e:
            self.show_message("error", f"فشل الحفظ:\n{e}")

    def _show_fuel_expense_table(self):
        win = self.build_centered_popup("📊 مصاريف الوقود", 850, 500)

        tree_frame = tb.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(tree_frame, columns=("driver", "date", "amount"), show="headings", height=12)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, ["اسم السائق", "تاريخ الدفع", "المبلغ (€)"])

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
                self.show_message("error", f"تعذر تحميل بيانات المصاريف:\n{e}", parent=win)
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
                self.show_message("warning", "يرجى تحديد سطر يحتوي على مصروف وقود.")
                return

            values = tree.item(selected[0], "values")
            if not values or not values[0].strip():
                self.show_message("warning", "⚠️ السطر المحدد لا يحتوي على اسم سائق صالح.")
                return

            old_driver = values[0].strip()
            old_date = values[1].strip()
            old_amount = values[2].strip()

            edit_win = self.build_centered_popup("📝 تعديل مصروف الوقود", 400, 250)
            frm = tb.Frame(edit_win, padding=20)
            frm.pack(fill="both", expand=True)
            frm.columnconfigure(1, weight=1)

            # --- اسم السائق ---
            ttk.Label(frm, text="اسم السائق:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
            driver_entry = ttk.Combobox(frm, values=self.get_driver_names(), width=30)
            driver_entry.set(old_driver)
            driver_entry.grid(row=0, column=1, sticky="w", pady=5)

            # --- التاريخ ---
            ttk.Label(frm, text="التاريخ:").grid(row=1, column=0, sticky="e", pady=5, padx=5)
            date_picker = CustomDatePicker(frm)
            date_picker.set(old_date)
            date_picker.grid(row=1, column=1, sticky="w", pady=5)

            # --- المبلغ ---
            ttk.Label(frm, text="المبلغ (€):").grid(row=2, column=0, sticky="e", pady=5, padx=5)
            amount_entry = tb.Entry(frm)
            amount_entry.insert(0, old_amount)
            amount_entry.grid(row=2, column=1, sticky="w", pady=5)

            # --- حفظ التعديل ---
            def save_edit():
                new_driver = driver_entry.get().strip()
                new_date = date_picker.get().strip()
                try:
                    new_amount = float(amount_entry.get().strip())
                    if new_amount <= 0:
                        raise ValueError
                except:
                    self.show_message("error", "المبلغ غير صالح.")
                    return

                if not new_driver or not new_date:
                    self.show_message("warning", "يرجى إدخال اسم السائق والتاريخ.")
                    return

                try:
                    old_amount_val = float(old_amount)
                except:
                    self.show_message("error", "المبلغ القديم غير صالح.")
                    return

                try:
                    with sqlite3.connect("medicaltrans.db") as conn:
                        c = conn.cursor()
                        c.execute("""
                            SELECT id FROM fuel_expenses
                            WHERE driver_name = ? AND date = ? AND amount = ?
                            LIMIT 1
                        """, (old_driver, old_date, old_amount_val))
                        row_ = c.fetchone()
                        if not row_:
                            self.show_message("error", "لم يتم العثور على السجل الأصلي.")
                            return
                        expense_id = row_[0]

                        c.execute("""
                            UPDATE fuel_expenses
                            SET driver_name = ?, date = ?, amount = ?
                            WHERE id = ?
                        """, (new_driver, new_date, new_amount, expense_id))
                        conn.commit()

                    edit_win.destroy()
                    self.show_message("success", "✅ تم تعديل المصروف بنجاح.", parent=win)
                    if hasattr(self, '_refresh_driver_comboboxes'):
                        self._refresh_driver_comboboxes()
                    load_all_fuel_expenses()
                except Exception as e:
                    self.show_message("error", f"فشل التعديل:\n{e}")

            # --- الأزرار ---
            btns = tb.Frame(frm)
            btns.grid(row=3, column=0, columnspan=2, pady=15)

            ttk.Button(btns, text="💾 حفظ", style="Green.TButton", command=save_edit)\
                .pack(side="left", padx=10, ipadx=15)

            ttk.Button(btns, text="❌ إغلاق", style="danger.TButton", command=edit_win.destroy)\
                .pack(side="left", padx=10, ipadx=15)

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
                self.show_message("success", "✅ تم حذف المصروف بنجاح.")
            except Exception as e:
                self.show_message("error", f"فشل الحذف:\n{e}")

        tree.bind("<Button-1>", on_click)


    def _show_filtered_fuel_expenses(self, driver_name, start_date, end_date):
        win = self.build_centered_popup("📊 مصاريف محددة", 850, 500)

        tree_frame = tb.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(tree_frame, columns=("driver", "date", "amount"), show="headings", height=12)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, ["اسم السائق", "تاريخ الدفع", "المبلغ (€)"])

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
            self.show_message("error", f"حدث خطأ أثناء جلب البيانات:\n{e}", parent=win)
            win.destroy()
            return

        if not rows:
            self.show_message("info", "لا توجد مصاريف مطابقة للفلتر.")
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
        controls_frame = tb.Frame(win)
        controls_frame.pack(fill="x", pady=10)

        center_buttons = tb.Frame(controls_frame)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self.export_table_to_pdf(tree, "تقرير مصاريف مفلترة")).pack(side="left", padx=10)

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton",
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
                self.show_message("info", "لا توجد مصاريف لهذا الشهر.")
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
            self.show_message("error", f"فشل إنشاء PDF:\n{e}")

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
                    self.show_message("warning", "يرجى إدخال اسم العطلة.")
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
            self.show_message("error", "صيغة التاريخ غير صحيحة. يرجى استخدام YYYY-MM-DD.")
            return

        if not self.validate_date_range(start_str, end_str, context="الحدث"):
            return

        # تحويل التواريخ إلى تنسيق قاعدة البيانات
        start = start_date.strftime("%Y-%m-%d")
        end = end_date.strftime("%Y-%m-%d")

        if not title or not start or not end:
            self.show_message("warning", "يرجى اختيار نوع الحدث والتاريخين.")
            return

        conn = sqlite3.connect("medicaltrans.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO calendar_events (title, description, start_date, end_date)
            VALUES (?, ?, ?, ?)
        """, (title, desc, start, end))
        conn.commit()
        conn.close()

        self.show_message("success", f"✅ تم حفظ حدث {title} في التقويم!")

        self.event_type_combo.set("")
        self.event_desc_text.delete("1.0", tb.END)
        self.start_date_entry.entry.delete(0, tb.END)
        self.end_date_entry.entry.delete(0, tb.END)

        self._load_calendar_events()

    def show_upcoming_appointments_popup(self):
        win = self.build_centered_popup("📌 المواعيد القادمة", 700, 450)

        # إعداد الجدول + الشريط + الأعمدة
        columns = ("id", "car", "type", "date")
        labels = ["", "رقم اللوحة", "نوع الموعد", "تاريخ الموعد"]

        tree_frame = tb.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self.appointment_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        self.appointment_tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.appointment_tree.yview, style="TScrollbar")
        self.appointment_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(self.appointment_tree, labels)

        # تحميل البيانات وتطبيق ألوان متناوبة
        self._load_upcoming_appointments()
        self.apply_alternate_row_colors(self.appointment_tree)

        # أزرار التعديل + الأرشفة + الإغلاق في الأسفل
        controls_frame = tb.Frame(win)
        controls_frame.pack(fill="x", pady=10)

        center_buttons = tb.Frame(controls_frame)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="📝 تعديل الموعد", style="Purple.TButton",
                   command=self._edit_selected_appointment).pack(side="left", padx=10)

        ttk.Button(center_buttons, text="📁 عرض المؤرشفة", style="info.TButton",
                   command=self._show_archived_appointments_window).pack(side="left", padx=10)

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton",
                   command=win.destroy).pack(side="left", padx=10)

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
            self.show_message("warning", "يرجى اختيار موعد أولاً.")
            return

        values = self.appointment_tree.item(selected[0], "values")
        appt_id, plate, appt_type, appt_date = values

        win = self.build_centered_popup("📝 تعديل الموعد", 350, 250)

        frm = tb.Frame(win, padding=20)
        frm.pack(fill="both", expand=True)

        # رقم اللوحة أولاً
        ttk.Label(frm, text="رقم اللوحة:").grid(row=0, column=0, sticky="e", pady=5)
        plate_entry = tb.Entry(frm)
        plate_entry.insert(0, plate)
        plate_entry.grid(row=0, column=1, pady=5)

        # تاريخ الموعد ثانيًا
        ttk.Label(frm, text="تاريخ الموعد:").grid(row=1, column=0, sticky="e", pady=5)
        date_picker = CustomDatePicker(frm)
        date_picker.set(appt_date)
        date_picker.grid(row=1, column=1, pady=5)

        # نوع الموعد ثالثًا
        ttk.Label(frm, text="نوع الموعد:").grid(row=2, column=0, sticky="e", pady=5)
        type_entry = tb.Entry(frm)
        type_entry.insert(0, appt_type)
        type_entry.grid(row=2, column=1, pady=5)

        def save_appointment_edit_changes():
            new_plate = plate_entry.get().strip()
            new_type = type_entry.get().strip()
            new_date = date_picker.get().strip()

            try:
                datetime.strptime(new_date, "%Y-%m-%d")
            except:
                self.show_message("error", "صيغة التاريخ غير صحيحة.")
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
            self.show_message("success", "✅ تم تعديل الموعد بنجاح.")

        # ✅ إطار الأزرار
        btn_frame = tb.Frame(frm)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)

        # أزرار متمركزة باستخدام grid داخل نفس الصف
        ttk.Button(btn_frame, text="💾 حفظ التعديلات", style="Green.TButton", command=save_appointment_edit_changes)\
            .grid(row=0, column=0, padx=10, ipadx=10)

        ttk.Button(btn_frame, text="❌ إغلاق", style="danger.TButton", command=win.destroy)\
            .grid(row=0, column=1, padx=10, ipadx=10)

        btn_frame.pack_propagate(False)

    def _show_archived_appointments_window(self):
        win = self.build_centered_popup("📁 المواعيد المؤرشفة", 700, 450)

        # إعداد الجدول + الأعمدة + شريط التمرير
        columns = ("id", "car", "type", "date")
        labels = ["", "رقم اللوحة", "نوع الموعد", "تاريخ الموعد"]

        tree_frame = tb.Frame(win)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.configure_tree_columns(tree, labels)

        # تحميل البيانات من قاعدة البيانات
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

        # ===== الأزرار في الأسفل بتوسيط واضح =====
        controls_frame = tb.Frame(win)
        controls_frame.pack(fill="x", pady=10)

        center_buttons = tb.Frame(controls_frame)
        center_buttons.pack(anchor="center")

        ttk.Button(center_buttons, text="🖨️ طباعة", style="info.TButton",
                   command=lambda: self._print_calendar_table("archived", tree)).pack(side="left", padx=10)

        ttk.Button(center_buttons, text="❌ إغلاق", style="danger.TButton",
                   command=win.destroy).pack(side="left", padx=10)

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
