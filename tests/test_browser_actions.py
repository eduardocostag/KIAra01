from app.browser.session import PageSnapshot
from app.models import PermissionLevel
from app.tools.browser import BrowserClickTool, BrowserFillTool, BrowserReadTool


class _Browser:
    async def fill(self, *, label: str, value: str) -> None:
        self.filled = (label, value)

    async def click(self, *, role: str, name: str) -> PageSnapshot:
        self.clicked = (role, name)
        return PageSnapshot("https://example.com/ok", "Concluído", "Tudo certo")

    async def snapshot(self) -> PageSnapshot:
        return PageSnapshot("https://example.com", "Exemplo", "Conteúdo visível")


async def test_browser_fill_does_not_submit_and_redacts_value() -> None:
    browser = _Browser()
    tool = BrowserFillTool(browser)
    result = await tool.execute(label="Pesquisa", value="assunto privado")
    assert result.success
    assert browser.filled == ("Pesquisa", "assunto privado")
    assert tool.permission_level == PermissionLevel.SAFE_ACTION
    assert "privado" not in str(
        tool.audit_parameters({"label": "Pesquisa", "value": "assunto privado"})
    )


async def test_browser_click_remains_confirmed_and_read_is_read_only() -> None:
    browser = _Browser()
    click = BrowserClickTool(browser)
    read = BrowserReadTool(browser)
    assert click.permission_level == PermissionLevel.SENSITIVE_ACTION
    assert read.permission_level == PermissionLevel.READ_ONLY
    assert (await click.execute(role="button", name="Continuar")).success
    page = await read.execute()
    assert "Conteúdo visível" in page.output
