unit uConfig;

{ HUGINN IA - Configuracao do diagnostico (HuginnFVDiag.ini ao lado do .exe).
  A senha nunca vai em texto puro: so protegida por DPAPI, e so se o usuario pedir. }

interface

type
  TFVConfig = record
    Host: string;
    Porta: Integer;
    Servico: string;
    UsarSID: Boolean;
    ModoDireto: Boolean;
    Usuario: string;
    Senha: string;
    Owner: string;          // schema do WinThor (vazio = mesmo do usuario)
    SalvarSenha: Boolean;
    AmostraPedidos: Boolean;
    AmostraClientes: Boolean;
    PastaSaida: string;
    function OwnerEfetivo: string;
    function ServidorTexto: string;
  end;

function ArquivoIni: string;
function CarregarConfig: TFVConfig;
procedure SalvarConfig(const C: TFVConfig);
function IdentificadorValido(const S: string): Boolean;

implementation

uses
  System.SysUtils, System.IniFiles, System.IOUtils, System.RegularExpressions,
  uDpapi;

const
  SEC = 'Conexao';
  SEC_OPC = 'Opcoes';

function ArquivoIni: string;
begin
  Result := ChangeFileExt(ParamStr(0), '.ini');
end;

function IdentificadorValido(const S: string): Boolean;
begin
  Result := TRegEx.IsMatch(S, '^[A-Z][A-Z0-9_$#]{0,127}$');
end;

{ TFVConfig }

function TFVConfig.OwnerEfetivo: string;
begin
  if Trim(Owner) <> '' then
    Result := UpperCase(Trim(Owner))
  else
    Result := UpperCase(Trim(Usuario));
end;

function TFVConfig.ServidorTexto: string;
begin
  if UsarSID then
    Result := Format('%s:%d:%s', [Host, Porta, Servico])
  else
    Result := Format('%s:%d/%s', [Host, Porta, Servico]);
end;

function CarregarConfig: TFVConfig;
var
  Ini: TIniFile;
begin
  Ini := TIniFile.Create(ArquivoIni);
  try
    Result.Host := Ini.ReadString(SEC, 'Host', '');
    Result.Porta := Ini.ReadInteger(SEC, 'Porta', 1521);
    Result.Servico := Ini.ReadString(SEC, 'Servico', '');
    Result.UsarSID := Ini.ReadBool(SEC, 'UsarSID', False);
    Result.ModoDireto := Ini.ReadBool(SEC, 'ModoDireto', True);
    Result.Usuario := Ini.ReadString(SEC, 'Usuario', '');
    Result.Owner := Ini.ReadString(SEC, 'Owner', '');
    Result.SalvarSenha := Ini.ReadBool(SEC, 'SalvarSenha', False);
    if Result.SalvarSenha then
      Result.Senha := DpapiUnprotect(Ini.ReadString(SEC, 'SenhaDPAPI', ''))
    else
      Result.Senha := '';
    Result.AmostraPedidos := Ini.ReadBool(SEC_OPC, 'AmostraPedidos', True);
    Result.AmostraClientes := Ini.ReadBool(SEC_OPC, 'AmostraClientes', False);
    Result.PastaSaida := Ini.ReadString(SEC_OPC, 'PastaSaida',
      TPath.Combine(TPath.GetDocumentsPath, 'HUGINN\Diagnosticos'));
  finally
    Ini.Free;
  end;
end;

procedure SalvarConfig(const C: TFVConfig);
var
  Ini: TIniFile;
begin
  Ini := TIniFile.Create(ArquivoIni);
  try
    Ini.WriteString(SEC, 'Host', C.Host);
    Ini.WriteInteger(SEC, 'Porta', C.Porta);
    Ini.WriteString(SEC, 'Servico', C.Servico);
    Ini.WriteBool(SEC, 'UsarSID', C.UsarSID);
    Ini.WriteBool(SEC, 'ModoDireto', C.ModoDireto);
    Ini.WriteString(SEC, 'Usuario', C.Usuario);
    Ini.WriteString(SEC, 'Owner', C.Owner);
    Ini.WriteBool(SEC, 'SalvarSenha', C.SalvarSenha);
    if C.SalvarSenha and (C.Senha <> '') then
      Ini.WriteString(SEC, 'SenhaDPAPI', DpapiProtect(C.Senha))
    else
      Ini.DeleteKey(SEC, 'SenhaDPAPI');
    Ini.WriteBool(SEC_OPC, 'AmostraPedidos', C.AmostraPedidos);
    Ini.WriteBool(SEC_OPC, 'AmostraClientes', C.AmostraClientes);
    Ini.WriteString(SEC_OPC, 'PastaSaida', C.PastaSaida);
  finally
    Ini.Free;
  end;
end;

end.
