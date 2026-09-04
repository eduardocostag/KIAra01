from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse


class BrowserUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    url: str
    title: str
    text: str


class BrowserSession:
    """One isolated Playwright context; callers never interact by fixed coordinates."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 15_000,
        allow_private_hosts: bool = False,
        profile_dir: str | Path | None = None,
    ) -> None:
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
        self._page = (
            self._context.pages[0] if self._context.pages else await self._context.new_page()
        )
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

    async def search_google_maps_businesses(
        self, *, query: str, limit: int
    ) -> list[dict[str, str]]:
        """Read public business fields from individual Google Maps profiles."""
        async with self._lock:
            await self.start()
            url = f"https://www.google.com/maps/search/{quote(query, safe='')}"
            await self._page.goto(url, wait_until="commit")
            await self._page.wait_for_timeout(2500)
            links: list[str] = []
            stagnant = 0
            while len(links) < limit * 2 and stagnant < 4:
                current = await self._page.locator('a[href*="/maps/place/"]').evaluate_all(
                    "els => [...new Set(els.map(e => e.href))]"
                )
                previous = len(links)
                links = list(dict.fromkeys([*links, *current]))
                stagnant = stagnant + 1 if len(links) == previous else 0
                feed = self._page.locator('[role="feed"]')
                if await feed.count():
                    await feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
                    await self._page.wait_for_timeout(900)
                else:
                    break
            businesses: list[dict[str, str]] = []
            for profile_url in links[: limit * 2]:
                try:
                    await self._page.goto(profile_url, wait_until="domcontentloaded")
                    await self._page.wait_for_timeout(900)
                    name = await self._first_text('h1, [role="main"] h1')
                    phone = await self._maps_field('button[data-item-id^="phone:tel:"]')
                    address = await self._maps_field('button[data-item-id="address"]')
                    website = await self._maps_website()
                    rating, review_count = await self._maps_reputation()
                    whatsapp = ""
                    if phone and not website and await self._whatsapp_number_is_valid(phone):
                        whatsapp = phone
                    if name and phone:
                        businesses.append(
                            {
                                "name": name,
                                "phone": phone,
                                "whatsapp": whatsapp,
                                "address": address,
                                "website": website,
                                "maps_url": profile_url,
                                "rating": rating,
                                "review_count": review_count,
                            }
                        )
                    if len(businesses) >= limit:
                        break
                except Exception:  # noqa: BLE001,S112 - one bad profile must not abort the batch
                    continue
            return businesses

    async def search_public_consumer_intent(
        self, *, query: str, location: str, limit: int
    ) -> list[dict[str, str]]:
        """Descobre publicações indexadas; não abre perfis nem coleta contatos pessoais."""
        platforms = (
            ("instagram", "instagram.com"),
            ("facebook", "facebook.com"),
            ("tiktok", "tiktok.com"),
            ("linkedin", "linkedin.com"),
        )
        phrases = '("procuro" OR "preciso" OR "indicação" OR "qual o valor")'
        per_platform = max(2, min(10, (limit + len(platforms) - 1) // len(platforms)))
        async with self._lock:
            await self.start()
            async def search_platform(platform: str, domain: str) -> list[dict[str, str]]:
                platform_results: list[dict[str, str]] = []
                search = f'site:{domain} {phrases} "{query}" "{location}"'
                page = await self._context.new_page()
                page.set_default_timeout(min(self.timeout_ms, 10_000))
                try:
                    await page.goto(
                        f"https://www.google.com/search?q={quote(search)}",
                        wait_until="domcontentloaded",
                        timeout=min(self.timeout_ms, 10_000),
                    )
                    await page.wait_for_timeout(900)
                    results = await page.locator("a:has(h3)").evaluate_all(
                        """els => els.slice(0, 20).map(a => ({
                          url: a.href,
                          title: (a.querySelector('h3')?.innerText || '').trim(),
                          excerpt: (a.closest('[data-snhf]')?.innerText ||
                                    a.parentElement?.parentElement?.innerText || '').trim()
                        }))"""
                    )
                    for item in results:
                        url = self._unwrap_google_result(str(item.get("url", "")))
                        host = (urlparse(url).hostname or "").casefold()
                        if domain not in host:
                            continue
                        platform_results.append({
                            "platform": platform,
                            "url": url,
                            "title": str(item.get("title", ""))[:500],
                            "excerpt": str(item.get("excerpt", ""))[:2000],
                        })
                        if len(platform_results) >= per_platform:
                            break
                except Exception:  # noqa: BLE001,S110 - one platform cannot abort the batch
                    pass
                finally:
                    await page.close()
                return platform_results

            batches = await asyncio.gather(
                *(search_platform(platform, domain) for platform, domain in platforms)
            )
        return [item for batch in batches for item in batch][:limit]

    @staticmethod
    def _unwrap_google_result(url: str) -> str:
        parsed = urlparse(url)
        if parsed.hostname and parsed.hostname.endswith("google.com") and parsed.path == "/url":
            target = parse_qs(parsed.query).get("q", [""])[0]
            return unquote(target)
        return url

    async def _whatsapp_number_is_valid(self, phone: str) -> bool:
        digits = "".join(character for character in phone if character.isdigit())
        if len(digits) in {10, 11}:
            digits = "55" + digits
        if len(digits) < 12:
            return False
        await self._page.goto(f"https://wa.me/{digits}", wait_until="domcontentloaded")
        await self._page.wait_for_timeout(700)
        text = (await self._page.locator("body").inner_text()).casefold()
        invalid = ("inválido", "invalid", "não está no whatsapp", "isn't on whatsapp")
        valid = ("iniciar conversa", "continue to chat", "conversar", "chat on whatsapp")
        return not any(marker in text for marker in invalid) and any(
            marker in text for marker in valid
        )

    async def _first_text(self, selector: str) -> str:
        locator = self._page.locator(selector).first
        return (await locator.inner_text()).strip() if await locator.count() else ""

    async def _maps_field(self, selector: str) -> str:
        locator = self._page.locator(selector).first
        if not await locator.count():
            return ""
        label = (await locator.get_attribute("aria-label") or "").strip()
        text = (await locator.inner_text()).strip()
        value = label or text
        return value.split(":", 1)[-1].strip() if ":" in value else value

    async def _maps_website(self) -> str:
        locator = self._page.locator(
            'a[data-item-id="authority"], a[aria-label^="Site:"], a[aria-label^="Website:"]'
        ).first
        if not await locator.count():
            return ""
        return (await locator.get_attribute("href") or "").strip()

    async def _maps_reputation(self) -> tuple[float, int]:
        """Read rating and review volume without treating either as guaranteed demand."""
        rating = 0.0
        review_count = 0
        rating_locator = self._page.locator(
            '[role="img"][aria-label*="estrela"], [role="img"][aria-label*="star"]'
        ).first
        if await rating_locator.count():
            label = (await rating_locator.get_attribute("aria-label") or "").replace(",", ".")
            match = re.search(r"([0-5](?:\.\d)?)", label)
            if match:
                rating = float(match.group(1))
        reviews_locator = self._page.locator(
            'button[aria-label*="avaliaç"], button[aria-label*="review"]'
        ).first
        if await reviews_locator.count():
            label = await reviews_locator.get_attribute("aria-label") or ""
            digits = "".join(character for character in label if character.isdigit())
            if digits:
                review_count = int(digits)
        return rating, review_count

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
                if len(digits) >= 8:
                    url = "https://web.whatsapp.com/send?" + urlencode(
                        {"phone": digits, "text": message}
                    )
                    await self._page.goto(url, wait_until="domcontentloaded")
                else:
                    await self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
                    search = self._page.get_by_role("textbox").first
                    await search.fill(recipient)
                    await search.press("Enter")
                composer = self._page.locator("footer [contenteditable='true']").last
                if len(digits) < 8:
                    await composer.fill(message)
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
