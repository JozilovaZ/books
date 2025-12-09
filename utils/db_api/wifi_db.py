# wifi_db.py
from .database import Database

class WifiDatabase(Database):
    def create_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS wifi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password TEXT NOT NULL,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        self.execute(sql, commit=True)
        # agar hali parol yo'q bo'lsa default qo'yish
        row = self.execute("SELECT password FROM wifi LIMIT 1", fetchone=True)
        if not row:
            self.execute("INSERT INTO wifi (password, note) VALUES (?, ?)", parameters=("default_pass", "initial"), commit=True)

    def set_password(self, password: str, note: str = None):
        # oddiy: jadvalda bitta satr bo'lishi sharti bilan replace qilamiz
        sql = "DELETE FROM wifi"
        self.execute(sql, commit=True)
        sql = "INSERT INTO wifi (password, note) VALUES (?, ?)"
        self.execute(sql, parameters=(password, note), commit=True)

    def get_password(self):
        row = self.execute("SELECT password FROM wifi LIMIT 1", fetchone=True)
        return row[0] if row else None

    def remove_password(self):
        self.execute("DELETE FROM wifi", commit=True)
