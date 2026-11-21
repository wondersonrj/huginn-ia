unit uLicencaHUGINN;

{ HUGINN - validacao de licenca (lado do CLIENTE), compartilhada por todas as
  aplicacoes HUGINN.

  Compativel com o Gerador de Licencas HUGINN v1.1 (LicenseSignerHUGINN.pas):
    arquivo .dat = Base64(payload) + '.' + Base64(assinatura)
    payload      = PRODUTO|Cliente|ID_DA_INSTALACAO|aaaa-mm-dd   (UTF-8)
    assinatura   = RSA 2048 + SHA-256 via CryptoAPI (CryptSignHash, little-endian)

  Esta unit contem SOMENTE a CHAVE PUBLICA (derivada da chave do Gerador).
  A chave privada fica apenas no Gerador, de uso interno. }

interface

uses
  System.SysUtils;

type
  TStatusLicenca = (slAusente, slInvalida, slOutroProduto, slOutraInstalacao, slVencida, slValida);

  TLicencaHUGINN = record
    Status: TStatusLicenca;
    Produto, Cliente, Instalacao: string;
    Validade: TDateTime;
    DiasRestantes: Integer;
    Arquivo: string;
    Mensagem: string;
    function Valida: Boolean;
  end;

{ ID desta instalacao, para o botao "Copiar ID" (formato XXXX-XXXX-XXXX-XXXX). }
function IdInstalacao: string;
{ Arquivo padrao da licenca do produto, ao lado do executavel. }
function ArquivoLicencaPadrao(const Produto: string): string;
function VerificarCodigo(const Codigo, Produto: string): TLicencaHUGINN;
function VerificarArquivo(const Arquivo, Produto: string): TLicencaHUGINN;
{ Valida o .dat escolhido pelo usuario e, se valido, copia para o arquivo padrao. }
function InstalarLicenca(const Origem, Produto: string): TLicencaHUGINN;

implementation

uses
  Winapi.Windows, System.Classes, System.IOUtils, System.NetEncoding, System.Hash,
  System.Win.Registry, System.DateUtils;

const
  PROV_RSA_AES = 24;
  CRYPT_VERIFYCONTEXT = $F0000000;
  CALG_SHA_256 = $0000800C;

  // PUBLICKEYBLOB (RSA 2048) derivado da chave do Gerador de Licencas HUGINN v1.1.
  ChavePublica: array[0..275] of Byte = (
    $06, $02, $00, $00, $00, $24, $00, $00, $52, $53, $41, $31, $00, $08, $00, $00,
    $01, $00, $01, $00, $FD, $85, $CF, $B8, $5B, $5A, $BF, $DD, $6A, $DB, $1A, $EB,
    $6E, $20, $3D, $C5, $0D, $76, $43, $E2, $64, $4B, $55, $6E, $C3, $AE, $DB, $E6,
    $9F, $43, $6B, $22, $A9, $6E, $D9, $50, $8E, $8E, $2E, $42, $AA, $F8, $B1, $19,
    $5F, $73, $B3, $89, $63, $9C, $84, $4D, $31, $1F, $11, $A9, $1E, $44, $F7, $FA,
    $2B, $62, $EF, $24, $28, $AA, $11, $54, $E6, $EE, $3A, $DC, $98, $D7, $6F, $16,
    $B1, $9C, $73, $AA, $35, $34, $D9, $0C, $97, $C2, $79, $F7, $FA, $91, $D5, $41,
    $3C, $69, $01, $48, $A0, $1D, $2A, $D1, $93, $E2, $A1, $24, $72, $81, $84, $71,
    $A1, $7F, $22, $80, $5F, $0A, $ED, $17, $DC, $2C, $19, $92, $05, $08, $E0, $A3,
    $9C, $18, $3D, $E8, $98, $03, $AB, $29, $57, $8C, $25, $72, $8C, $A0, $20, $3D,
    $3E, $4F, $7D, $79, $3F, $81, $7C, $CF, $5D, $87, $5F, $9F, $B6, $EC, $DC, $28,
    $E0, $EC, $9A, $8A, $AC, $2A, $01, $22, $A5, $99, $DE, $C2, $0D, $49, $2D, $D1,
    $16, $C9, $92, $26, $F1, $71, $A8, $22, $E8, $4C, $1C, $24, $80, $D0, $39, $FE,
    $5B, $87, $BD, $2D, $2E, $46, $DA, $5B, $2F, $E6, $A7, $96, $34, $4F, $8A, $1C,
    $0B, $BE, $93, $AB, $17, $A6, $E8, $96, $EF, $DD, $70, $C3, $62, $2B, $2F, $DE,
    $38, $29, $FE, $76, $28, $73, $99, $C3, $D4, $28, $BA, $51, $68, $5E, $23, $00,
    $B7, $1A, $7E, $69, $5E, $B9, $ED, $35, $30, $96, $86, $C8, $60, $0B, $36, $E6,
    $42, $6C, $5C, $DA
  );

