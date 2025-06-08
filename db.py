import sqlite3

# القيم الصحيحة
valid_options = ["حتى الساعة", "من - إلى", "بعد الساعة", "عند الاتصال", "بدون موعد"]

def super_normalize(text):
    if not text:
        return ''
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(' ' if unicodedata.category(c) == 'Zs' else c for c in text)
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
    return text.strip()

def best_match_option(val):
    val = super_normalize(val)
    for opt in valid_options:
        if val.startswith(super_normalize(opt)):
            return opt
    return None

with sqlite3.connect("medicaltrans.db") as conn:
    c = conn.cursor()
    c.execute("SELECT id, mon_time, tue_time, wed_time, thu_time, fri_time FROM doctors")
    for row in c.fetchall():
        id_, *times = row
        new_times = []
        update_needed = False
        for t in times:
            if t:
                opt = best_match_option(t)
                if opt:
                    # استبدل الخيار في بداية النص بالخيار الصحيح
                    rest = t[len(opt):].strip() if t.strip().startswith(opt) else t
                    new_time = f"{opt} {rest}".strip() if rest else opt
                    if new_time != t:
                        update_needed = True
                    new_times.append(new_time)
                else:
                    new_times.append(t)
            else:
                new_times.append(None)
        if update_needed:
            print(f"تحديث id={id_} -> {new_times}")
            c.execute("""
                UPDATE doctors SET
                    mon_time=?, tue_time=?, wed_time=?, thu_time=?, fri_time=?
                WHERE id=?
            """, (*new_times, id_))
    conn.commit()
print("تم التصحيح.")