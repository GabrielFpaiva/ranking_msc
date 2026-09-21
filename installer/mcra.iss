; installer/mcra.iss — instalador do MCRA PMJP para Windows 10/11.
; Compilar: iscc installer\mcra.iss /DMyAppVersion=1.0.0

#define MyAppName "MCRA PMJP"
#define MyAppExeName "MCRA.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\MCRA
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=MCRA-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\dist\MCRA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  Check: WebView2Ausente; StatusMsg: "Instalando o componente de exibicao..."
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[Code]
function WebView2Ausente: Boolean;
var
  Versao: String;
begin
  Result := not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', Versao);
end;
