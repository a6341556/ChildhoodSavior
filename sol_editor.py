import os
import tempfile

from pyamf.sol import decode, encode, SOL


class SOLFile:
    """保留 AMF 容器與型別，透過路徑修改巢狀欄位。"""

    def __init__(self, filepath=None):
        self.filepath = None
        self.sol_instance = None
        self.data = {}
        self.encoding = 0
        if filepath:
            self.load(filepath)

    def load(self, filepath=None):
        path = filepath or self.filepath
        if not path:
            raise ValueError("請先選擇檔案。")
        path = os.fspath(path)
        with open(path, "rb") as source:
            content = source.read()
        name, values = decode(content)
        name_length = int.from_bytes(content[16:18], "big")
        encoding = content[21 + name_length]
        instance = SOL(name)
        instance.update(values)
        self.filepath = path
        self.sol_instance = instance
        self.data = instance
        self.encoding = encoding
        return self.data

    def get_data(self):
        return self.data

    def get_value(self, path):
        value = self.data
        for key in path:
            value = value[key]
        return value

    @staticmethod
    def is_editable(value):
        return type(value) in (str, bool, int, float)

    def update_path(self, path, text):
        if not path:
            raise ValueError("不能取代根物件。")
        parent = self.get_value(path[:-1])
        old = parent[path[-1]]
        if not self.is_editable(old):
            raise ValueError("請展開容器以修改內部欄位；此型別只供瀏覽。")
        try:
            if type(old) is bool:
                converted = {"true": True, "false": False, "1": True, "0": False}[text.strip().lower()]
            else:
                converted = type(old)(text)
        except (ValueError, KeyError) as error:
            raise ValueError(f"請輸入有效的 {type(old).__name__} 值。") from error
        parent[path[-1]] = converted
        return True

    def update_value(self, key, new_value):
        return self.update_path((key,), new_value)

    def save(self):
        if self.sol_instance is None:
            raise ValueError("請先載入檔案。")
        output = encode(self.sol_instance.name, self.sol_instance, encoding=self.encoding)
        directory = os.path.dirname(os.path.abspath(self.filepath))
        fd, temporary = tempfile.mkstemp(prefix=".sol-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "wb") as target:
                target.write(output.getvalue())
            os.replace(temporary, self.filepath)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        return True
