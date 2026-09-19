import csv
import os
import re
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import zxingcpp
except ImportError:
    zxingcpp = None

try:
    from PIL import Image, ImageOps, ImageFilter
except ImportError:
    Image = None


APP_TITLE = "Честный знак — PDF → CSV для Контур СУЛ"
CSV_HEADERS = ["Код маркировки", "GTIN", "Название товара"]


def clean_decoded(value: str) -> str:
    """Normalize scanner output without destroying GS1 group separators."""
    if value is None:
        return ""
    value = value.replace("\x00", "")
    value = value.replace("\r", "").replace("\n", "")
    # Keep ASCII 29 (GS) — it is meaningful in GS1 DataMatrix.
    return value.strip()


def looks_like_marking_code(value: str) -> bool:
    value = clean_decoded(value)
    # Typical Russian Chestny Znak GS1 DataMatrix starts with AI 01.
    # Do not reject codes containing GS (ASCII 29), spaces or punctuation.
    return bool(re.match(r"^01\d{14}", value))


def render_page(page, dpi=300):
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    mode = "RGB"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples)


def decode_image(img):
    """Decode DataMatrix from several robust image variants."""
    if zxingcpp is None:
        raise RuntimeError("Не установлен zxing-cpp.")

    variants = [img]
    gray = ImageOps.grayscale(img)
    variants.append(gray)
    variants.append(ImageOps.autocontrast(gray))
    variants.append(gray.filter(ImageFilter.SHARPEN))
    try:
        variants.append(gray.point(lambda p: 255 if p > 170 else 0))
    except Exception:
        pass

    out = []
    seen = set()
    for variant in variants:
        try:
            results = zxingcpp.read_barcodes(variant)
        except Exception:
            continue
        for r in results:
            try:
                text = r.text
            except Exception:
                continue
            if text:
                text = clean_decoded(text)
                if text and text not in seen:
                    seen.add(text)
                    out.append(text)
    return out


def decode_pdf(path, progress_cb=None):
    if fitz is None or Image is None or zxingcpp is None:
        raise RuntimeError(
            "Не хватает библиотек. Установите зависимости из requirements.txt: "
            "PyMuPDF, Pillow, zxing-cpp."
        )

    found = []
    doc = fitz.open(path)
    try:
        total = len(doc)
        for i, page in enumerate(doc):
            # Try progressively higher DPI. This is important for small
            # graphical DataMatrix codes embedded in PDF pages.
            decoded = []
            for dpi in (300, 450, 600):
                img = render_page(page, dpi)
                decoded = decode_image(img)
                if decoded:
                    break

            for code in decoded:
                if looks_like_marking_code(code):
                    found.append(code)

            if progress_cb:
                progress_cb(i + 1, total)
    finally:
        doc.close()
    return found