type
  HCRYPTPROV = NativeUInt;
  HCRYPTHASH = NativeUInt;
  HCRYPTKEY = NativeUInt;

function CryptAcquireContextW(var phProv: HCRYPTPROV; pszContainer, pszProvider: PWideChar;
  dwProvType, dwFlags: DWORD): BOOL; stdcall; external 'advapi32.dll' name 'CryptAcquireContextW';
function CryptReleaseContext(hProv: HCRYPTPROV; dwFlags: DWORD): BOOL; stdcall; external 'advapi32.dll';
function CryptImportKey(hProv: HCRYPTPROV; pbData: PByte; dwDataLen: DWORD; hPubKey: HCRYPTKEY;
  dwFlags: DWORD; var phKey: HCRYPTKEY): BOOL; stdcall; external 'advapi32.dll';
function CryptDestroyKey(hKey: HCRYPTKEY): BOOL; stdcall; external 'advapi32.dll';
function CryptCreateHash(hProv: HCRYPTPROV; Algid: DWORD; hKey: HCRYPTKEY; dwFlags: DWORD;
  var phHash: HCRYPTHASH): BOOL; stdcall; external 'advapi32.dll';
function CryptHashData(hHash: HCRYPTHASH; pbData: PByte; dwDataLen: DWORD; dwFlags: DWORD): BOOL;
  stdcall; external 'advapi32.dll';
function CryptVerifySignatureW(hHash: HCRYPTHASH; pbSignature: PByte; dwSigLen: DWORD;
  hPubKey: HCRYPTKEY; sDescription: PWideChar; dwFlags: DWORD): BOOL; stdcall;
  external 'advapi32.dll' name 'CryptVerifySignatureW';
function CryptDestroyHash(hHash: HCRYPTHASH): BOOL; stdcall; external 'advapi32.dll';

function TLicencaHUGINN.Valida: Boolean;
begin
  Result := Status = slValida;
end;

function MachineGuid: string;
var
  R: TRegistry;
begin
  Result := '';
  R := TRegistry.Create(KEY_READ or KEY_WOW64_64KEY);
  try
    R.RootKey := HKEY_LOCAL_MACHINE;
    if R.OpenKeyReadOnly('SOFTWARE\Microsoft\Cryptography') then
    try
      Result := R.ReadString('MachineGuid');
    finally
      R.CloseKey;
    end;
  finally
    R.Free;
  end;
end;

function IdInstalacao: string;
var
  Base, H: string;
begin
  // Identifica o Windows (MachineGuid). No WinThor Cloud/RDP todos os usuarios do
  // mesmo servidor compartilham o mesmo ID.
  Base := UpperCase(Trim(MachineGuid));
  if Base = '' then
    Base := UpperCase(GetEnvironmentVariable('COMPUTERNAME'));
  H := UpperCase(THashSHA2.GetHashString('HUGINN|' + Base, THashSHA2.TSHA2Version.SHA256));
  Result := Copy(H, 1, 4) + '-' + Copy(H, 5, 4) + '-' + Copy(H, 9, 4) + '-' + Copy(H, 13, 4);
end;

function ArquivoLicencaPadrao(const Produto: string): string;
begin
  Result := TPath.Combine(ExtractFilePath(ParamStr(0)), 'licenca_' + LowerCase(Trim(Produto)) + '.dat');
end;

function AssinaturaConfere(const Payload, Assinatura: TBytes): Boolean;
var
  P: HCRYPTPROV;
  K: HCRYPTKEY;
  H: HCRYPTHASH;
