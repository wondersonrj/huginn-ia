unit uXmlNFe;

{ HUGINN XML Automatico - leitura segura da NF-e.

  - Os bytes recebidos sao a fonte da verdade: o hash SHA-256 e calculado sobre
    eles e o arquivo liberado ao WinThor e uma copia byte a byte (nunca
    reserializado).
  - Parser MSXML 6 com DTD proibida, sem resolver entidades externas, sem
    validacao por schema e sem acesso a rede. Limite de tamanho explicito.
  - Ler o protocolo do XML NAO equivale a consultar a autorizacao na SEFAZ. }

interface

uses
  System.SysUtils, uTipos;

const
  TAMANHO_MAX_XML = 5 * 1024 * 1024;

type
  EXmlNFe = class(Exception);            // XML invalido ou inconsistente
  EForaEscopo = class(EXmlNFe);          // documento valido, mas nao e NF-e modelo 55

function LerBytesArquivo(const Arquivo: string): TBytes;
function Sha256Hex(const Dados: TBytes): string;
function InterpretarNFe(const Dados: TBytes): TNotaXML;
function LerNFeArquivo(const Arquivo: string; out Bytes: TBytes): TNotaXML;

implementation

uses
  System.Classes, System.Hash, System.Variants, System.Math,
  Winapi.Windows, Winapi.ActiveX, Winapi.msxml,
  uValidacao;

const
  NO_ELEMENTO = 1;   // DOMNodeType NODE_ELEMENT

function LerBytesArquivo(const Arquivo: string): TBytes;
var
  F: TFileStream;
begin
  F := TFileStream.Create(Arquivo, fmOpenRead or fmShareDenyWrite);
  try
    if F.Size = 0 then
      raise EXmlNFe.Create('Arquivo vazio.');
    if F.Size > TAMANHO_MAX_XML then
      raise EXmlNFe.CreateFmt('Arquivo acima do limite de %d MB.', [TAMANHO_MAX_XML div (1024 * 1024)]);
    SetLength(Result, F.Size);
    F.ReadBuffer(Result[0], F.Size);
  finally
    F.Free;
  end;
end;

function Sha256Hex(const Dados: TBytes): string;
var
  H: THashSHA2;
begin
  H := THashSHA2.Create(THashSHA2.TSHA2Version.SHA256);
  if Length(Dados) > 0 then
    H.Update(Dados, Length(Dados));
  Result := LowerCase(H.HashAsString);
end;

{ ---------- navegacao no DOM, ignorando prefixo de namespace ---------- }

function Filho(const N: IXMLDOMNode; const Nome: string): IXMLDOMNode;
var
  I: Integer;
  C: IXMLDOMNode;
begin
  Result := nil;
  if N = nil then
    Exit;
  for I := 0 to N.childNodes.length - 1 do
  begin
    C := N.childNodes.item[I];
    if (Integer(C.nodeType) = NO_ELEMENTO) and (string(C.baseName) = Nome) then
      Exit(C);
  end;
end;

function Descendente(const N: IXMLDOMNode; const Nome: string): IXMLDOMNode;
var
  I: Integer;
  C: IXMLDOMNode;
begin
  Result := nil;
  if N = nil then
    Exit;
  for I := 0 to N.childNodes.length - 1 do
  begin
    C := N.childNodes.item[I];
    if Integer(C.nodeType) <> NO_ELEMENTO then
      Continue;
    if string(C.baseName) = Nome then
      Exit(C);
    Result := Descendente(C, Nome);
    if Result <> nil then
      Exit;
  end;
end;

function Txt(const N: IXMLDOMNode; const Nome: string): string;
var
  C: IXMLDOMNode;
begin
  C := Filho(N, Nome);
  if C = nil then
    Result := ''
  else
    Result := Trim(string(C.text));
end;

function TxtDesc(const N: IXMLDOMNode; const Nome: string): string;
var
  C: IXMLDOMNode;
begin
  C := Descendente(N, Nome);
  if C = nil then
    Result := ''
  else
    Result := Trim(string(C.text));
end;

function Atributo(const N: IXMLDOMNode; const Nome: string): string;
var
  E: IXMLDOMElement;
begin
  Result := '';
  if (N <> nil) and Supports(N, IXMLDOMElement, E) then
    Result := Trim(VarToStr(E.getAttribute(Nome)));
end;

