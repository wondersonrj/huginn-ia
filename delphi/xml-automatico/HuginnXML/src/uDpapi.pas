unit uDpapi;

{ HUGINN IA - Protecao de senha com DPAPI do Windows (CryptProtectData).
  A senha so pode ser aberta pelo mesmo usuario do Windows na mesma maquina. }

interface

function DpapiProtect(const APlain: string): string;
function DpapiUnprotect(const ACipherB64: string): string;

implementation

uses
  Winapi.Windows, System.SysUtils, System.NetEncoding;

type
  TDataBlob = record
    cbData: DWORD;
    pbData: PByte;
  end;
  PDataBlob = ^TDataBlob;

const
  CRYPTPROTECT_UI_FORBIDDEN = $1;
  ENTROPIA = 'HUGINN-XML-AUTO';

function CryptProtectData(pDataIn: PDataBlob; szDataDescr: PWideChar;
  pOptionalEntropy: PDataBlob; pvReserved: Pointer; pPromptStruct: Pointer;
  dwFlags: DWORD; pDataOut: PDataBlob): BOOL; stdcall; external 'crypt32.dll';

function CryptUnprotectData(pDataIn: PDataBlob; ppszDataDescr: PPWideChar;
  pOptionalEntropy: PDataBlob; pvReserved: Pointer; pPromptStruct: Pointer;
  dwFlags: DWORD; pDataOut: PDataBlob): BOOL; stdcall; external 'crypt32.dll';

function NovoBase64: TBase64Encoding;
begin
  Result := TBase64Encoding.Create(0); // 0 = sem quebra de linha
end;

function DpapiProtect(const APlain: string): string;
var
  InB, OutB, Ent: TDataBlob;
  Dados, EntB, Res: TBytes;
  B64: TBase64Encoding;
begin
  Result := '';
  if APlain = '' then
    Exit;
  Dados := TEncoding.UTF8.GetBytes(APlain);
  EntB := TEncoding.UTF8.GetBytes(ENTROPIA);
  try
    InB.cbData := Length(Dados);
    InB.pbData := @Dados[0];
    Ent.cbData := Length(EntB);
    Ent.pbData := @EntB[0];
    OutB.cbData := 0;
    OutB.pbData := nil;
    if not CryptProtectData(@InB, 'HUGINN', @Ent, nil, nil,
      CRYPTPROTECT_UI_FORBIDDEN, @OutB) then
      RaiseLastOSError;
    try
      SetLength(Res, OutB.cbData);
      Move(OutB.pbData^, Res[0], OutB.cbData);
    finally
      LocalFree(HLOCAL(OutB.pbData));
    end;
  finally
    if Length(Dados) > 0 then
      FillChar(Dados[0], Length(Dados), 0);
  end;
  B64 := NovoBase64;
  try
    Result := B64.EncodeBytesToString(Res);
  finally
    B64.Free;
  end;
end;

function DpapiUnprotect(const ACipherB64: string): string;
var
  InB, OutB, Ent: TDataBlob;
  Cifra, EntB, Res: TBytes;
  B64: TBase64Encoding;
begin
  Result := '';
  if Trim(ACipherB64) = '' then
    Exit;
  B64 := NovoBase64;
  try
    Cifra := B64.DecodeStringToBytes(Trim(ACipherB64));
  finally
    B64.Free;
  end;
  if Length(Cifra) = 0 then
    Exit;
  EntB := TEncoding.UTF8.GetBytes(ENTROPIA);
  InB.cbData := Length(Cifra);
  InB.pbData := @Cifra[0];
  Ent.cbData := Length(EntB);
  Ent.pbData := @EntB[0];
  OutB.cbData := 0;
  OutB.pbData := nil;
  if not CryptUnprotectData(@InB, nil, @Ent, nil, nil,
    CRYPTPROTECT_UI_FORBIDDEN, @OutB) then
    Exit; // outra maquina/usuario: senha precisa ser digitada de novo
  try
    SetLength(Res, OutB.cbData);
    if OutB.cbData > 0 then
      Move(OutB.pbData^, Res[0], OutB.cbData);
    Result := TEncoding.UTF8.GetString(Res);
    if Length(Res) > 0 then
      FillChar(Res[0], Length(Res), 0);
  finally
    LocalFree(HLOCAL(OutB.pbData));
  end;
end;

end.
