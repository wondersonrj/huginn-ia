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
DefaultDirName={code:ExistingDirectory}
UsePreviousAppDir=yes
UsePreviousTasks=yes
DisableDirPage=no
DefaultGroupName=HUGINN IA
PrivilegesRequired=lowest
UninstallLogMode=overwrite
SetupMutex=Local\HUGINN-IA-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#Output}
OutputBaseFilename=HUGINN-IA-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
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
; Execute trusted NEW maintenance code/runtime before modifying the old installation.
Source: "{#Payload}\runtime\*"; DestDir: "{tmp}\HUGINN-maintenance\runtime"; Flags: dontcopy recursesubdirs createallsubdirs
Source: "{#Payload}\installer_migration.py"; DestDir: "{tmp}\HUGINN-maintenance"; Flags: dontcopy
Source: "{#Payload}\maintenance_windows.py"; DestDir: "{tmp}\HUGINN-maintenance"; Flags: dontcopy
Source: "{#Payload}\installer-inventory.json"; DestDir: "{tmp}\HUGINN-maintenance"; Flags: dontcopy
Source: "{#Payload}\*"; DestDir: "{app}"; Excludes: "runtime\*,state\*,*.dpapi,profiles.json,local-token.bin"; Flags: ignoreversion recursesubdirs createallsubdirs
; Runtime is immutable for this bootstrap family. A different runtime requires a separate installation.
Source: "{#Payload}\runtime\*"; DestDir: "{app}\runtime"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HUGINN IA"; Filename: "{app}\HUGINN-IA.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\HUGINN IA"; Filename: "{app}\HUGINN-IA.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HUGINN-IA.exe"; Description: "Abrir HUGINN IA e configurar a conexao"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Fixed files from this package only. Never recursively delete runtime/versions.
#include "runtime-uninstall.iss"

[Code]
const
  AppRegistry = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{1F07B592-9CB4-4937-B35B-4A197E9AB867}_is1';
var
  PreserveData, Staged, Prepared, Successful: Boolean;
  MigrationLock, MaintenanceMutex: THandle;

function MaintenanceCreateMutex(Security, InitialOwner: LongWord; Name: String): THandle;
  external 'CreateMutexW@kernel32.dll stdcall';
function MaintenanceCreateFile(Name: String; Access, Sharing, Security, Disposition, Attributes: LongWord; Template: THandle): THandle;
  external 'CreateFileW@kernel32.dll stdcall';
function MaintenanceLock(Handle: THandle; OffsetLow, OffsetHigh, CountLow, CountHigh: LongWord): Boolean;
  external 'LockFile@kernel32.dll stdcall';
function MaintenanceUnlock(Handle: THandle; OffsetLow, OffsetHigh, CountLow, CountHigh: LongWord): Boolean;
  external 'UnlockFile@kernel32.dll stdcall';
