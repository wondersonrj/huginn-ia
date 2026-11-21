unit uConfig;

{ HUGINN XML Automatico - configuracao (HuginnXML.ini ao lado do .exe).
  Mesmo padrao do HuginnFVDiag: a senha so e guardada se o usuario pedir, e
  sempre protegida por DPAPI (nunca em texto puro). }

interface

uses
  uTipos;

type
  TXmlConfig = record
    // Conexao Oracle (UniDAC)
    Host: string;
    Porta: Integer;
    Servico: string;
    UsarSID: Boolean;
    ModoDireto: Boolean;
    Usuario: string;
    Senha: string;
    Owner: string;            // schema do WinThor (vazio = sinonimos do usuario)
    SalvarSenha: Boolean;
    // Operacao
    UsarOracle: Boolean;      // False = provedor de demonstracao
    ModoPesquisa: TModoPesquisa;
    UsarFator253: Boolean;
    ToleranciaCustoPct: Double;
    PastaBase: string;        // Recebidos, Liberados e logs ficam aqui
    PastaLiberados: string;   // onde o XML original e disponibilizado para a 1301
    // Entrega para a fila da 1321 (GRAVA no ERP: desligada por padrao)
    Entrega1321: Boolean;
    CodFunc: Integer;         // matricula gravada em PCNFENTXML.CODFUNC
    JanelaDias1321: Integer;  // APARTIRDIA da 1321 (trace: 90)
    function ServidorTexto: string;
  end;

function ArquivoIni: string;
function CarregarConfig: TXmlConfig;
procedure SalvarConfig(const C: TXmlConfig);
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

function TXmlConfig.ServidorTexto: string;
begin
  if UsarSID then
    Result := Format('%s:%d:%s', [Host, Porta, Servico])
  else
    Result := Format('%s:%d/%s', [Host, Porta, Servico]);
end;

function CarregarConfig: TXmlConfig;
var
  Ini: TIniFile;
  Modo: Integer;
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
    Result.UsarOracle := Ini.ReadBool(SEC_OPC, 'UsarOracle', False);
    Modo := Ini.ReadInteger(SEC_OPC, 'ModoPesquisa', Ord(mpAutomatica));
    if (Modo < Ord(Low(TModoPesquisa))) or (Modo > Ord(High(TModoPesquisa))) then
      Modo := Ord(mpAutomatica);
    Result.ModoPesquisa := TModoPesquisa(Modo);
    Result.UsarFator253 := Ini.ReadBool(SEC_OPC, 'UsarFator253', True);
    Result.ToleranciaCustoPct := Ini.ReadFloat(SEC_OPC, 'ToleranciaCustoPct', 5);
    Result.PastaBase := Ini.ReadString(SEC_OPC, 'PastaBase',
      TPath.Combine(TPath.GetDocumentsPath, 'HUGINN\XML'));
    Result.PastaLiberados := Ini.ReadString(SEC_OPC, 'PastaLiberados',
      TPath.Combine(Result.PastaBase, 'Liberados'));
    Result.Entrega1321 := Ini.ReadBool(SEC_OPC, 'Entrega1321', False);
    Result.CodFunc := Ini.ReadInteger(SEC_OPC, 'CodFunc', 0);
    Result.JanelaDias1321 := Ini.ReadInteger(SEC_OPC, 'JanelaDias1321', 90);
  finally
    Ini.Free;
  end;
end;

procedure SalvarConfig(const C: TXmlConfig);
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
    Ini.WriteBool(SEC_OPC, 'UsarOracle', C.UsarOracle);
    Ini.WriteInteger(SEC_OPC, 'ModoPesquisa', Ord(C.ModoPesquisa));
    Ini.WriteBool(SEC_OPC, 'UsarFator253', C.UsarFator253);
    Ini.WriteFloat(SEC_OPC, 'ToleranciaCustoPct', C.ToleranciaCustoPct);
    Ini.WriteString(SEC_OPC, 'PastaBase', C.PastaBase);
    Ini.WriteString(SEC_OPC, 'PastaLiberados', C.PastaLiberados);
    Ini.WriteBool(SEC_OPC, 'Entrega1321', C.Entrega1321);
    Ini.WriteInteger(SEC_OPC, 'CodFunc', C.CodFunc);
    Ini.WriteInteger(SEC_OPC, 'JanelaDias1321', C.JanelaDias1321);
  finally
    Ini.Free;
  end;
end;

end.
