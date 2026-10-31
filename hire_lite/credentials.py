"""Password lookup: environment variable first, then the OS keychain."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess


def get_password(cfg: dict) -> str:
    s = cfg["sender"]
    pw = os.environ.get(s.get("password_env") or "HL_SMTP_PASSWORD", "")
    user = s.get("username") or cfg["profile"]["email"]
    service = s.get("keyring_service") or "hire-lite-smtp"
    if not pw:
        try:
            import keyring  # type: ignore

            pw = keyring.get_password(service, user) or ""
        except Exception:
            pw = ""
    if not pw and platform.system() == "Darwin" and shutil.which("security"):
        # macOS Keychain without the keyring package: `security add-generic-password -s <service> -a <user> -w`
        res = subprocess.run(["security", "find-generic-password", "-s", service, "-a", user, "-w"],
                             capture_output=True, text=True)
        pw = res.stdout.strip()
    # Gmail shows app passwords in groups of four; spaces are not part of the secret.
    return pw.replace(" ", "")
