import tkinter as tk
from datetime import datetime, timedelta
import ttkbootstrap as tb

class CustomDatePicker(tb.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.selected_date = tk.StringVar()
        self._outside_click_binding = None
        self._is_inside_toplevel = isinstance(master, tk.Toplevel)  # ✅

        self._create_widgets()

    def _create_widgets(self):
        self.entry = tb.Entry(self, textvariable=self.selected_date, width=12)
        self.entry.pack(side='left', padx=(0, 5))

        self.cal_btn = tb.Button(self, text='📅', command=self._show_calendar, width=3)
        self.cal_btn.pack(side='left')

    def _show_calendar(self):
        if hasattr(self, 'popup') and self.popup.winfo_exists():
            self._close_calendar()
            return

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()

        self.popup = tb.Toplevel(self)
        self.popup.title("📅 التاريخ")
        self.popup.geometry(f"240x220+{x}+{y}")
        self.popup.transient(self.winfo_toplevel())

        # ✅ نفعّل grab لفترة قصيرة جدًا
        self.popup.grab_set()
        self.popup.after(100, lambda: self.popup.grab_release())

        self.popup.protocol("WM_DELETE_WINDOW", self._close_calendar)
        self.popup.bind("<Destroy>", lambda e: self._close_calendar(), add="+")

        self._calendar_frame = tb.Frame(self.popup)
        self._calendar_frame.pack()

        self.current_date = datetime.today().replace(day=1)
        self._draw_calendar()

        self._outside_click_binding = self.winfo_toplevel().bind("<Button-1>", self._handle_outside_click, add="+")

    def _handle_outside_click(self, event):
        if not hasattr(self, 'popup') or not self.popup.winfo_exists():
            return

        widget = self.popup.winfo_containing(event.x_root, event.y_root)
        if widget is None or not str(widget).startswith(str(self.popup)):
            self._close_calendar()

    def _close_calendar(self):
        if hasattr(self, 'popup') and self.popup.winfo_exists():
            try:
                self.popup.grab_release()  # ⬅️ يمكن تركه احتياطيًا
            except:
                pass
            self.popup.destroy()

        try:
            if self._outside_click_binding:
                parent = self.winfo_toplevel()
                if parent.winfo_exists():
                    parent.unbind("<Button-1>", self._outside_click_binding)
        except:
            pass
        self._outside_click_binding = None

    def _draw_calendar(self):
        for widget in self._calendar_frame.winfo_children():
            widget.destroy()

        style = tb.Style()
        style.configure("Calendar.TButton", font=("Segoe UI", 9), padding=3)

        header = tb.Frame(self._calendar_frame)
        header.pack(pady=5)

        tb.Button(header, text='<', width=3, command=lambda: self._change_month(-1)).pack(side='left')
        self.month_label = tb.Label(header, text=self.current_date.strftime('%B %Y'), font=('Segoe UI', 10, 'bold'))
        self.month_label.pack(side='left', padx=10)
        tb.Button(header, text='>', width=3, command=lambda: self._change_month(1)).pack(side='left')

        days_frame = tb.Frame(self._calendar_frame)
        days_frame.pack(padx=5)

        days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
        for i, day in enumerate(days):
            tb.Label(days_frame, text=day, width=3, anchor='center', font=("Segoe UI", 9, "bold"))\
                .grid(row=0, column=i, padx=1, pady=1)

        first_day = self.current_date
        start_day = (first_day.weekday() + 1) % 7
        next_month = (self.current_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        num_days = (next_month - first_day).days

        row = 1
        col = start_day

        for day in range(1, num_days + 1):
            btn = tb.Button(
                days_frame,
                text=str(day),
                width=3,
                style="Calendar.TButton",
                command=lambda d=day: self._select_date(d)
            )
            btn.grid(row=row, column=col, padx=1, pady=1)

            col += 1
            if col > 6:
                col = 0
                row += 1

    def _change_month(self, offset):
        year = self.current_date.year
        month = self.current_date.month + offset
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self.current_date = datetime(year, month, 1)
        self._draw_calendar()

    def _select_date(self, day):
        date = datetime(self.current_date.year, self.current_date.month, day)
        self.selected_date.set(date.strftime('%Y-%m-%d'))
        self._close_calendar()

    def get(self):
        return self.selected_date.get()

    def set(self, date_str):
        self.selected_date.set(date_str)