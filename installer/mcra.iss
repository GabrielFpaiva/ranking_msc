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

; NOTA: A pasta de dados %LOCALAPPDATA%\MCRA fica fora de {app} de propósito.
; Ela contém configuração com usuários cadastrados, snapshots por competência,
; relatórios gerados e logs de auditoria. A remoção desses dados é decidida pelo
; usuário no diálogo de desinstalação (CurUninstallStepChanged). Não acrescente
; [UninstallDelete] para essa pasta — a trilha de auditoria é um ativo que deve
; ser preservado por padrão.

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
  Flags: nowait postinstall skipifsilent runascurrentuser

[Code]
function WebView2Ausente: Boolean;
var
  VersaoHKLM, VersaoHKCU: String;
  ExisteHKLM, ExisteHKCU: Boolean;
begin
  { Consultar HKEY_LOCAL_MACHINE (instalação por sistema) }
  ExisteHKLM := RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', VersaoHKLM);

  { Consultar HKEY_CURRENT_USER (instalação por usuário) }
  ExisteHKCU := RegQueryStringValue(HKEY_CURRENT_USER,
    'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'pv', VersaoHKCU);

  { WebView2 está ausente se nenhuma das duas chaves existe E o valor é válido
    (0.0.0.0 é a marca de "registrado mas não instalado") }
  Result := not ((ExisteHKLM and (VersaoHKLM <> '0.0.0.0')) or
                 (ExisteHKCU and (VersaoHKCU <> '0.0.0.0')));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  LocalAppDataPath: String;
  Response: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // NOTA: Desinstalador roda elevado; {localappdata} resolve para a conta que
    // rodou o desinstalador. Se a pessoa elevar com outra conta de admin, o
    // caminho não será o dela e a limpeza não achará nada. Isso é esperado —
    // a remoção só funciona quando a pessoa é administradora da própria máquina.
    LocalAppDataPath := ExpandConstant('{localappdata}\MCRA');

    Response := MsgBox(
      'Desinstalar também os dados de configuração e histórico?' + #13 + #13 +
      'Caminho: ' + LocalAppDataPath + #13 + #13 +
      'Se "Não" for escolhido, os seguintes dados serão preservados:' + #13 +
      '- Usuários cadastrados na configuração' + #13 +
      '- Snapshots de validação por competência' + #13 +
      '- Relatórios gerados anteriormente' + #13 +
      '- Logs de auditoria e execução' + #13 + #13 +
      'Deseja remover esses dados?',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2);

    if Response = IDYES then
    begin
      DelTree(LocalAppDataPath, True, True, True);
    end;
  end;
end;
