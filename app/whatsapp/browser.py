from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

from .store import normalize_phone


class BrowserNotReady(RuntimeError):
    pass


class WhatsAppBrowser:
    """Only visible UI interactions. No injected WhatsApp runtime or private API."""

    def __init__(self, profile_dir):
        self.profile_dir = Path(profile_dir)
        self.runtime = self.context = self.page = None
        self.phone = None

    async def start(self):
        from playwright.async_api import async_playwright
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.runtime = await async_playwright().start()
        self.context = await self.runtime.chromium.launch_persistent_context(
            str(self.profile_dir), headless=False, viewport={"width": 1280, "height": 900},
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(12000)
        await self.page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")

    async def close(self):
        if self.context:
            await self.context.close()
        if self.runtime:
            await self.runtime.stop()

    async def status(self):
        if not self.page or self.page.is_closed():
            return "offline"
        if not self.page.url.startswith("https://web.whatsapp.com/"):
            return "offline"
        return "ready" if await self.page.locator("#pane-side").count() else "qr"

    async def open_chat(self, phone):
        phone = normalize_phone(phone)
        if await self.status() != "ready":
            raise BrowserNotReady("Faça a leitura do QR Code no navegador aberto.")
        if self.phone != phone:
            await self.page.goto("https://web.whatsapp.com/send?" + urlencode({"phone": phone}), wait_until="domcontentloaded")
            self.phone = None
        await self.page.locator("#main footer [contenteditable='true'][role='textbox']").wait_for(state="visible", timeout=25000)
        await self.verify_identity(phone)
        self.phone = phone

    async def verify_identity(self, phone):
        # A name alone is insufficient. Existing DOM message IDs encode the actual chat JID.
        ids = await self.page.locator("#main [data-id]").evaluate_all("els => els.map(el => el.getAttribute('data-id'))")
        peers = set()
        for identifier in ids:
            match = re.match(r"(?:true|false)_([0-9]+)@(?:c\.us|s\.whatsapp\.net)_", identifier or "")
            if match:
                peers.add(match[1])
        if peers == {phone}:
            return
        # Some clients use opaque LIDs; verify the phone in the contact-info panel instead.
        header = self.page.locator("#main header")
        await header.click()
        try:
            panel = self.page.locator("[data-testid='drawer-right'], [data-testid='contact-info-drawer']").first
            await panel.wait_for(state="visible", timeout=5000)
            content = await panel.inner_text()
            phones = {normalize_phone(m) for m in re.findall(r"\+[0-9][0-9 ()-]{7,25}[0-9]", content)}
            if phones != {phone}:
                raise BrowserNotReady("Não foi possível confirmar o telefone deste chat; envio suspenso.")
        except Exception as exc:
            raise BrowserNotReady("Identidade do chat não confirmada. Nenhuma mensagem enviada.") from exc
        finally:
            await self.page.keyboard.press("Escape")

    async def read(self, phone):
        await self.open_chat(phone)
        return await self.page.locator("#main [data-id]").evaluate_all("""els => {
          const seen = new Set();
          return els.flatMap(el => {
            const id = el.getAttribute('data-id');
            if (!id || seen.has(id)) return [];
            const bubble = el.matches('.message-in,.message-out') ? el : el.querySelector('.message-in,.message-out') || el.closest('.message-in,.message-out');
            if (!bubble) return [];
            seen.add(id);
            const texts = bubble.querySelectorAll('.selectable-text.copyable-text');
            const text = Array.from(texts).map(x => x.innerText).join('\n').trim();
            return [{id, direction:bubble.classList.contains('message-out')?'out':'in',text}];
          });
        }""")

    async def scan_visible_conversations(self, limit=30):
        if await self.status() != "ready":
            raise BrowserNotReady("Faça a leitura do QR Code no navegador aberto.")
        cells = self.page.locator("#pane-side [data-testid='cell-frame-container']")
        count = min(await cells.count(), limit)
        if count == 0:
            raise BrowserNotReady("Não encontrei conversas carregadas na lista do WhatsApp Web.")
        labels = await cells.evaluate_all("""els => els.slice(0, 30).map(el => {
          const title = el.querySelector('[data-testid="cell-frame-title"]');
          return title?.innerText?.trim() || el.getAttribute('aria-label') || '';
        })""")
        conversations = []
        skipped = 0
        for index in range(count):
            cell = cells.nth(index)
            if not await cell.is_visible():
                skipped += 1
                continue
            await cell.click()
            await self.page.locator("#main footer [contenteditable='true'][role='textbox']").wait_for(state="visible")
            await self.page.wait_for_timeout(250)
            messages = await self.page.locator("#main [data-id]").evaluate_all("""els => {
              const seen = new Set();
              return els.flatMap(el => {
                const id = el.getAttribute('data-id');
                if (!id || seen.has(id)) return [];
                const bubble = el.matches('.message-in,.message-out') ? el : el.querySelector('.message-in,.message-out') || el.closest('.message-in,.message-out');
                if (!bubble) return [];
                seen.add(id);
                const text = Array.from(bubble.querySelectorAll('.selectable-text.copyable-text')).map(x => x.innerText).join('\\n').trim();
                return [{id, direction:bubble.classList.contains('message-out')?'out':'in',text}];
              });
            }""")
            inbound = [message for message in messages if message["direction"] == "in" and message["text"]]
            if not inbound:
                skipped += 1
                continue
            heading = self.page.locator("#main header span[dir='auto']").first
            name = await heading.inner_text() if await heading.count() else ""
            name = name.strip() or (labels[index].strip() if index < len(labels) else "")
            phone = await self._active_chat_phone(messages)
            if not phone:
                skipped += 1
                continue
            conversations.append({"phone": phone, "name": name[:160] or phone, "messages": messages[-20:]})
        return {"conversations": conversations, "scanned": count, "skipped": skipped}

    async def _active_chat_phone(self, messages):
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        peers = set()
        for message in messages:
            match = re.match(r"(?:true|false)_([0-9]+)@(?:c\.us|s\.whatsapp\.net)_", message["id"])
            if match:
                peers.add(match[1])
        if len(peers) == 1:
            return next(iter(peers))
        header = self.page.locator("#main header")
        await header.click()
        try:
            panel = self.page.locator("[data-testid='drawer-right'], [data-testid='contact-info-drawer']").first
            await panel.wait_for(state="visible", timeout=5000)
            content = await panel.inner_text()
            phones = {
                digits for match in re.findall(r"\+[0-9][0-9 ()-]{7,25}[0-9]", content)
                if len(digits := re.sub(r"\D", "", match)) in range(8, 16)
            }
            return next(iter(phones)) if len(phones) == 1 else None
        except PlaywrightTimeoutError:
            return None
        finally:
            await self.page.keyboard.press("Escape")

    async def send(self, phone, text, expected_ids=None):
        await self.open_chat(phone)
        before = {item["id"] for item in await self.read(phone)}
        if expected_ids is not None and before != set(expected_ids):
            raise BrowserNotReady("Conversa mudou antes do envio; revisão necessária.")
        composer = self.page.locator("#main footer [contenteditable='true'][role='textbox']").first
        if (await composer.inner_text()).strip():
            raise BrowserNotReady("Há um rascunho humano no chat. Envio suspenso.")
        await composer.fill(text)
        await self.verify_identity(phone)
        current = {item["id"] for item in await self.read(phone)}
        if current != before:
            await composer.fill("")
            raise BrowserNotReady("Nova mensagem antes do envio; envio cancelado.")
        await composer.press("Enter")
        # Only a new outgoing DOM bubble confirms the UI accepted the send; not delivery/read.
        import asyncio
        for _ in range(15):
            await asyncio.sleep(0.5)
            messages = await self.read(phone)
            for message in messages:
                if message["id"] not in before and message["direction"] == "out" and message["text"].strip() == text.strip():
                    return message["id"]
        return False


class ChromeExtensionBrowser:
    """Typed UI commands through the user's already-authenticated Chrome tab."""

    read_only = False

    def __init__(self, bridge):
        self.bridge = bridge

    async def start(self):
        return None

    async def close(self):
        return None

    async def status(self):
        return "ready" if self.bridge.online() else "offline"

    async def wait_for_analysis_scan(self, job_id, limit):
        return await self.bridge.wait_for_scan(job_id, limit)

    async def read(self, phone):
        result = await self.bridge.execute("read", normalize_phone(phone))
        return result["messages"]

    async def send(self, phone, text, expected_ids=None):
        if expected_ids is None:
            raise BrowserNotReady("Envio requer uma leitura atual da conversa.")
        result = await self.bridge.execute("send", normalize_phone(phone), text=text, expected_ids=expected_ids)
        return result["message_id"]