class ContextMenu:
    def __init__(self, widget):
        self.widget = widget
        self.menu = tk.Menu(widget, tearoff=False)
        self.menu.add_command(label="Вырезать", command=self.cut)
        self.menu.add_command(label="Копировать", command=self.copy)
        self.menu.add_command(label="Вставить", command=self.paste)
        self.menu.add_separator()
        self.menu.add_command(label="Выделить всё", command=self.select_all)
        widget.bind("<Button-3>", self.popup)
        widget.bind("<Control-Button-1>", self.popup)

    def popup(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def cut(self):
        try:
            self.widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def copy(self):
        try:
            self.widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def paste(self):
        try:
            self.widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    def select_all(self):
        try:
            self.widget.select_range(0, "end")
            self.widget.icursor("end")
        except tk.TclError:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1040x700")
        self.minsize(900, 600)

        self.codes = []
        self.pdf_files = []

        self.gtin = tk.StringVar()
        self.product = tk.StringVar()
        self.status = tk.StringVar(value="Готово. Загрузите PDF.")
        self.count_var = tk.StringVar(value="0")
        self.valid_var = tk.StringVar(value="0")
        self.dup_var = tk.StringVar(value="0")

        self._build_style()
        self._build_ui()

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10))
        style.configure("Card.TFrame", padding=18)
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 10))
        style.configure("Big.TEntry", padding=9, font=("Segoe UI", 11))
        style.configure("Stat.TLabel", font=("Segoe UI", 15, "bold"))

    def _build_ui(self):
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="PDF → CSV", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Распознавание графических DataMatrix «Честного знака» для Контур СУЛ",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        card = ttk.LabelFrame(root, text="Данные товара", padding=16)
        card.pack(fill="x", pady=(0, 14))

        ttk.Label(card, text="GTIN").grid(row=0, column=0, sticky="w", padx=(0, 10))
        e1 = ttk.Entry(card, textvariable=self.gtin, style="Big.TEntry")
        e1.grid(row=1, column=0, sticky="ew", padx=(0, 18))
        ContextMenu(e1)

        ttk.Label(card, text="Название товара").grid(row=0, column=1, sticky="w", padx=(0, 10))
        e2 = ttk.Entry(card, textvariable=self.product, style="Big.TEntry")
        e2.grid(row=1, column=1, sticky="ew")
        ContextMenu(e2)

        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=2)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(0, 14))

        ttk.Button(
            actions, text="📄  Загрузить PDF", style="Primary.TButton",
            command=self.select_pdf
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            actions, text="Очистить", command=self.clear_all
        ).pack(side="left", padx=8)

        ttk.Button(
            actions, text="Экспорт CSV для СУЛ", style="Primary.TButton",
            command=self.export_csv
        ).pack(side="right")

        stats = ttk.Frame(root)
        stats.pack(fill="x", pady=(0, 14))
        for title, variable in [
            ("Найдено", self.count_var),
            ("Корректных", self.valid_var),
            ("Дубликатов", self.dup_var),
        ]:
            box = ttk.LabelFrame(stats, text=title, padding=12)
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            ttk.Label(box, textvariable=variable, style="Stat.TLabel").pack(anchor="w")

        table_frame = ttk.LabelFrame(root, text="Распознанные коды", padding=8)
        table_frame.pack(fill="both", expand=True)

        columns = ("n", "code", "gtin", "name")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("n", text="№")
        self.tree.heading("code", text="Код маркировки")
        self.tree.heading("gtin", text="GTIN")
        self.tree.heading("name", text="Название товара")
        self.tree.column("n", width=55, anchor="center")
        self.tree.column("code", width=540)
        self.tree.column("gtin", width=150)
        self.tree.column("name", width=250)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        # Dedicated result line remains visible when the window is resized.
        result_bar = ttk.Frame(root)
        result_bar.pack(fill="x", pady=(10, 0))
        ttk.Label(result_bar, text="Уникальных кодов:", style="Sub.TLabel").pack(side="left")
        ttk.Label(result_bar, textvariable=self.count_var, style="Stat.TLabel").pack(side="left", padx=(6, 18))
        ttk.Label(result_bar, textvariable=self.status, style="Sub.TLabel").pack(
            side="left", fill="x", expand=True
        )

    def select_pdf(self):
        files = filedialog.askopenfilenames(
            title="Выберите PDF с DataMatrix",
            filetypes=[("PDF", "*.pdf"), ("Все файлы", "*.*")]
        )
        if not files:
            return

        self.pdf_files = list(files)
        self.status.set(f"Выбрано PDF: {len(files)}. Начинаю распознавание…")
        self._set_busy(True)

        threading.Thread(target=self._worker, args=(self.pdf_files,), daemon=True).start()

    def _worker(self, files):
        all_codes = []
        errors = []

        for idx, path in enumerate(files, 1):
            try:
                codes = decode_pdf(
                    path,
                    progress_cb=lambda page, total, p=path: self.after(
                        0, lambda: self.status.set(
                            f"{Path(p).name}: страница {page}/{total}"
                        )
                    )
                )
                all_codes.extend(codes)
            except Exception as exc:
                errors.append(f"{Path(path).name}: {exc}")

        # Preserve order while removing exact duplicates.
        unique = list(dict.fromkeys(all_codes))

        self.after(0, self._finish_decode, unique, errors)

    def _finish_decode(self, codes, errors):
        self.codes = codes
        self._refresh_table()

        if errors:
            self.status.set(
                f"Готово. Кодов: {len(codes)}. Ошибки: {len(errors)}."
            )
            messagebox.showwarning(
                "Распознавание завершено с ошибками",
                "\n".join(errors[:10]) + (
                    "\n…" if len(errors) > 10 else ""
                )
            )
        else:
            self.status.set(f"Готово. Уникальных кодов: {len(codes)}.")

        self._set_busy(False)

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for i, code in enumerate(self.codes, 1):
            self.tree.insert(
                "", "end",
                values=(i, code, self.gtin.get().strip(), self.product.get().strip())
            )

        self.count_var.set(str(len(self.codes)))
        self.valid_var.set(str(sum(looks_like_marking_code(c) for c in self.codes)))

    def _set_busy(self, busy):
        if busy:
            self.config(cursor="watch")
        else:
            self.config(cursor="")

    def clear_all(self):
        self.codes = []
        self.pdf_files = []
        self.gtin.set("")
        self.product.set("")
        self._refresh_table()
        self.status.set("Очищено. Готово к новой загрузке.")

    def export_csv(self):
        if not self.codes:
            messagebox.showwarning("Нет кодов", "Сначала загрузите PDF и распознайте DataMatrix.")
            return

        gtin = self.gtin.get().strip()
        product = self.product.get().strip()

        if not re.fullmatch(r"\d{14}", gtin):
            messagebox.showwarning("GTIN", "GTIN должен содержать ровно 14 цифр.")
            return

        if not product:
            messagebox.showwarning("Название товара", "Введите название товара.")
            return

        path = filedialog.asksaveasfilename(
            title="Сохранить CSV для Контур СУЛ",
            defaultextension=".csv",
            filetypes=[("CSV UTF-8", "*.csv")]
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
                writer.writerow(CSV_HEADERS)
                for code in self.codes:
                    writer.writerow([code, gtin, product])

            self.status.set(f"CSV сохранён: {Path(path).name}")
            messagebox.showinfo(
                "Готово",
                f"CSV создан.\n\nКодов: {len(self.codes)}\nФайл: {path}"
            )
        except Exception as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))


if __name__ == "__main__":
    App().mainloop()