begin
  Result := False;
  if (Length(Payload) = 0) or (Length(Assinatura) = 0) then
    Exit;
  P := 0; K := 0; H := 0;
  if not CryptAcquireContextW(P, nil, nil, PROV_RSA_AES, CRYPT_VERIFYCONTEXT) then
    Exit;
  try
    if not CryptImportKey(P, @ChavePublica[0], DWORD(SizeOf(ChavePublica)), 0, 0, K) then
      Exit;
    try
      if not CryptCreateHash(P, CALG_SHA_256, 0, 0, H) then
        Exit;
      try
        if not CryptHashData(H, @Payload[0], DWORD(Length(Payload)), 0) then
          Exit;
        Result := CryptVerifySignatureW(H, @Assinatura[0], DWORD(Length(Assinatura)), K, nil, 0);
      finally
        CryptDestroyHash(H);
      end;
    finally
      CryptDestroyKey(K);
    end;
  finally
    CryptReleaseContext(P, 0);
  end;
end;

function VerificarCodigo(const Codigo, Produto: string): TLicencaHUGINN;
var
  Partes, Campos: TArray<string>;
  PayloadBytes, Sig: TBytes;
  Payload: string;
  Y, M, D: Word;
begin
  Result := Default(TLicencaHUGINN);
  Result.Status := slInvalida;
  Partes := Trim(Codigo).Split(['.']);
  if Length(Partes) <> 2 then
  begin
    Result.Mensagem := 'Arquivo de licença em formato inválido.';
    Exit;
  end;
  try
    PayloadBytes := TNetEncoding.Base64.DecodeStringToBytes(Partes[0]);
    Sig := TNetEncoding.Base64.DecodeStringToBytes(Partes[1]);
  except
    Result.Mensagem := 'Arquivo de licença corrompido.';
    Exit;
  end;
  if not AssinaturaConfere(PayloadBytes, Sig) then
  begin
    Result.Mensagem := 'Assinatura da licença inválida (arquivo alterado ou não emitido pela HUGINN).';
    Exit;
  end;
  Payload := TEncoding.UTF8.GetString(PayloadBytes);
  Campos := Payload.Split(['|']);
  if Length(Campos) <> 4 then
  begin
    Result.Mensagem := 'Conteúdo da licença inválido.';
    Exit;
  end;
  Result.Produto := Campos[0];
  Result.Cliente := Campos[1];
  Result.Instalacao := Campos[2];
  Y := StrToIntDef(Copy(Campos[3], 1, 4), 0);
  M := StrToIntDef(Copy(Campos[3], 6, 2), 0);
  D := StrToIntDef(Copy(Campos[3], 9, 2), 0);
  if not TryEncodeDate(Y, M, D, Result.Validade) then
  begin
    Result.Mensagem := 'Validade da licença inválida.';
    Exit;
  end;
  Result.DiasRestantes := Trunc(Result.Validade) - Trunc(Date);
  if not SameText(Result.Produto, Trim(Produto)) then
  begin
    Result.Status := slOutroProduto;
    Result.Mensagem := 'Esta licença é de outro produto (' + Result.Produto + ').';
  end
  else if not SameText(Trim(Result.Instalacao), IdInstalacao) then
  begin
    Result.Status := slOutraInstalacao;
    Result.Mensagem := 'Esta licença foi emitida para outra instalação (ID ' + Result.Instalacao +
      '). O ID desta máquina é ' + IdInstalacao + '.';
  end
  else if Result.DiasRestantes < 0 then
  begin
    Result.Status := slVencida;
    Result.Mensagem := 'Licença vencida em ' + DateToStr(Result.Validade) + '.';
  end
  else
  begin
    Result.Status := slValida;
    Result.Mensagem := 'Licenciado para ' + Result.Cliente + ' até ' + DateToStr(Result.Validade) + '.';
  end;
end;

function VerificarArquivo(const Arquivo, Produto: string): TLicencaHUGINN;
begin
  if not TFile.Exists(Arquivo) then
  begin
    Result := Default(TLicencaHUGINN);
    Result.Status := slAusente;
    Result.Mensagem := 'Nenhuma licença instalada.';
  end
  else
    Result := VerificarCodigo(TFile.ReadAllText(Arquivo, TEncoding.UTF8), Produto);
  Result.Arquivo := Arquivo;
end;

function InstalarLicenca(const Origem, Produto: string): TLicencaHUGINN;
var
  Destino: string;
begin
  Result := VerificarArquivo(Origem, Produto);
  if not Result.Valida then
    Exit;
  Destino := ArquivoLicencaPadrao(Produto);
  if not SameText(TPath.GetFullPath(Origem), TPath.GetFullPath(Destino)) then
    TFile.Copy(Origem, Destino, True);
  Result.Arquivo := Destino;
end;

end.
