from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.parse import urlparse


class BrowserUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    url: str
    title: str
    text: str


class BrowserSession:
    """One isolated Playwright context; callers never interact by fixed coordinates."""

    def __init__(self, *, headless: bool = False, timeout_ms: int = 15_000, allow_private_hosts: bool = False, profile_dir: str | Path | None = None) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.allow_private_hosts = allow_private_hosts
        self.profile_dir = Path(profile_dir) if profile_dir else None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailable("Instale o extra browser para usar automação web.") from exc
        self._playwright = await async_playwright().start()
        if self.profile_dir is not None:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(self.profile_dir), headless=self.headless, channel="chrome"
            )
        else:
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
        await self._context.route("**/*", self._guard_request)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._playwright = self._browser = self._context = self._page = None

    async def navigate(self, url: str) -> PageSnapshot:
        self.validate_url(url)
        await self.validate_resolved_host(url)
        async with self._lock:
            await self.start()
            response = await self._page.goto(url, wait_until="domcontentloaded")
            self.validate_url(self._page.url, allow_private_hosts=self.allow_private_hosts)
            if response is not None and response.status >= 400:
                raise RuntimeError(f"Navegação retornou HTTP {response.status}.")
            return await self.snapshot()

    async def snapshot(self) -> PageSnapshot:
        if self._page is None:
            raise BrowserUnavailable("A sessão do navegador não foi iniciada.")
        if self._page.url != "about:blank":
            self.validate_url(self._page.url, allow_private_hosts=self.allow_private_hosts)
            await self.validate_resolved_host(self._page.url)
        return PageSnapshot(
            url=self._page.url,
            title=await self._page.title(),
            text=(await self._page.locator("body").inner_text())[:50_000],
        )

    async def click(self, *, role: str, name: str) -> PageSnapshot:
        async with self._lock:
            await self.start()
            await self._page.get_by_role(role, name=name, exact=True).click()
            await self._page.wait_for_load_state("domcontentloaded")
            return await self.snapshot()

    async def fill(self, *, label: str, value: str) -> None:
        if len(value) > 20_000:
            raise ValueError("Valor excede o limite permitido.")
        async with self._lock:
            await self.start()
            await self._page.get_by_label(label, exact=True).fill(value)

    async def send_social_message(self, *, platform: str, recipient: str, message: str) -> str:
        if not 1 <= len(message) <= 4000:
            raise ValueError("A mensagem deve ter entre 1 e 4000 caracteres.")
        platform = platform.casefold().strip()
        recipient = recipient.strip().lstrip("@").replace(" ", "")
        if not recipient:
            raise ValueError("Informe um destinatário.")
        async with self._lock:
            await self.start()
            if platform == "whatsapp":
                digits = "".join(character for character in recipient if character.isdigit())
                if len(digits) < 8:
                    raise ValueError("Para WhatsApp, informe o número com DDI e DDD.")
                url = "https://web.whatsapp.com/send?" + urlencode(
                    {"phone": digits, "text": message}
                )
                await self._page.goto(url, wait_until="domcontentloaded")
                composer = self._page.locator("footer [contenteditable='true']").last
            elif platform == "instagram":
                await self._page.goto(
                    f"https://www.instagram.com/{quote(recipient, safe='._')}/",
                    wait_until="domcontentloaded",
                )
                button = self._page.get_by_role("button", name="Message").or_(
                    self._page.get_by_role("button", name="Mensagem")
                )
                await button.first.click()
                composer = self._page.get_by_role("textbox").last
                await composer.fill(message)
            elif platform == "telegram":
                await self._page.goto(
                    f"https://web.telegram.org/k/#@{quote(recipient, safe='._')}",
                    wait_until="domcontentloaded",
                )
                composer = self._page.locator("[contenteditable='true']").last
                await composer.fill(message)
            else:
                raise ValueError("Plataforma não suportada.")
            try:
                await composer.wait_for(state="visible", timeout=self.timeout_ms)
                await composer.press("Enter")
            except Exception as exc:
                raise BrowserUnavailable(
                    f"Não consegui localizar a conversa no {platform}. Faça login no perfil "
                    "do navegador da Kiara e confirme o destinatário."
                ) from exc
            return f"Mensagem enviada pelo {platform} para {recipient}."

    @staticmethod
    def validate_url(url: str, *, allow_private_hosts: bool = False) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Apenas URLs HTTPS sem credenciais são permitidas.")
        hostname = parsed.hostname.casefold().rstrip(".")
        if not allow_private_hosts and hostname in {"localhost", "localhost.localdomain"}:
            raise ValueError("Destinos locais não são permitidos.")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return
        if not allow_private_hosts and not address.is_global:
            raise ValueError("Endereços privados, loopback e link-local não são permitidos.")

    async def validate_resolved_host(self, url: str) -> None:
        if self.allow_private_hosts:
            return
        hostname = urlparse(url).hostname
        if hostname is None:
            raise ValueError("URL sem hostname.")
        addresses = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        if not addresses:
            raise ValueError("Hostname não pôde ser resolvido.")
        for address in addresses:
            resolved = ipaddress.ip_address(address[4][0])
            if not resolved.is_global:
                raise ValueError("Hostname resolve para endereço não público.")

    async def _guard_request(self, route, request) -> None:
        try:
            self.validate_url(request.url, allow_private_hosts=self.allow_private_hosts)
            await self.validate_resolved_host(request.url)
        except (OSError, ValueError):
            await route.abort("blockedbyclient")
            return
        await route.continue_()
