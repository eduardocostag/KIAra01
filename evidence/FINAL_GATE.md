# Kiara — gate final local

Data: 2026-08-24 (America/Sao_Paulo)

## Resultado

- Testes: 134 aprovados, 4 ignorados por dependerem de sessão interativa/hardware real.
- Ruff: aprovado, sem violações.
- Diagnóstico: Windows, PowerShell, configuração, diretório de auditoria, captura, microfone, faster-whisper e Windows SAPI disponíveis.
- Executável portátil: iniciado e mantido em execução durante smoke test.
- Instalador: instalação silenciosa aprovada; aplicativo instalado iniciou e permaneceu em execução durante 5 segundos; desinstalação retornou código 0 e removeu a pasta de teste.
- AppSec: nenhum achado P0/P1 aberto na revisão final.

## Artefatos

### dist/Kiara.exe

- Tamanho: 185649773 bytes
- SHA-256: `B987D89CFF01CC11CA3CFD07234977B794428A911F9B3D041D0D1BD07FD06606`
- Authenticode: `NotSigned`

### dist/installer/Kiara-Setup-0.1.0.exe

- Tamanho: 185685996 bytes
- SHA-256: `645E249A535EE32C1D4273617E073A083A90ACAB6EF8C8CAE0F6A24C249D9D6E`
- Authenticode: `NotSigned`

## Evidência associada

- `evidence/pytest-final.xml`
- `evidence/playwright-real.png`
- `evidence/playwright-real.txt`
- `evidence/windows-integration.xml`

## Limites para release pública

1. Assinar o executável e o instalador com certificado Authenticode confiável.
2. Executar os quatro testes interativos em uma sessão Windows destravada com janela em primeiro plano e microfone real.
3. Validar o provedor multimodal externo com credenciais reais e orçamento autorizado.
4. Validar integrações Graph/Gmail somente quando as respectivas credenciais forem fornecidas.

O estado atual é adequado para beta local controlada. Não é declarado como release pública assinada.
