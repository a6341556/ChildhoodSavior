import tkinter as tk
from tkinter import filedialog, ttk, messagebox
# 假設 sol_editor.py 已經被放在同一個目錄
from sol_editor import SOLFile
import os

class SOLEditorApp:
    def __init__(self, master):
        self.master = master
        master.title("Flash LSO 存檔編輯器")
        
        self.sol_handler = SOLFile()
        self.entries = {}  # 用於儲存 Key 和 Value 的輸入框 widgets

        # 框架設置
        self.control_frame = ttk.Frame(master, padding="10")
        self.control_frame.pack(fill='x')

        self.data_frame = ttk.Frame(master, padding="10")
        self.data_frame.pack(fill='both', expand=True)

        # 1. 控制區
        self.open_button = ttk.Button(self.control_frame, text="開啟 .sol 檔案", command=self.open_file)
        self.open_button.pack(side='left', padx=5)

        self.save_button = ttk.Button(self.control_frame, text="儲存修改", command=self.save_changes, state=tk.DISABLED)
        self.save_button.pack(side='right', padx=5)

        self.filepath_label = ttk.Label(self.control_frame, text="請點擊 '開啟 .sol 檔案'")
        self.filepath_label.pack(side='left', padx=10)

        # 2. 數據顯示區 (使用 Canvas 和 Scrollbar)
        self.canvas = tk.Canvas(self.data_frame, borderwidth=0)
        self.data_container = ttk.Frame(self.canvas)
        self.vscrollbar = ttk.Scrollbar(self.data_frame, orient="vertical", command=self.canvas.yview)
        
        self.canvas.configure(yscrollcommand=self.vscrollbar.set)

        self.vscrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.data_container, anchor="nw")

        self.data_container.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)


    def on_frame_configure(self, event):
        """當內部 Frame 大小改變時，調整 Canvas 的捲軸範圍。"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """當 Canvas 大小改變時，調整內部 Frame 的寬度。"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)


    def open_file(self):
        """彈出檔案選擇對話框，讀取並顯示數據。"""
        filepath = filedialog.askopenfilename(
            defaultextension=".sol",
            filetypes=[("Flash Shared Object Files", "*.sol")],
            title="選擇要編輯的 .sol 檔案"
        )
        if not filepath:
            return

        try:
            self.sol_handler.load(filepath)
            self.filepath_label.config(text=f"載入成功: {os.path.basename(filepath)}")
            self.save_button.config(state=tk.NORMAL)
            self.display_data(self.sol_handler.get_data())
        except Exception as e:
            messagebox.showerror("載入錯誤", f"無法載入檔案: {e}")
            self.filepath_label.config(text="載入失敗")
            self.save_button.config(state=tk.DISABLED)

    def display_data(self, data):
        """將數據字典中的 Key-Value 條列在 UI 上。"""
        # 清除舊的 Widgets
        for widget in self.data_container.winfo_children():
            widget.destroy()
        self.entries = {}
        
        row_num = 0
        
        # 創建表頭
        ttk.Label(self.data_container, text="Key", font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Label(self.data_container, text="Value (可修改)", font=('Arial', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ttk.Label(self.data_container, text="類型", font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=5, pady=5, sticky='w')
        
        for key, value in data.items():
            row_num += 1
            
            # Key 標籤
            ttk.Label(self.data_container, text=key, foreground='blue').grid(row=row_num, column=0, padx=5, pady=2, sticky='w')

            # Value 輸入框
            entry = ttk.Entry(self.data_container, width=50)
            entry.insert(0, str(value))
            entry.grid(row=row_num, column=1, padx=5, pady=2, sticky='we')
            self.entries[key] = entry  # 儲存輸入框的引用

            # 類型標籤
            ttk.Label(self.data_container, text=f"({type(value).__name__})").grid(row=row_num, column=2, padx=5, pady=2, sticky='w')

        # 讓容器適應內容大小
        self.data_container.update_idletasks()
        self.on_frame_configure(None)

    def save_changes(self):
        """讀取所有輸入框的新值，更新 SOLFile 實例，並寫入檔案。"""
        try:
            # 1. 更新內存數據
            for key, entry in self.entries.items():
                new_value = entry.get()
                self.sol_handler.update_value(key, new_value)
            
            # 2. 寫入檔案
            self.sol_handler.save()
            
            messagebox.showinfo("儲存成功", f"檔案已成功儲存至:\n{self.sol_handler.filepath}")

        except Exception as e:
            messagebox.showerror("儲存錯誤", f"儲存失敗:\n{e}")

if __name__ == '__main__':
    # 執行前請確保 sol_editor.py 檔案存在！
    root = tk.Tk()
    app = SOLEditorApp(root)
    root.mainloop()