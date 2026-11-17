#ifndef Payload
  #error Payload is required
#endif
#ifndef AppVersion
  #define AppVersion "0.2.1"
#endif
[Setup]
AppId={{9A462CA8-26FD-44BD-93E7-4D4F8C04E021}
AppName=HUGINN Smart Connector
AppVersion={#AppVersion}
AppPublisher=HUGINN
DefaultDirName={autopf}\HUGINN Smart Connector
DefaultGroupName=HUGINN Smart Connector
OutputDir={#Output}
OutputBaseFilename=HUGINN_Smart_Connector_Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
UninstallDisplayIcon={app}\HUGINNConnector.exe
SetupLogging=yes
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Configurar Smart Connector"; Filename: "{app}\HUGINNConnector.exe"; Parameters: "--configure"
Name: "{group}\Desinstalar Smart Connector"; Filename: "{uninstallexe}"
[Code]
function Command(const Switch: String): Boolean;
var ResultCode: Integer;
begin
  Result := Exec(ExpandConstant('{app}\HUGINNConnector.exe'), Switch, '', SW_HIDE,
                 ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\HUGINNConnector.exe')) then
    if not Command('--stop-service') then
      Result := 'Não foi possível parar o serviço. Verifique o Visualizador de Eventos.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    if not Command('--init') then RaiseException('Falha ao criar configuração protegida.');
    if not WizardSilent then
      if not Command('--configure') then RaiseException('Falha no assistente de configuração.');
    if not Command('--install-service') then
      RaiseException('Falha ao iniciar serviço. Consulte o Visualizador de Eventos e a documentação.');
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := Command('--remove-service');
  if not Result then MsgBox('Não foi possível remover o serviço. Desinstalação cancelada.', mbError, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    if not UninstallSilent then
      if MsgBox('Apagar permanentemente configuração, credenciais e logs? Não será possível recuperar.',
                 mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{commonappdata}\HUGINN\SmartConnector'), True, True, True);
  end;
end;
