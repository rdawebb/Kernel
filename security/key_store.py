from cryptography.fernet import Fernet
from pathlib import Path

class KeyStore:
    def __init__(self):
        key_file = Path.home() / ".tui_mail" / "keys" / "master.key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if not key_file.exists():
            key_file.write_bytes(Fernet.generate_key())
        self.cipher = Fernet(key_file.read_bytes())

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self.cipher.decrypt(value.encode()).decode()
        except Exception:
            return ""
