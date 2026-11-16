"""Local username/PIN account store. Salted PBKDF2-HMAC-SHA256 verifiers only.
This is a prototype access gate, NOT face/biometric authentication."""
from __future__ import annotations
import hashlib, hmac, json, os, re, secrets, time
from pathlib import Path

PIN_ITERS, RECOVERY_ITERS = 310_000, 180_000
LOGIN_MAX_FAILS, LOGIN_LOCK_S = 5, 60
RECOVERY_MAX_FAILS, RECOVERY_LOCK_S = 5, 300
_USER_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
_PIN_RE = re.compile(r"^[0-9]{6,12}$")


def _hash(secret: str, salt: bytes, iters: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, iters).hex()


def _verifier(secret: str, iters: int) -> dict:
    salt = secrets.token_bytes(16)
    return {"salt": salt.hex(), "iters": iters, "hash": _hash(secret, salt, iters)}


def _check(secret: str, v: dict) -> bool:
    h = _hash(secret, bytes.fromhex(v["salt"]), v["iters"])
    return hmac.compare_digest(h, v["hash"])


class AccountError(Exception):
    pass


class AccountStore:
    def __init__(self, path: str = "user_data/access.json", clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"users": {}}

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        os.replace(tmp, self.path)

    @staticmethod
    def validate(username: str, pin: str):
        if not _USER_RE.match(username or ""):
            raise AccountError("Username must be 3-32 ASCII letters or digits.")
        if not _PIN_RE.match(pin or ""):
            raise AccountError("PIN must be 6-12 ASCII digits.")

    def register(self, username: str, pin: str) -> str:
        """Create account; returns the one-time recovery code (shown once, never stored)."""
        self.validate(username, pin)
        key = username.lower()
        if key in self.data["users"]:
            raise AccountError("That username already exists.")
        code = "-".join(secrets.token_hex(2).upper() for _ in range(4))
        self.data["users"][key] = {
            "username": username, "pin": _verifier(pin, PIN_ITERS),
            "recovery": _verifier(code, RECOVERY_ITERS),
            "fails": 0, "locked_until": 0, "rec_fails": 0, "rec_locked_until": 0,
        }
        self._save()
        return code

    def _lock_left(self, u: dict, field: str) -> int:
        return max(0, int(u[field] - self.clock()))

    def login(self, username: str, pin: str) -> bool:
        u = self.data["users"].get((username or "").lower())
        if not u:
            raise AccountError("Incorrect username or PIN.")
        left = self._lock_left(u, "locked_until")
        if left:
            raise AccountError(f"Too many attempts. Try again in {left} s.")
        if _check(pin or "", u["pin"]):
            u["fails"] = 0
            self._save()
            return True
        u["fails"] += 1
        if u["fails"] >= LOGIN_MAX_FAILS:
            u["fails"], u["locked_until"] = 0, self.clock() + LOGIN_LOCK_S
        self._save()
        raise AccountError("Incorrect username or PIN.")

    def recover(self, username: str, code: str, new_pin: str) -> str:
        """Reset PIN with recovery code; returns a fresh recovery code."""
        self.validate(username or "abc", new_pin)
        u = self.data["users"].get((username or "").lower())
        if not u:
            raise AccountError("Recovery failed.")
        left = self._lock_left(u, "rec_locked_until")
        if left:
            raise AccountError(f"Recovery locked. Try again in {left} s.")
        if not _check((code or "").strip().upper(), u["recovery"]):
            u["rec_fails"] += 1
            if u["rec_fails"] >= RECOVERY_MAX_FAILS:
                u["rec_fails"], u["rec_locked_until"] = 0, self.clock() + RECOVERY_LOCK_S
            self._save()
            raise AccountError("Recovery failed.")
        new_code = "-".join(secrets.token_hex(2).upper() for _ in range(4))
        u["pin"], u["recovery"] = _verifier(new_pin, PIN_ITERS), _verifier(new_code, RECOVERY_ITERS)
        u["rec_fails"] = u["fails"] = 0
        self._save()
        return new_code

    @staticmethod
    def _new_code() -> str:
        return "-".join(secrets.token_hex(2).upper() for _ in range(4))

    def change_username(self, username: str, pin: str, new_username: str) -> str:
        """Verify the PIN, then rename the account. Returns the new username."""
        self.login(username, pin)
        if not _USER_RE.match(new_username or ""):
            raise AccountError("Username must be 3-32 ASCII letters or digits.")
        old, new = username.lower(), new_username.lower()
        if new != old and new in self.data["users"]:
            raise AccountError("That username already exists.")
        u = self.data["users"].pop(old)
        u["username"] = new_username
        self.data["users"][new] = u
        self._save()
        return new_username

    def change_pin(self, username: str, pin: str, new_pin: str):
        self.login(username, pin)
        if not _PIN_RE.match(new_pin or ""):
            raise AccountError("PIN must be 6-12 ASCII digits.")
        self.data["users"][username.lower()]["pin"] = _verifier(new_pin, PIN_ITERS)
        self._save()

    def new_recovery_code(self, username: str, pin: str) -> str:
        """Verify the PIN, replace the recovery code and return the new one (shown once)."""
        self.login(username, pin)
        code = self._new_code()
        self.data["users"][username.lower()]["recovery"] = _verifier(code, RECOVERY_ITERS)
        self._save()
        return code

    def has_users(self) -> bool:
        return bool(self.data["users"])
