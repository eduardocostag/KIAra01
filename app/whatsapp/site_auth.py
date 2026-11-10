"""Interactive sign-in to Kiara; credentials and refresh tokens stay in memory."""
from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SiteLoginError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SiteSession:
    """Supabase password session, refreshed before its access token expires."""

    def __init__(self, url: str, public_key: str, *, clock=time.time, opener=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise SiteLoginError("SUPABASE_URL precisa ser uma URL HTTPS sem credenciais.")
        if not public_key.strip():
            raise SiteLoginError("Configure a chave pública do Supabase.")
        self.url = url.rstrip("/")
        self.public_key = public_key.strip()
        self.clock = clock
        self.opener = opener or build_opener(_NoRedirect())
        self._access = ""
        self._refresh = ""
        self._expires = 0.0

    def _exchange(self, grant: str, body: dict[str, str]) -> None:
        request = Request(
            self.url + "/auth/v1/token?grant_type=" + grant,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "apikey": self.public_key},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("oversized response")
            payload = json.loads(raw)
            access = payload.get("access_token")
            refresh = payload.get("refresh_token")
            lifetime = int(payload.get("expires_in", 0))
            if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh or lifetime <= 0:
                raise ValueError("invalid session")
        except (HTTPError, URLError, OSError, ValueError, TypeError, AttributeError) as exc:
            # Never surface provider bodies, passwords, or token-bearing requests.
            raise SiteLoginError("Não foi possível autenticar no site. Confira o login, a conexão e eventuais requisitos de MFA/CAPTCHA.") from None
        self._access, self._refresh = access, refresh
        self._expires = self.clock() + lifetime

    def login(self, email: str, password: str) -> None:
        self._exchange("password", {"email": email.strip(), "password": password})

    def token(self) -> str:
        if not self._refresh:
            raise SiteLoginError("Entre na conta da Kiara antes de sincronizar.")
        if self.clock() >= self._expires - 60:
            self._exchange("refresh_token", {"refresh_token": self._refresh})
        return self._access


def interactive_site_session() -> SiteSession:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    session = SiteSession(url, key)
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("Conectar à Kiara")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.columnconfigure(0, weight=1)

    tk.Label(root, text="Entre na sua conta Kiara", font=("Segoe UI", 13, "bold")).grid(
        row=0, column=0, padx=24, pady=(22, 6), sticky="w"
    )
    tk.Label(root, text="A senha é usada somente para conectar e não será salva.").grid(
        row=1, column=0, padx=24, pady=(0, 16), sticky="w"
    )
    tk.Label(root, text="E-mail").grid(row=2, column=0, padx=24, sticky="w")
    email_input = tk.Entry(root, width=42)
    email_input.grid(row=3, column=0, padx=24, pady=(4, 12), sticky="ew")
    tk.Label(root, text="Senha").grid(row=4, column=0, padx=24, sticky="w")
    password_input = tk.Entry(root, width=42, show="*")
    password_input.grid(row=5, column=0, padx=24, pady=(4, 16), sticky="ew")
    result: dict[str, SiteSession] = {}

    def connect():
        password = password_input.get()
        try:
            session.login(email_input.get(), password)
            result["session"] = session
            password_input.delete(0, tk.END)
            root.destroy()
        except SiteLoginError as exc:
            password_input.delete(0, tk.END)
            messagebox.showerror("Não foi possível conectar", str(exc), parent=root)

    def cancel():
        password_input.delete(0, tk.END)
        root.destroy()

    buttons = tk.Frame(root)
    buttons.grid(row=6, column=0, padx=24, pady=(0, 22), sticky="e")
    tk.Button(buttons, text="Cancelar", command=cancel).pack(side="right", padx=(8, 0))
    tk.Button(buttons, text="Conectar", command=connect, default="active").pack(side="right")
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Return>", lambda _event: connect())
    root.bind("<Escape>", lambda _event: cancel())
    email_input.focus_set()
    root.mainloop()

    if "session" not in result:
        raise SiteLoginError("Conexão cancelada.")
    return result["session"]
