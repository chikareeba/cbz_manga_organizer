import os
import re
import zipfile
import shutil
import tempfile
import urllib.request
import urllib.parse
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk


class GroupedCBZCombiner:
    def __init__(self, root):
        self.root = root
        self.root.title("CBZ Combiner")
        self.root.configure(bg="#1e1e1e")

        self.style = ttk.Style()
        self.style.theme_use("default")
        self.setup_styles()

        self.groups = {}
        self.group_covers = {}
        self.cover_failed = {}
        self.cover_preview_img = None
        self.cover_cache = {}

        # ---------- PREVIEW ----------
        # ---------- PREVIEW ----------
        preview_frame = tk.Frame(root, bg="#1e1e1e", width=220, height=320)
        preview_frame.pack(pady=10)

        # Prevent auto-resize
        preview_frame.pack_propagate(False)

        tk.Label(
            preview_frame,
            text="Cover Preview",
            fg="white",
            bg="#1e1e1e",
            font=("Segoe UI", 12, "bold")
        ).pack()

        self.cover_label = tk.Label(
            preview_frame,
            text="No Cover Loaded",
            fg="#aaaaaa",
            bg="#1e1e1e",
            width=200,
            height=300
        )

        self.cover_label.pack(expand=True)

        # ---------- MAIN ----------
        main = tk.Frame(root, bg="#1e1e1e")
        main.pack(padx=10, pady=10)

        left = tk.Frame(main, bg="#2a2a2a")
        left.grid(row=0, column=0, padx=10)

        tk.Label(left, text="Groups", fg="white", bg="#2a2a2a").pack()

        self.group_listbox = tk.Listbox(
            left, bg="#1e1e1e", fg="white",
            selectbackground="#3a3a3a", exportselection=False, width=25
        )
        self.group_listbox.pack()
        self.group_listbox.bind("<<ListboxSelect>>", self.load_group_files)

        ttk.Button(left, text="Add Group", command=self.add_group).pack()
        ttk.Button(left, text="Remove Group", command=self.remove_group).pack()
        ttk.Button(left, text="Set Cover", command=self.set_cover).pack()
        ttk.Button(left, text="Fetch Covers", command=self.fetch_all_covers).pack()
        ttk.Button(left, text="Export CBZ", command=self.export_cbz).pack()

        right = tk.Frame(main, bg="#2a2a2a")
        right.grid(row=0, column=1, padx=10)

        tk.Label(right, text="Drop CBZ Files Below",
                 fg="#aaaaaa", bg="#2a2a2a").pack()

        self.file_listbox = tk.Listbox(
            right, bg="#1e1e1e", fg="white",
            selectbackground="#3a3a3a", exportselection=False, width=60, height=12
        )
        self.file_listbox.pack()

        self.file_listbox.drop_target_register(DND_FILES)
        self.file_listbox.dnd_bind("<<Drop>>", self.drop_files)

        ttk.Button(right, text="Add Files", command=self.add_files).pack()
        ttk.Button(right, text="Remove", command=self.remove_file).pack()
        ttk.Button(right, text="Move Up", command=self.move_up).pack(pady=(10, 0))
        ttk.Button(right, text="Move Down", command=self.move_down).pack()

        # ---------- META ----------
        meta = tk.Frame(root, bg="#1e1e1e")
        meta.pack(pady=10)

        ttk.Label(meta, text="Title:").grid(row=0, column=0)
        self.title_entry = ttk.Entry(meta)
        self.title_entry.grid(row=0, column=1)

        ttk.Label(meta, text="Author:").grid(row=0, column=2)
        self.author_entry = ttk.Entry(meta)
        self.author_entry.grid(row=0, column=3)

    def setup_styles(self):
        self.style.configure("TButton", background="#3a3a3a", foreground="white")

    # ---------- AUTO COVER ----------
    def generate_cover_from_cbz(self, group):
        files = self.groups.get(group)
        if not files:
            return False

        try:
            with zipfile.ZipFile(files[0], 'r') as z:
                imgs = sorted([f for f in z.namelist()
                               if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
                if not imgs:
                    return

                with z.open(imgs[0]) as img_file:
                    img = Image.open(img_file).convert("RGB")
                    path = Path(f"auto_cover_{group.replace(' ', '_')}.jpg")
                    img.save(path, "JPEG", quality=95)
                    self.group_covers[group] = str(path)
                    return True
        except Exception as e:
            print("Auto cover failed:", e)

    # ---------- COVER PREVIEW ----------
    def update_cover_preview(self, group):
        path = self.group_covers.get(group)

        if not path or not os.path.exists(path):
            self.cover_label.config(image="", text="No Cover Loaded")
            return

        img = Image.open(path)
        img.thumbnail((200, 300))

        self.cover_preview_img = ImageTk.PhotoImage(img)

        self.cover_label.config(
            image=self.cover_preview_img,
            text="",
            width=200,
            height=300
        )
    # ---------- MOVE ----------
    def move_up(self):
        g = self.get_selected_group()
        sel = self.file_listbox.curselection()
        if not g or not sel:
            return
        i = sel[0]
        if i == 0:
            return
        items = self.groups[g]
        items.insert(i - 1, items.pop(i))
        self.load_group_files()
        self.file_listbox.select_set(i - 1)

    def move_down(self):
        g = self.get_selected_group()
        sel = self.file_listbox.curselection()
        if not g or not sel:
            return
        i = sel[0]
        items = self.groups[g]
        if i >= len(items) - 1:
            return
        items.insert(i + 1, items.pop(i))
        self.load_group_files()
        self.file_listbox.select_set(i + 1)

    # ---------- SORT ----------
    def sort_group(self, group):
        self.groups[group].sort(
            key=lambda p: int(re.findall(r'\d+', os.path.basename(p))[0]) if re.findall(r'\d+', os.path.basename(p)) else float('inf')
        )

    # ---------- FILE ----------
    def parse_volume(self, filename):
        m = re.search(r'(?:Vol|Volume)[\.\s]*(\d+)', filename, re.I)
        return int(m.group(1)) if m else None

    def drop_files(self, event):
        files = self.root.tk.splitlist(event.data)

        for f in files:
            f = f.strip("{}")
            if not f.lower().endswith(".cbz"):
                continue

            vol = self.parse_volume(f)

            if vol:
                group = f"Vol {vol}"
                if group not in self.groups:
                    self.groups[group] = []
                    self.group_covers[group] = None
                    self.cover_failed[group] = False
                self.groups[group].append(f)
            else:
                group = self.get_selected_group()
                if group:
                    self.groups[group].append(f)

        for g in self.groups:
            self.sort_group(g)

        self.refresh_group_list()
        self.load_group_files()

    def add_files(self):
        for f in filedialog.askopenfilenames():
            self.drop_files(type("event", (), {"data": f}))

    def remove_file(self):
        g = self.get_selected_group()
        if not g:
            return
        for i in reversed(self.file_listbox.curselection()):
            del self.groups[g][i]
        self.load_group_files()

    def load_group_files(self, event=None):
        sel = self.group_listbox.curselection()
        print(sel)
        if not sel:
            return
        group = self.group_listbox.get(sel[0])
        print(group)


        self.file_listbox.delete(0, tk.END)
        for f in self.groups[group]:
            self.file_listbox.insert(tk.END, os.path.basename(f))

        if not self.group_covers.get(group):
            cover_exists = self.generate_cover_from_cbz(group)

            if cover_exists:
                self.update_cover_preview(group)
        else:
            self.update_cover_preview(group)


    def get_selected_group(self):
        sel = self.group_listbox.curselection()
        return self.group_listbox.get(sel[0]) if sel else None

    def refresh_group_list(self):
        self.group_listbox.delete(0, tk.END)
        for g in sorted(self.groups):
            self.group_listbox.insert(tk.END, g)

    def add_group(self):
        name = simpledialog.askstring("Group", "Name:")
        if name:
            self.groups[name] = []
            self.group_covers[name] = None
            self.cover_failed[name] = False
            self.refresh_group_list()

    def remove_group(self):
        g = self.get_selected_group()
        if g:
            del self.groups[g]
            self.refresh_group_list()

    def set_cover(self):
        g = self.get_selected_group()
        file = filedialog.askopenfilename()
        if g and file:
            self.group_covers[g] = file
            self.update_cover_preview(g)

    # ---------- FETCH (FIXED) ----------
    def fetch_all_covers(self):
        title = self.title_entry.get()
        group = self.get_selected_group()

        if not title:
            messagebox.showwarning("Missing Title", "Enter a title first")
            return

        if not group:
            messagebox.showwarning("No Group Selected", "Select a group first")
            return

        images = self.fetch_cover_options(title)
        if not images:
            messagebox.showwarning("No Covers Found", "Could not find covers")
            return

        chosen = self.choose_cover_popup(images, group)
        if chosen:
            path = Path(f"cover_{group.replace(' ', '_')}.jpg")
            chosen.save(path)
            self.group_covers[group] = str(path)
            self.update_cover_preview(group)

    # ---------- COVER FETCH ----------
    def fetch_cover_options(self, title):
        images = []
        try:
            url = f"https://api.mangadex.org/manga?title={urllib.parse.quote(title)}"
            data = json.loads(urllib.request.urlopen(url).read())
            for manga in data["data"][:2]:
                mid = manga["id"]
                cover_url = f"https://api.mangadex.org/cover?manga[]={mid}"
                covers = json.loads(urllib.request.urlopen(cover_url).read())
                for c in covers["data"]:
                    img_url = f"https://uploads.mangadex.org/covers/{mid}/{c['attributes']['fileName']}"
                    try:
                        images.append(Image.open(urllib.request.urlopen(img_url)))
                    except:
                        pass
        except:
            pass
        return images

    def choose_cover_popup(self, images, group):
        win = tk.Toplevel(self.root)
        frame = tk.Frame(win)
        frame.pack()
        selected = {"img": None}

        def pick(img):
            selected["img"] = img
            win.destroy()

        tk_imgs = []
        for i, img in enumerate(images):
            thumb = img.copy()
            thumb.thumbnail((120, 180))
            tk_img = ImageTk.PhotoImage(thumb)
            tk_imgs.append(tk_img)

            lbl = tk.Label(frame, image=tk_img)
            lbl.grid(row=i//4, column=i%4)
            lbl.bind("<Button-1>", lambda e, im=img: pick(im))

        win.tk_imgs = tk_imgs
        self.root.wait_window(win)
        return selected["img"]

    # ---------- EXPORT ----------
    def export_cbz(self):
        output_dir = filedialog.askdirectory(title="Select Output Folder")
        if not output_dir:
            return

        for group, cbz_files in self.groups.items():
            if not cbz_files:
                continue

            temp_dir = tempfile.mkdtemp()
            counter = 1
            last_image = None

            try:
                cover_path = self.group_covers.get(group)
                if cover_path and os.path.exists(cover_path):
                    with Image.open(cover_path) as im:
                        im = im.convert("RGB")
                        im.save(os.path.join(temp_dir, f"{counter:05d}.jpg"), "JPEG", quality=95)
                        counter += 1

                for cbz in cbz_files:
                    extract_path = os.path.join(temp_dir, os.path.basename(cbz))
                    os.makedirs(extract_path, exist_ok=True)

                    with zipfile.ZipFile(cbz, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)

                    images = sorted([
                        os.path.join(root, f)
                        for root, _, files in os.walk(extract_path)
                        for f in files
                        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                    ])

                    last_image, counter = self.process_images_with_stitching(images, temp_dir, counter)

                if last_image is not None:
                    last_image.save(os.path.join(temp_dir, f"{counter:05d}.jpg"), "JPEG", quality=95)

                output_path = os.path.join(output_dir, f"{group}.cbz")
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out:
                    for img in sorted(Path(temp_dir).glob("*.jpg")):
                        out.write(img, img.name)

            finally:
                shutil.rmtree(temp_dir)

        messagebox.showinfo("Done", "CBZ export complete!")

    def process_images_with_stitching(self, image_paths, temp_dir, counter):
        last_image = None

        for img_path in image_paths:
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                width, height = im.size

                if height < 300 and last_image is not None:
                    prev_w, prev_h = last_image.size
                    new_img = Image.new("RGB", (prev_w, prev_h + height))
                    new_img.paste(last_image, (0, 0))
                    new_img.paste(im, (0, prev_h))
                    last_image = new_img
                    continue

                if last_image is not None:
                    last_image.save(os.path.join(temp_dir, f"{counter:05d}.jpg"), "JPEG", quality=95)
                    counter += 1

                last_image = im

        return last_image, counter


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = GroupedCBZCombiner(root)
    root.mainloop()