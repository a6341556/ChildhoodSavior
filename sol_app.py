import os
import queue
import threading
import time
import tkinter as tk
from itertools import chain
from tkinter import filedialog, messagebox, ttk

from sol_editor import SOLFile


class SOLEditorApp:
    PAGE_SIZE = 200

    def __init__(self, master):
        self.master = master
        master.title("Flash LSO 存檔編輯器")
        master.geometry("960x650")
        self.sol_handler = SOLFile()
        self.paths = {}
        self.pages = {}
        self.pending = set()
        self.selected = None
        self.dirty = False
        self.busy = False
        self.results = queue.Queue()
        controls = ttk.Frame(master, padding=10)
        controls.pack(fill="x")
        self.open_button = ttk.Button(controls, text="開啟 .sol 檔案", command=self.open_file)
        self.open_button.pack(side="left")
        self.save_button = ttk.Button(controls, text="儲存修改", command=self.save_changes, state="disabled")
        self.save_button.pack(side="right")
        self.filepath_label = ttk.Label(controls, text="請開啟 .sol 檔案")
        self.filepath_label.pack(side="left", padx=10)
        frame = ttk.Frame(master, padding=10)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("value", "type"), selectmode="browse")
        for column, title, width in (("#0", "欄位／索引（展開查看子項目）", 280), ("value", "值／摘要", 420), ("type", "型別", 120)):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", self.expand_node)
        self.tree.bind("<<TreeviewSelect>>", self.select_node)
        editor = ttk.Frame(master, padding=10)
        editor.pack(fill="x")
        self.path_label = ttk.Label(editor, text="選取數值或字串欄位以編輯")
        self.path_label.pack(anchor="w")
        self.value_text = tk.Text(editor, height=3, wrap="word", state="disabled")
        self.value_text.pack(fill="x", pady=5)
        self.apply_button = ttk.Button(editor, text="套用欄位修改", command=self.apply_edit, state="disabled")
        self.apply_button.pack(anchor="e")
        self.status = ttk.Label(master, text="容器按需展開，每批最多顯示 200 個欄位。", padding=5)
        self.status.pack(fill="x")
        master.after(50, self.poll_results)
        master.protocol("WM_DELETE_WINDOW", self.close)

    @staticmethod
    def is_container(value):
        return isinstance(value, (dict, list, tuple))

    @staticmethod
    def preview(value):
        if SOLEditorApp.is_container(value):
            return f"{len(value)} 個項目"
        if isinstance(value, str):
            return value[:160].replace("\n", "\\n") + ("…" if len(value) > 160 else "")
        if type(value) in (bool, int, float, type(None)):
            return str(value)
        return f"<{type(value).__name__}>"

    def set_busy(self, busy):
        self.busy = busy
        self.open_button.configure(state="disabled" if busy else "normal")
        self.save_button.configure(state="disabled" if busy or self.sol_handler.sol_instance is None else "normal")
        self.select_node()

    def run_job(self, action, function):
        self.set_busy(True)

        def work():
            started = time.perf_counter()
            try:
                result = function()
                self.results.put((action, result, None, time.perf_counter() - started))
            except Exception as error:
                self.results.put((action, None, error, time.perf_counter() - started))

        threading.Thread(target=work, daemon=True).start()

    def poll_results(self):
        try:
            action, result, error, elapsed = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            if error is not None:
                messagebox.showerror("操作失敗", str(error))
                self.status.configure(text="操作失敗；原有資料仍保留。")
            elif action == "load":
                self.sol_handler = result
                self.display_data(result.get_data())
                self.dirty = False
                self.filepath_label.configure(text=os.path.basename(result.filepath))
                self.status.configure(text=f"讀檔與解碼：{elapsed:.3f} 秒。展開容器查看內容。")
            else:
                self.dirty = False
                self.status.configure(text=f"儲存完成：{elapsed:.3f} 秒。")
            self.set_busy(False)
        self.master.after(50, self.poll_results)

    def has_unapplied_edit(self):
        return self.selected is not None and self.value_text.edit_modified()

    def confirm_discard(self):
        return not (self.dirty or self.has_unapplied_edit()) or messagebox.askyesno("尚未儲存", "放棄尚未儲存的修改？")

    def open_file(self):
        if self.busy or not self.confirm_discard():
            return
        filepath = filedialog.askopenfilename(filetypes=[("Flash Shared Object Files", "*.sol")])
        if filepath:
            # 放棄尚未套用的欄位，避免舊欄位影響下一份檔案。
            self.value_text.edit_modified(False)
            self.status.configure(text="正在讀取與解碼…")
            self.run_job("load", lambda: SOLFile(filepath))

    def display_data(self, data):
        self.selected = None
        self.tree.delete(*self.tree.get_children())
        self.paths.clear()
        self.pages.clear()
        self.pending.clear()
        self.add_page("", (), data)
        self.select_node()

    def add_page(self, parent, path, value, iterator=None):
        if iterator is None:
            iterator = iter(value.items()) if isinstance(value, dict) else enumerate(value)
        ancestors = {id(self.sol_handler.data)}
        ancestor = self.sol_handler.data
        for key in path:
            ancestor = ancestor[key]
            ancestors.add(id(ancestor))
        for _ in range(self.PAGE_SIZE):
            try:
                key, child = next(iterator)
            except StopIteration:
                return
            node = self.tree.insert(parent, "end", text=str(key), values=(self.preview(child), type(child).__name__))
            self.paths[node] = path + (key,)
            if self.is_container(child) and child:
                if id(child) in ancestors:
                    self.tree.set(node, "value", "循環參照（不再展開）")
                else:
                    self.tree.insert(node, "end", text="載入中…")
                    self.pending.add(node)
        try:
            first = next(iterator)
        except StopIteration:
            return
        more = self.tree.insert(parent, "end", text="展開以顯示更多…")
        self.tree.insert(more, "end", text="下一批")
        self.pages[more] = (parent, path, value, chain((first,), iterator))

    def expand_node(self, event=None):
        node = self.tree.focus()
        if node in self.pages:
            args = self.pages.pop(node)
            self.master.after_idle(lambda: self.load_next_page(node, args))
        elif node in self.pending:
            self.pending.remove(node)
            self.tree.delete(*self.tree.get_children(node))
            path = self.paths[node]
            self.add_page(node, path, self.sol_handler.get_value(path))

    def load_next_page(self, node, args):
        if self.tree.exists(node):
            self.tree.delete(node)
            self.add_page(*args)

    def select_node(self, event=None):
        selection = self.tree.selection()
        node = selection[0] if selection else None
        if node == self.selected and self.has_unapplied_edit() and not self.busy:
            return
        if self.has_unapplied_edit() and not self.busy:
            if not self.apply_edit():
                self.tree.selection_set(self.selected)
                return
        self.selected = None
        self.value_text.configure(state="normal")
        self.value_text.delete("1.0", "end")
        self.value_text.edit_modified(False)
        self.apply_button.configure(state="disabled")
        path = self.paths.get(node)
        editable = False
        if path is not None:
            value = self.sol_handler.get_value(path)
            self.path_label.configure(text="根" + "".join(f"[{key!r}]" for key in path))
            editable = self.sol_handler.is_editable(value) and not self.busy
            if editable:
                self.selected = node
                self.value_text.insert("1.0", str(value))
                self.value_text.edit_modified(False)
                self.apply_button.configure(state="normal")
        else:
            self.path_label.configure(text="選取數值或字串欄位以編輯")
        self.value_text.configure(state="normal" if editable else "disabled")

    def apply_edit(self):
        if self.busy or self.selected is None:
            return False
        if not self.value_text.edit_modified():
            return True
        try:
            path = self.paths[self.selected]
            self.sol_handler.update_path(path, self.value_text.get("1.0", "end-1c"))
        except ValueError as error:
            messagebox.showerror("欄位格式錯誤", str(error))
            return False
        for node, path in self.paths.items():
            self.tree.set(node, "value", self.preview(self.sol_handler.get_value(path)))
        self.value_text.edit_modified(False)
        self.dirty = True
        self.status.configure(text="欄位已套用，請按「儲存修改」寫入檔案。")
        return True

    def save_changes(self):
        if self.busy or self.sol_handler.sol_instance is None:
            return
        if self.selected is not None and not self.apply_edit():
            return
        self.status.configure(text="正在編碼與儲存…")
        self.run_job("save", self.sol_handler.save)

    def close(self):
        if self.busy:
            messagebox.showinfo("處理中", "請等檔案操作完成再關閉。")
        elif self.confirm_discard():
            self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    SOLEditorApp(root)
    root.mainloop()
