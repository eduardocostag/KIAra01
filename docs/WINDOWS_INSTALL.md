# Build, instalação e release no Windows

## Artefatos

O pipeline produz `dist\Kiara.exe` (PyInstaller) e
`dist\installer\Kiara-Setup-<versão>.exe` (Inno Setup por usuário).

O instalador possui identidade (`AppId`) estável. Executar uma versão mais nova sobre uma
existente faz upgrade no mesmo diretório e preserva os dados em `%LOCALAPPDATA%\Kiara`.
A entrada **Kiara** em Aplicativos Instalados executa a desinstalação. Dados pessoais
permanecem por padrão para evitar perda acidental e podem ser removidos separadamente.

## Pré-requisitos

- Python 3.12 e o ambiente `.venv`;
- dependências `dev`, `ui` e `release`;
- Inno Setup 6 (`ISCC.exe`);
- Windows SDK (`signtool.exe`) e certificado de code signing para uma release pública.

```powershell
python -m pip install -e ".[dev,ui,release]"
```

## Build local não assinado

Este fluxo é explícito e serve somente para desenvolvimento interno:

```powershell
$env:KIARA_ALLOW_UNSIGNED_DEV_BUILD = "1"
.\scripts\build-windows.ps1
.\scripts\build-installer.ps1 -AllowUnsignedDev
```

Ele não instala o aplicativo, não executa o instalador e não altera o Registro. O artefato
resultante não deve ser publicado.

## Release assinada

O certificado deve ficar em armazenamento seguro e acessível à identidade do CI. Nunca
adicione PFX, senha ou chave privada ao repositório. O script assina primeiro o payload e,
depois da compilação, o instalador, ambos com SHA-256 e timestamp RFC 3161:

```powershell
.\scripts\build-windows.ps1
.\scripts\build-installer.ps1 `
  -Version 1.0.0 `
  -CertificateThumbprint $env:KIARA_SIGNING_CERT_THUMBPRINT `
  -TimestampUrl "http://timestamp.digicert.com"
```

Sem `-AllowUnsignedDev`, qualquer assinatura ausente ou inválida bloqueia a release. Antes
de distribuir, verifique em uma máquina limpa:

```powershell
Get-AuthenticodeSignature .\dist\Kiara.exe
Get-AuthenticodeSignature .\dist\installer\Kiara-Setup-1.0.0.exe
Get-FileHash .\dist\installer\Kiara-Setup-1.0.0.exe -Algorithm SHA256
```

O status das duas assinaturas deve ser `Valid`. Certificado Authenticode e cadeia de
confiança são dependências externas; sem eles, o artefato é apenas um build de desenvolvimento.

## Experiência de instalação

- instalação em `%LOCALAPPDATA%\Programs\Kiara`, sem elevação por padrão;
- atalho no menu Iniciar;
- atalho na área de trabalho opcional e desmarcado;
- autostart opcional e desmarcado;
- execução pós-instalação opcional e desmarcada;
- fechamento coordenado do app durante upgrade.

O autostart usa um atalho na pasta Startup do usuário. Ele só é criado quando a pessoa marca
a opção e é removido pelo desinstalador; o instalador não escreve em `HKCU\...\Run`.

## Testes seguros e aceite

Os testes automatizados validam manifesto e pipeline sem executar o instalador:

```powershell
python -m pytest tests\test_windows_installer.py -q
python -m ruff check tests\test_windows_installer.py
```

Em uma VM Windows descartável, valide o artefato final: instalação, primeiro start, upgrade,
preservação de dados, atalhos, autostart opt-in e desinstalação. Esse aceite não deve rodar no
computador de desenvolvimento, pois altera estado do sistema.