function MaintenanceClose(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function ExistingDirectory(Param: String): String;
begin
  if not RegQueryStringValue(HKCU64, AppRegistry, 'Inno Setup: App Path', Result) then
    Result := ExpandConstant('{localappdata}\Programs\HUGINN IA');
end;

procedure StageMaintenance();
begin
  if not Staged then begin
    ExtractTemporaryFiles('{tmp}\HUGINN-maintenance\*');
    Staged := True;
  end;
end;

function RunMaintenance(Action: String): Boolean;
var ExitCode: Integer;
begin
  StageMaintenance();
  Result := Exec(ExpandConstant('{tmp}\HUGINN-maintenance\runtime\python.exe'),
    '-I "' + ExpandConstant('{tmp}\HUGINN-maintenance\installer_migration.py') + '" ' + Action +
    ' --root "' + ExpandConstant('{app}') + '" --inventory "' + ExpandConstant('{tmp}\HUGINN-maintenance\installer-inventory.json') +
    '" --report "' + ExpandConstant('{tmp}\HUGINN-maintenance\report.ini') + '"',
    ExpandConstant('{tmp}\HUGINN-maintenance'), SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

function MigrationMessage(): String;
var Status: String;
begin
  Status := GetIniString('Migration', 'status', 'operation_refused', ExpandConstant('{tmp}\HUGINN-maintenance\report.ini'));
  Result := 'Nao foi possivel atualizar com seguranca (' + Status + '). Dados preservados. Nao reinicie o Windows; consulte o guia de recuperacao e execute o Setup novamente.';
  if Status = 'use_registered_directory' then
    Result := 'Ja existe uma instalacao deste usuario. Use a pasta mostrada no assistente; mudar de pasta separaria o cofre DPAPI. Nenhuma instalacao foi removida.';
  if Status = 'incompatible_installation' then
    Result := 'Instalacao de outra familia/runtime/canal. A migracao foi recusada e os dados foram preservados. Consulte o suporte; nao e preciso reiniciar o Windows.';
  if (Status = 'identity_unconfirmed') or (Status = 'shutdown_refused') or (Pos('shutdown_pending', Status) = 1) then
    Result := 'A instancia ativa nao confirmou identidade/encerramento seguro. Use Encerrar HUGINN na propria interface e repita. Nenhum processo ou servico de terceiros sera finalizado.';
  Result := Result + ' Codigo: ' + Status;
end;

procedure ReleaseMigrationLock();
begin
  if MigrationLock <> 0 then begin
    MaintenanceUnlock(MigrationLock, 0, 0, 1, 0);
    MaintenanceClose(MigrationLock);
    MigrationLock := 0;
  end;
  if MaintenanceMutex <> 0 then begin
    MaintenanceClose(MaintenanceMutex); MaintenanceMutex := 0;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then begin
    Result := RunMaintenance('inspect');
    if not Result and not WizardSilent then MsgBox(MigrationMessage(), mbError, MB_OK);
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  RunMaintenance('inspect');
  Result := MemoDirInfo + NewLine + NewLine + 'Atualizacao HUGINN IA: ' +
    GetIniString('Migration', 'previous', 'instalacao nova', ExpandConstant('{tmp}\HUGINN-maintenance\report.ini')) +
    ' -> {#AppVersion}' + NewLine + 'Origem: ' +
    GetIniString('Migration', 'kind', 'fresh', ExpandConstant('{tmp}\HUGINN-maintenance\report.ini')) + NewLine + 'Preservar conexoes, senhas DPAPI, token, dados e configuracoes deste usuario.' + NewLine +
    'A instancia autenticada do HUGINN sera encerrada com seguranca. Sem desinstalar duas vezes, sem reiniciar o Windows e sem alterar Oracle.' + NewLine +
    'Copias portateis em outras pastas nao serao alteradas.' + NewLine + MemoTasksInfo;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := ''; NeedsRestart := False;
  if not RunMaintenance('inspect') then begin Result := MigrationMessage(); Exit; end;
  if not RunMaintenance('stop-owned') then begin Result := MigrationMessage(); Exit; end;
  MaintenanceMutex := MaintenanceCreateMutex(0, 0, 'Local\HUGINN-IA-Installed');
  if MaintenanceMutex = 0 then begin Result := 'Nao foi possivel proteger a manutencao. Nenhum arquivo foi alterado.'; Exit; end;
  ForceDirectories(ExpandConstant('{app}\state'));
  MigrationLock := MaintenanceCreateFile(ExpandConstant('{app}\state\supervisor.lock'), $C0000000, 3, 0, 4, $80, 0);
  if MigrationLock = $FFFFFFFF then begin MigrationLock := 0; ReleaseMigrationLock(); Result := 'Pasta em uso/sem permissao. Nenhum dado foi removido.'; Exit; end;
  if not MaintenanceLock(MigrationLock, 0, 0, 1, 0) then begin
    MaintenanceClose(MigrationLock); MigrationLock := 0; ReleaseMigrationLock();
    Result := 'HUGINN ainda em uso. Aguarde seu encerramento e repita; nenhum outro processo sera finalizado.'; Exit;
  end;
  if not RunMaintenance('prepare') then begin Result := MigrationMessage(); ReleaseMigrationLock(); Exit; end;
  Prepared := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var ExitCode: Integer;
begin
  if CurStep = ssPostInstall then begin
    if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-I "' + ExpandConstant('{app}\installer_state.py') + '" --activate-maintenance',
        ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
      RaiseException('A nova versao nao confirmou integridade/saude. A instalacao anterior sera restaurada, preservando as conexoes.');
    if not RunMaintenance('commit') then RaiseException(MigrationMessage());
    Successful := True;
    ReleaseMigrationLock();
  end;
end;

procedure DeinitializeSetup();
begin
  if Prepared and not Successful then
    if not RunMaintenance('rollback') and not WizardSilent then
      MsgBox('Recuperacao pendente. Preserve a pasta e execute novamente o Setup. Nao reinicie o Windows nem apague o cofre.', mbError, MB_OK);
  ReleaseMigrationLock();
end;

function InitializeUninstall(): Boolean;
begin
  if CheckForMutexes('Local\HUGINN-IA-Setup') then begin
    if not UninstallSilent then MsgBox('Aguarde o Setup terminar antes de desinstalar. Nenhum dado sera removido.', mbInformation, MB_OK);
    Result := False; Exit;
  end;
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
