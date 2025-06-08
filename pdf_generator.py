from datetime import datetime, timedelta

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def generate_driver_day_schedule(
    driver_name, date_str, weekday_name, entries, canvas_obj
):
    width, height = landscape(A4)

    # رأس الصفحة
    canvas_obj.setFont("Helvetica-Bold", 14)
    canvas_obj.drawString(2 * cm, height - 2 * cm, f"{weekday_name} – {date_str}")
    canvas_obj.drawString(2 * cm, height - 3 * cm, f"اسم السائق: {driver_name}")
    canvas_obj.drawString(2 * cm, height - 4 * cm, "بداية العمل: _____________")

    # جدول الأعمدة
    headers = ["الطبيب / المخبر", "الوقت", "الوصف / ما يجب أخذه", "العنوان"]
    col_widths = [8 * cm, 5 * cm, 12 * cm, 10 * cm]
    start_y = height - 5 * cm
    row_height = 1.2 * cm

    # رؤوس الأعمدة
    canvas_obj.setFont("Helvetica-Bold", 12)
    for i, header in enumerate(headers):
        x = sum(col_widths[:i]) + 2 * cm
        canvas_obj.rect(x, start_y, col_widths[i], -row_height, stroke=1, fill=0)
        canvas_obj.drawString(x + 0.2 * cm, start_y - 0.9 * cm, header)

    # صفوف البيانات
    canvas_obj.setFont("Helvetica", 11)
    for row_idx, row in enumerate(entries):
        y = start_y - (row_idx + 1) * row_height
        for col_idx, cell in enumerate(row):
            x = sum(col_widths[:col_idx]) + 2 * cm
            canvas_obj.rect(x, y, col_widths[col_idx], -row_height, stroke=1, fill=0)
            canvas_obj.drawString(x + 0.2 * cm, y - 0.9 * cm, str(cell))

    canvas_obj.showPage()


def generate_weekly_schedule(driver_name, start_date_str, weekly_entries, output_path):
    import sqlite3

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    conn = sqlite3.connect("medicaltrans.db")
    cursor = conn.cursor()

    weekdays_map = {
        0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة"
    }

    for i in range(7):  # مرّ على كامل الأسبوع لتجاهل السبت/الأحد والعطل
        current_date = start_date + timedelta(days=i)
        weekday_index = current_date.weekday()

        # ❌ تجاهل السبت (5) والأحد (6)
        if weekday_index > 4:
            continue

        date_str = current_date.strftime("%Y-%m-%d")

        # ❌ عطلة رسمية؟
        cursor.execute("SELECT 1 FROM holidays WHERE date = ?", (date_str,))
        if cursor.fetchone():
            continue

        # ❌ عطلة السائق؟
        cursor.execute("""
            SELECT 1 FROM vacations
            WHERE name = ? AND ? BETWEEN from_date AND to_date
        """, (driver_name, date_str))
        if cursor.fetchone():
            continue

        # ❌ هل يوجد طبيب في إجازة في المهام؟
        cursor.execute("""
            SELECT doctor FROM driver_tasks
            WHERE driver = ? AND date = ?
        """, (driver_name, date_str))
        doctors = cursor.fetchall()

        skip_day = False
        for (doc,) in doctors:
            cursor.execute("""
                SELECT 1 FROM vacations
                WHERE name = ? AND ? BETWEEN from_date AND to_date
            """, (doc, date_str))
            if cursor.fetchone():
                skip_day = True
                break

        if skip_day:
            continue

        # ✅ توليد الصفحة
        entries = weekly_entries.get(i, [])
        readable_date = current_date.strftime("%d/%m/%Y")
        weekday_name = weekdays_map[weekday_index]
        generate_driver_day_schedule(driver_name, readable_date, weekday_name, entries, c)

    conn.close()
    c.save()