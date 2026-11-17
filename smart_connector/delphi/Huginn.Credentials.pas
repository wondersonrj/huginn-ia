unit Huginn.Credentials;

interface

procedure SaveCloudToken(const Origin, Token: string);
function ReadCloudToken(const Origin: string): string;
procedure DeleteCloudToken(const Origin: string);

implementation

uses System.SysUtils, Winapi.Windows;

type
  PCredential = ^TCredential;
  TCredential = record
    Flags, Kind: DWORD;
    TargetName, Comment: PWideChar;
    LastWritten: TFileTime;
    BlobSize: DWORD;
    Blob: PByte;
    Persist, AttributeCount: DWORD;
    Attributes: Pointer;
    TargetAlias, UserName: PWideChar;
  end;

function CredWriteW(var Credential: TCredential; Flags: DWORD): BOOL; stdcall;
  external 'advapi32.dll' name 'CredWriteW';
function CredReadW(Target: PWideChar; Kind, Flags: DWORD; var Credential: PCredential): BOOL; stdcall;
  external 'advapi32.dll' name 'CredReadW';
function CredDeleteW(Target: PWideChar; Kind, Flags: DWORD): BOOL; stdcall;
  external 'advapi32.dll' name 'CredDeleteW';
procedure CredFree(Buffer: Pointer); stdcall; external 'advapi32.dll' name 'CredFree';

function TargetFor(const Origin: string): string;
begin
  if (Origin = '') or (Length(Origin) > 512) then
    raise Exception.Create('Origem da credencial invalida.');
  Result := 'HUGINN/SmartConnector/' + LowerCase(Origin);
  if Result[Length(Result)] = '/' then Delete(Result, Length(Result), 1);
end;

procedure SaveCloudToken(const Origin, Token: string);
var Credential: TCredential; Target: string; I: Integer;
begin
  if (Length(Token) < 32) or (Length(Token) > 1024) then
    raise Exception.Create('Token invalido.');
  for I := 1 to Length(Token) do
    if (Ord(Token[I]) <= 32) or (Ord(Token[I]) = 127) then
      raise Exception.Create('Token invalido.');
  Target := TargetFor(Origin);
  FillChar(Credential, SizeOf(Credential), 0);
  Credential.Kind := 1; // CRED_TYPE_GENERIC
  Credential.TargetName := PWideChar(Target);
  Credential.BlobSize := Length(Token) * SizeOf(Char);
  Credential.Blob := PByte(PWideChar(Token));
  Credential.Persist := 2; // Current user's vault, persists on this Windows machine
  if not CredWriteW(Credential, 0) then
    raise Exception.Create('Cofre Windows indisponivel. Nao foi criado arquivo alternativo.');
end;

function ReadCloudToken(const Origin: string): string;
var Credential: PCredential; Target: string;
begin
  Target := TargetFor(Origin);
  if not CredReadW(PWideChar(Target), 1, 0, Credential) then
    raise Exception.Create('Configure a credencial da API para este usuario Windows.');
  try
    if (Credential.BlobSize < 64) or (Credential.BlobSize > 2048) or (Credential.BlobSize mod 2 <> 0) then
      raise Exception.Create('Credencial invalida no cofre Windows.');
    SetString(Result, PWideChar(Credential.Blob), Credential.BlobSize div SizeOf(Char));
  finally
    CredFree(Credential);
  end;
end;

procedure DeleteCloudToken(const Origin: string);
var Target: string;
begin
  Target := TargetFor(Origin);
  if not CredDeleteW(PWideChar(Target), 1, 0) and (GetLastError <> ERROR_NOT_FOUND) then
    raise Exception.Create('Nao foi possivel remover a credencial.');
end;

end.
