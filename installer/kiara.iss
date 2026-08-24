#ifndef MyAppVersion
  #define MyAppVersion "0.1.0-dev"
#endif

#ifndef SourceExe
  #define SourceExe "..\dist\Kiara.exe"
#endif

#ifndef OutputDirectory
  #define OutputDirectory "..\dist\installer"
#endif

#define MyAppName "Kiara"
#define MyAppPublisher "Kiara Project"
#define MyAppExeName "Kiara.exe"

[Setup]
; This GUID is the product identity. Never change it between releases: Inno Setup
; uses it to find the existing installation and perform an in-place upgrade.
AppId={{6B872A8F-15B5-4C73-BBB8-ECF4D4DA6D55}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Kiara
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDirectory}
OutputBaseFilename=Kiara-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Instalador da assistente pessoal Kiara

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked
Name: "autostart"; Description: "Iniciar a Kiara quando eu entrar no Windows"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Kiara"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Kiara"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
; Startup-folder opt-in avoids an installer-written HKCU Run value and is removed
; automatically by the uninstaller.
Name: "{userstartup}\Kiara"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar a Kiara"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Defensive cleanup if a shortcut survived a previous installer version.
Type: files; Name: "{userstartup}\Kiara.lnk"

