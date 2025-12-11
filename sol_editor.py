import os
from pyamf.sol import decode, encode, SOL # 繼承自 dict 的 SOL 類
from pyamf import util

class SOLFile:
    """
    Local Shared Object (LSO) 檔案的物件導向封裝。
    處理檔案讀取、數據存儲和寫入。
    """
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.sol_instance = None
        self.data = {}
        if filepath:
            self.load()

    def load(self, filepath=None):
        """
        讀取指定路徑的 .sol 檔案，並將數據解碼到 sol_instance 和 data 字典中。
        """
        if filepath:
            self.filepath = filepath
            
        if not self.filepath or not os.path.exists(self.filepath):
            raise FileNotFoundError(f"找不到檔案: {self.filepath}")

        with open(self.filepath, 'rb') as f:
            content = f.read()

        # 1. 解碼 (得到 Tuple: sol_name, data_dict)
        sol_name, data_dict = decode(content)
        
        # 2. 封裝成 SOL 實例
        self.sol_instance = SOL(sol_name)
        self.sol_instance.update(data_dict)
        self.data = dict(self.sol_instance) # 儲存一個可讀的副本
        
        return self.data

    def get_data(self):
        """回傳所有的 Key-Value 數據字典。"""
        return self.data

    def update_value(self, key, new_value):
        """
        更新內存數據，並同時更新 SOL 實例。
        """
        if key not in self.data:
            raise KeyError(f"Key '{key}' 不存在於檔案數據中。")
        
        # 保持類型一致性 (UI 處理時可能需要更複雜的轉換)
        old_value = self.data[key]
        value_type = type(old_value)

        try:
            # 嘗試轉換新值到舊值的類型
            if value_type is int:
                converted_value = int(new_value)
            elif value_type is float:
                converted_value = float(new_value)
            else:
                converted_value = new_value
        except ValueError:
            raise ValueError(f"無法將 '{new_value}' 轉換為 Key '{key}' 的原始類型 {value_type.__name__}。")

        # 更新內部數據和 SOL 實例
        self.data[key] = converted_value
        self.sol_instance[key] = converted_value
        
        return True

    def save(self):
        """
        將修改後的 SOL 實例編碼並安全地寫入檔案。
        """
        if not self.sol_instance:
            raise ValueError("無數據可儲存，請先載入檔案。")

        # 1. 編碼 (encode(name, values) 回傳 Stream)
        stream = encode(self.sol_instance.name, self.sol_instance)
        output_bytes = stream.getvalue() # 取得 bytes
        
        # 2. 安全寫入流程 (使用臨時檔案)
        temp_path = self.filepath + ".tmp"
        
        try:
            # 寫入臨時檔案
            with open(temp_path, 'wb') as f:
                f.write(output_bytes)
                
            # 替換原檔案
            if os.path.exists(self.filepath):
                os.remove(self.filepath)
            os.rename(temp_path, self.filepath)
            
            return True

        except Exception as e:
            # 失敗時嘗試清除臨時檔案
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise IOError(f"檔案寫入失敗: {e}")