function Num(const S, Contexto: string): Double;
begin
  if Trim(S) = '' then
    Exit(0);
  if not TryStrToFloat(Trim(S), Result, TFormatSettings.Invariant) or
     IsNan(Result) or IsInfinite(Result) then
    raise EXmlNFe.CreateFmt('Valor numérico inválido em %s: "%s".', [Contexto, S]);
end;

procedure Avisar(var Nota: TNotaXML; const Msg: string);
begin
  SetLength(Nota.Avisos, Length(Nota.Avisos) + 1);
  Nota.Avisos[High(Nota.Avisos)] := Msg;
end;

function ContemDoctype(const Dados: TBytes): Boolean;
const
  ALVO: AnsiString = '<!DOCTYPE';
var
  I, J: Integer;
  Ok: Boolean;
begin
  // Defesa adicional (o MSXML ja proibe DTD): procura "<!DOCTYPE" em ASCII.
  Result := False;
  for I := 0 to Length(Dados) - Length(ALVO) do
  begin
    Ok := True;
    for J := 1 to Length(ALVO) do
      if UpCase(AnsiChar(Dados[I + J - 1])) <> ALVO[J] then
      begin
        Ok := False;
        Break;
      end;
    if Ok then
      Exit(True);
  end;
end;

procedure ConferirChave(var Nota: TNotaXML);
var
  EmitChave: string;
begin
  if not ChaveNFeValida(Nota.Chave) then
    raise EXmlNFe.Create('Chave de acesso ausente ou com dígito verificador inválido: ' + Nota.Chave);
  // Leiaute da chave: cUF(2) AAMM(4) CNPJ/CPF(14) mod(2) serie(3) nNF(9) tpEmis(1) cNF(8) DV(1)
  EmitChave := Copy(Nota.Chave, 7, 14);
  if (Nota.EmitCNPJ <> '') and (EmitChave <> StringOfChar('0', 14 - Length(Nota.EmitCNPJ)) + Nota.EmitCNPJ) then
    Avisar(Nota, 'O CNPJ/CPF do emitente não confere com o da chave de acesso.');
  if Copy(Nota.Chave, 21, 2) <> Nota.Modelo then
    Avisar(Nota, 'O modelo informado não confere com o da chave de acesso.');
  if StrToIntDef(Copy(Nota.Chave, 23, 3), -1) <> StrToIntDef(Nota.Serie, -2) then
    Avisar(Nota, 'A série não confere com a da chave de acesso.');
  if StrToInt64Def(Copy(Nota.Chave, 26, 9), -1) <> StrToInt64Def(Nota.Numero, -2) then
    Avisar(Nota, 'O número da nota não confere com o da chave de acesso.');
  if Nota.TemProtocolo and (Nota.ChaveProt <> '') and (Nota.ChaveProt <> Nota.Chave) then
    Avisar(Nota, 'A chave do protocolo é diferente da chave da nota.');
end;

function InterpretarInterno(const Dados: TBytes): TNotaXML;
var
  Doc: IXMLDOMDocument2;
  MS: TMemoryStream;
  Unk: IUnknown;
  Fonte: OleVariant;
  Raiz, NFe, Inf, Ide, Emit, Dest, Det, Prod, Imposto, Tot, Prot: IXMLDOMNode;
  NomeRaiz, Ctx: string;
  I: Integer;
  It: TItemXML;
