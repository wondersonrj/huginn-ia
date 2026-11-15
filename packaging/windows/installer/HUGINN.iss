#ifndef Payload
  #error Payload required
#endif
#ifndef Output
  #error Output required
#endif
#ifndef AppVersion
  #error AppVersion required
#endif
#ifndef RuntimeId
  #error RuntimeId required
#endif
[Setup]
AppId={{1F07B592-9CB4-4937-B35B-4A197E9AB867}
AppName=HUGINN IA
AppVersion={#AppVersion}
AppVerName=HUGINN IA {#AppVersion} - TESTE - build {#SourceCommit}
AppPublisher=HUGINN IA
DefaultDirName={localappdata}\Programs\HUGINN IA
DefaultGroupName=HUGINN IA
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#Output}
OutputBaseFilename=HUGINN-IA-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\HUGINN-IA-Installed
CloseApplications=no
RestartApplications=no
AlwaysRestart=no
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\HUGINN-IA.exe
SetupLogging=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Excludes: "runtime\*,state\*,*.dpapi,profiles.json,local-token.bin"; Flags: ignoreversion recursesubdirs createallsubdirs
; Runtime is immutable for this bootstrap family. A different runtime requires a separate installation.
Source: "{#Payload}\runtime\*"; DestDir: "{app}\runtime"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HUGINN IA"; Filename: "{app}\HUGINN-IA.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\HUGINN IA"; Filename: "{app}\HUGINN-IA.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HUGINN-IA.exe"; Description: "Abrir HUGINN IA e configurar a conexao"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\versions"

[Code]
var PreserveData: Boolean;
function PrepareToInstall(var NeedsRestart: Boolean): String;
var Data: AnsiString;
begin
  Result := '';
  NeedsRestart := False;
  if LoadStringFromFile(ExpandConstant('{app}\bootstrap.json'), Data) then
    if Pos('{#RuntimeId}', String(Data)) = 0 then
      Result := 'Este pacote usa outro runtime. Instale em uma pasta nova e recadastre a conexao; nao sera feito upgrade inseguro ou reinicio do Windows.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Code: Integer;
begin
  if CurStep = ssPostInstall then begin
    if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-I "' + ExpandConstant('{app}\installer_state.py') + '" --activate', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
      RaiseException('A nova versao nao confirmou saude. O apontador anterior foi preservado; consulte o guia de recuperacao.');
  end;
end;

function InitializeUninstall(): Boolean;
begin
  if CheckForMutexes('Local\HUGINN-IA-Installed') then begin
    if not UninstallSilent then MsgBox('Use Encerrar HUGINN na interface antes de desinstalar. Outros servicos nao serao encerrados.', mbInformation, MB_OK);
    Result := False;
    Exit;
  end;
  PreserveData := True;
  if not UninstallSilent then
    PreserveData := MsgBox('Manter conexoes e senhas protegidas deste usuario para reinstalar depois? Sim = manter; Nao = remover dados desta instalacao. Nenhum dado Oracle sera alterado.', mbConfirmation, MB_YESNO) = IDYES;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Code: Integer;
begin
  if (CurUninstallStep = usUninstall) and ((not PreserveData) or (ExpandConstant('{param:REMOVEDATA|0}') = '1')) then begin
    if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-I "' + ExpandConstant('{app}\installer_state.py') + '" --remove-data', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
      RaiseException('Nao foi possivel remover os dados privados. Desinstalacao interrompida; consulte o guia de suporte.');
  end;
end;