begin
  Result := Default(TNotaXML);
  if Length(Dados) = 0 then
    raise EXmlNFe.Create('Arquivo vazio.');
  if Length(Dados) > TAMANHO_MAX_XML then
    raise EXmlNFe.Create('Arquivo acima do limite permitido.');
  if ContemDoctype(Dados) then
    raise EXmlNFe.Create('XML com DTD/DOCTYPE não é permitido.');

  Result.TamanhoBytes := Length(Dados);
  Result.Sha256 := Sha256Hex(Dados);

  Doc := CoDOMDocument60.Create;
  Doc.async := False;
  Doc.validateOnParse := False;
  Doc.resolveExternals := False;
  Doc.preserveWhiteSpace := False;
  Doc.setProperty('ProhibitDTD', True);

  MS := TMemoryStream.Create;   // liberado pelo adaptador (soOwned)
  MS.WriteBuffer(Dados[0], Length(Dados));
  MS.Position := 0;
  Unk := TStreamAdapter.Create(MS, soOwned) as IStream;
  Fonte := Unk;
  if not Doc.load(Fonte) then
    raise EXmlNFe.CreateFmt('XML malformado (linha %d): %s',
      [Doc.parseError.line, Trim(string(Doc.parseError.reason))]);

  Raiz := Doc.documentElement;
  if Raiz = nil then
    raise EXmlNFe.Create('XML sem elemento raiz.');
  NomeRaiz := string(Raiz.baseName);

  if NomeRaiz = 'nfeProc' then
  begin
    NFe := Filho(Raiz, 'NFe');
    Prot := Filho(Raiz, 'protNFe');
  end
  else if NomeRaiz = 'NFe' then
  begin
    NFe := Raiz;
    Prot := nil;
  end
  else if (NomeRaiz = 'procEventoNFe') or (NomeRaiz = 'evento') or (NomeRaiz = 'envEvento') then
    raise EForaEscopo.Create('O arquivo é um EVENTO da NF-e (cancelamento, CC-e, manifestação), não a nota. Fora do escopo desta versão.')
  else if (NomeRaiz = 'resNFe') or (NomeRaiz = 'resEvento') then
    raise EForaEscopo.Create('O arquivo é um RESUMO da NF-e (distribuição DF-e), sem os itens. Baixe o XML completo.')
  else if (NomeRaiz = 'cteProc') or (NomeRaiz = 'CTe') then
    raise EForaEscopo.Create('O arquivo é um CT-e. Esta versão trata somente NF-e de entrada.')
  else
    raise EForaEscopo.Create('Documento não reconhecido como NF-e (raiz: ' + NomeRaiz + ').');

  if NFe = nil then
    raise EXmlNFe.Create('Elemento NFe não encontrado.');
  Inf := Filho(NFe, 'infNFe');
  if Inf = nil then
    raise EXmlNFe.Create('Elemento infNFe não encontrado.');

  Result.Versao := Atributo(Inf, 'versao');
  Result.Chave := Atributo(Inf, 'Id');
  if Result.Chave.StartsWith('NFe') then
    Result.Chave := Copy(Result.Chave, 4, MaxInt);

  Ide := Filho(Inf, 'ide');
  Emit := Filho(Inf, 'emit');
  Dest := Filho(Inf, 'dest');
  if (Ide = nil) or (Emit = nil) then
    raise EXmlNFe.Create('Identificação (ide) ou emitente (emit) ausente.');

  Result.Modelo := Txt(Ide, 'mod');
  if Result.Modelo = '65' then
    raise EForaEscopo.Create('O arquivo é uma NFC-e (modelo 65). Esta versão trata NF-e modelo 55.');
  if Result.Modelo <> '55' then
    raise EForaEscopo.Create('Modelo de documento não suportado: ' + Result.Modelo);

  Result.Serie := Txt(Ide, 'serie');
  Result.Numero := Txt(Ide, 'nNF');
  Result.DataEmissao := Txt(Ide, 'dhEmi');
  if Result.DataEmissao = '' then
    Result.DataEmissao := Txt(Ide, 'dEmi');
  Result.TpNF := Txt(Ide, 'tpNF');
  Result.TpAmb := Txt(Ide, 'tpAmb');
  Result.NatOp := Txt(Ide, 'natOp');

  Result.EmitCNPJ := Txt(Emit, 'CNPJ');
  if Result.EmitCNPJ = '' then
    Result.EmitCNPJ := Txt(Emit, 'CPF');
  Result.EmitNome := Txt(Emit, 'xNome');
  Result.EmitIE := Txt(Emit, 'IE');
  Result.EmitUF := TxtDesc(Emit, 'UF');

  if Dest <> nil then
  begin
    Result.DestCNPJ := Txt(Dest, 'CNPJ');
    if Result.DestCNPJ = '' then
      Result.DestCNPJ := Txt(Dest, 'CPF');
    Result.DestNome := Txt(Dest, 'xNome');
    Result.DestIE := Txt(Dest, 'IE');
  end;

  for I := 0 to Inf.childNodes.length - 1 do
  begin
    Det := Inf.childNodes.item[I];
    if (Integer(Det.nodeType) <> NO_ELEMENTO) or (string(Det.baseName) <> 'det') then
      Continue;
    Prod := Filho(Det, 'prod');
    if Prod = nil then
      raise EXmlNFe.Create('Item sem o grupo prod.');
    It := Default(TItemXML);
    It.NItem := StrToIntDef(Atributo(Det, 'nItem'), Length(Result.Itens) + 1);
    Ctx := 'item ' + IntToStr(It.NItem);
    It.CProd := Txt(Prod, 'cProd');
    It.CEAN := Txt(Prod, 'cEAN');
    It.CEANTrib := Txt(Prod, 'cEANTrib');
    It.XProd := Txt(Prod, 'xProd');
    It.NCM := Txt(Prod, 'NCM');
    It.CEST := Txt(Prod, 'CEST');
    It.CFOP := Txt(Prod, 'CFOP');
    It.UCom := Txt(Prod, 'uCom');
    It.UTrib := Txt(Prod, 'uTrib');
    It.QCom := Num(Txt(Prod, 'qCom'), Ctx + ' qCom');
    It.VUnCom := Num(Txt(Prod, 'vUnCom'), Ctx + ' vUnCom');
    It.VProd := Num(Txt(Prod, 'vProd'), Ctx + ' vProd');
    It.QTrib := Num(Txt(Prod, 'qTrib'), Ctx + ' qTrib');
    It.VUnTrib := Num(Txt(Prod, 'vUnTrib'), Ctx + ' vUnTrib');
    It.VDesc := Num(Txt(Prod, 'vDesc'), Ctx + ' vDesc');
    It.VFrete := Num(Txt(Prod, 'vFrete'), Ctx + ' vFrete');
    It.VSeg := Num(Txt(Prod, 'vSeg'), Ctx + ' vSeg');
    It.VOutro := Num(Txt(Prod, 'vOutro'), Ctx + ' vOutro');
    Imposto := Filho(Det, 'imposto');
    if Imposto <> nil then
    begin
      It.VICMS := Num(TxtDesc(Filho(Imposto, 'ICMS'), 'vICMS'), Ctx + ' vICMS');
      It.VICMSST := Num(TxtDesc(Filho(Imposto, 'ICMS'), 'vICMSST'), Ctx + ' vICMSST');
      It.VIPI := Num(TxtDesc(Filho(Imposto, 'IPI'), 'vIPI'), Ctx + ' vIPI');
    end;
    if It.QCom <= 0 then
      Avisar(Result, Format('Item %d com quantidade comercial zerada.', [It.NItem]));
    SetLength(Result.Itens, Length(Result.Itens) + 1);
    Result.Itens[High(Result.Itens)] := It;
  end;
  if Length(Result.Itens) = 0 then
    raise EXmlNFe.Create('A nota não tem itens (det).');

  Tot := Descendente(Filho(Inf, 'total'), 'ICMSTot');
  Result.VNF := Num(Txt(Tot, 'vNF'), 'total vNF');
  Result.VProdTotal := Num(Txt(Tot, 'vProd'), 'total vProd');
  Result.VICMSTotal := Num(Txt(Tot, 'vICMS'), 'total vICMS');
  Result.VSTTotal := Num(Txt(Tot, 'vST'), 'total vST');
  Result.VIPITotal := Num(Txt(Tot, 'vIPI'), 'total vIPI');

  if Prot <> nil then
  begin
    Result.TemProtocolo := True;
    Result.ChaveProt := TxtDesc(Prot, 'chNFe');
    Result.Protocolo := TxtDesc(Prot, 'nProt');
    Result.CStatProt := TxtDesc(Prot, 'cStat');
    if (Result.CStatProt <> '') and (Result.CStatProt <> '100') and (Result.CStatProt <> '150') then
      Avisar(Result, 'Protocolo com situação ' + Result.CStatProt + ' (não é "autorizado o uso").');
  end
  else
    Avisar(Result, 'XML sem protocolo de autorização (não é o nfeProc). Confirme a autorização antes da entrada.');

  if Result.TpNF = '0' then
    Avisar(Result, 'tpNF = 0: nota de ENTRADA emitida pelo próprio emitente. Confira se é este o documento esperado.');
  if Result.TpAmb = '2' then
    Avisar(Result, 'Nota emitida em ambiente de HOMOLOGAÇÃO (tpAmb = 2), sem valor fiscal.');

  ConferirChave(Result);
end;

function InterpretarNFe(const Dados: TBytes): TNotaXML;
var
  HR: HRESULT;
begin
  HR := CoInitializeEx(nil, COINIT_APARTMENTTHREADED);
  try
    Result := InterpretarInterno(Dados);
  finally
    if (HR = S_OK) or (HR = S_FALSE) then
      CoUninitialize;
  end;
end;

function LerNFeArquivo(const Arquivo: string; out Bytes: TBytes): TNotaXML;
begin
  Bytes := LerBytesArquivo(Arquivo);
  Result := InterpretarNFe(Bytes);
end;

end.
