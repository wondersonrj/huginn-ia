unit uEntrega1321;

{ HUGINN XML Automatico - entrega do XML conferido para a fila da rotina 1321
  (Importacao XML Automatico), que gera a pre-entrada com o motor fiscal do WinThor.

  UNICA unit do projeto que grava no ERP. Grava SOMENTE:
    - 1 linha em PCNFENTXML (XML original, SITUACAO 'A');
    - 1 linha em PCMANIFDESTINATARIO (identificacao da nota, CODIGO pela sequence oficial).
  Nada de impostos, custos ou pre-entrada: isso e feito pela 1321.

  Padrao copiado das linhas reais do cliente (DocFiscal / PCSIS1301-AUTOMATICO) e
  das consultas da 1321/1309 vistas em trace. Ver docs/MATRIZ_CONSULTAS.md.

  Tudo em UM bloco PL/SQL: se qualquer checagem falhar, nada fica gravado.
  Desligado por padrao (HuginnXML.ini, [Opcoes] Entrega1321=1 para ligar). }

interface

uses
  System.SysUtils, Uni, uTipos;

type
  TResultadoEntrega = record
    Ok: Boolean;
    Mensagem: string;
  end;

  TSituacao1321 = record
    Encontrado: Boolean;
    Situacao: string;      // A = aguardando, P = processando, F = falha (visto na 1309)
    Tentativas: Integer;
    NumTransEnt: string;
    LogProcesso: string;
    TemPreEntrada: Boolean;
    TransPreEntrada: string;
  end;

function TextoDoXml(const Bytes: TBytes): string;
function EnviarPara1321(Conn: TUniConnection; const Owner: string; const Nota: TNotaXML;
  const Bytes: TBytes; const CodFilial: string; CodFunc: Integer): TResultadoEntrega;
function ConsultarSituacao1321(Conn: TUniConnection; const Owner, Chave: string): TSituacao1321;

const
  PROGRAMA_HUGINN = 'HUGINN-XML';
  TAM_BLOCO = 4000;   // caracteres por bind do CLOB

implementation

uses
  System.Classes, System.Math, System.StrUtils, System.DateUtils, Data.DB, uValidacao, uConfig;

function Prefixo(const Owner: string): string;
begin
  if Trim(Owner) = '' then
    Result := ''
  else if IdentificadorValido(UpperCase(Trim(Owner))) then
    Result := UpperCase(Trim(Owner)) + '.'
  else
    raise Exception.Create('Schema (owner) inválido.');
end;

{ Converte os bytes recebidos em texto respeitando a codificacao declarada.
  O banco do cliente e WE8MSWIN1252: o WinThor grava o XML como texto, e o
  HUGINN faz o mesmo. O SHA-256 do arquivo original fica no log. }
function TextoDoXml(const Bytes: TBytes): string;
var
  Inicio: string;
  Enc: TEncoding;
  Ini: Integer;
begin
  Ini := 0;
  if (Length(Bytes) >= 3) and (Bytes[0] = $EF) and (Bytes[1] = $BB) and (Bytes[2] = $BF) then
    Ini := 3;  // BOM UTF-8
  Inicio := LowerCase(TEncoding.ASCII.GetString(Bytes, Ini, Min(200, Length(Bytes) - Ini)));
  if ContainsText(Inicio, 'iso-8859-1') or ContainsText(Inicio, 'windows-1252') then
  begin
    Enc := TEncoding.GetEncoding(1252);
    try
      Result := Enc.GetString(Bytes, Ini, Length(Bytes) - Ini);
    finally
      Enc.Free;
    end;
  end
  else
    Result := TEncoding.UTF8.GetString(Bytes, Ini, Length(Bytes) - Ini);
end;

function DataEmissao(const Nota: TNotaXML): TDateTime;
var
  Y, M, D: Word;
begin
  // dhEmi = AAAA-MM-DDThh:mm:ss-03:00 ; usa so a data
  Y := StrToIntDef(Copy(Nota.DataEmissao, 1, 4), 0);
  M := StrToIntDef(Copy(Nota.DataEmissao, 6, 2), 0);
  D := StrToIntDef(Copy(Nota.DataEmissao, 9, 2), 0);
  if not TryEncodeDate(Y, M, D, Result) then
    raise Exception.Create('Data de emissão inválida no XML: ' + Nota.DataEmissao);
end;

function EnviarPara1321(Conn: TUniConnection; const Owner: string; const Nota: TNotaXML;
  const Bytes: TBytes; const CodFilial: string; CodFunc: Integer): TResultadoEntrega;
var
  P, Texto, SQL, Blocos: string;
  Q: TUniQuery;
  I, N: Integer;
begin
  Result := Default(TResultadoEntrega);
  if not ChaveNFeValida(Nota.Chave) then
    raise Exception.Create('Chave inválida.');
  if Trim(CodFilial) = '' then
    raise Exception.Create('Filial não confirmada: confirme a filial antes de enviar.');
  if CodFunc <= 0 then
    raise Exception.Create('Matrícula (CODFUNC) não configurada.');
  P := Prefixo(Owner);
  Texto := TextoDoXml(Bytes);
  N := (Length(Texto) + TAM_BLOCO - 1) div TAM_BLOCO;
  Blocos := '';
  for I := 0 to N - 1 do
    Blocos := Blocos + '  V_B := :B' + IntToStr(I) + '; DBMS_LOB.WRITEAPPEND(V_XML, LENGTH(V_B), V_B);' + sLineBreak;

  // Cada bind aparece uma unica vez: os valores vao para variaveis locais.
  SQL :=
    'DECLARE' + sLineBreak +
    '  V_XML CLOB; V_N NUMBER; V_B VARCHAR2(32767);' + sLineBreak +
    '  V_CHAVE VARCHAR2(44) := :CHAVE; V_FIL VARCHAR2(2) := :FIL; V_CNPJ VARCHAR2(18) := :CNPJ;' + sLineBreak +
    '  V_NUM NUMBER := :NUMNOTA; V_SERIE VARCHAR2(3) := :SERIE; V_EMI DATE := :DTEMISSAO;' + sLineBreak +
    '  V_FUNC NUMBER := :CODFUNC; V_NAT VARCHAR2(60) := :NATOP; V_IE VARCHAR2(14) := :IE;' + sLineBreak +
    '  V_NOME VARCHAR2(60) := :NOME; V_TPNF NUMBER := :TPNF; V_VL NUMBER := :VLTOTAL;' + sLineBreak +
    '  V_PROG VARCHAR2(64) := :PROGRAMA;' + sLineBreak +
    'BEGIN' + sLineBreak +
    '  SELECT COUNT(*) INTO V_N FROM ' + P + 'PCNFENTXML WHERE CHAVENFE = V_CHAVE;' + sLineBreak +
    '  IF V_N > 0 THEN RAISE_APPLICATION_ERROR(-20001, ''HUGINN: XML desta chave já está na PCNFENTXML.''); END IF;' + sLineBreak +
    '  SELECT COUNT(*) INTO V_N FROM ' + P + 'PCMANIFDESTINATARIO WHERE CHAVENFE = V_CHAVE AND CODFILIAL = V_FIL;' + sLineBreak +
    '  IF V_N > 0 THEN RAISE_APPLICATION_ERROR(-20002, ''HUGINN: chave já existe na PCMANIFDESTINATARIO.''); END IF;' + sLineBreak +
    '  SELECT COUNT(*) INTO V_N FROM ' + P + 'PCNFENTPREENT WHERE CHAVENFE = V_CHAVE;' + sLineBreak +
    '  IF V_N > 0 THEN RAISE_APPLICATION_ERROR(-20003, ''HUGINN: já existe pré-entrada desta chave.''); END IF;' + sLineBreak +
    '  SELECT COUNT(*) INTO V_N FROM ' + P + 'PCNFENT WHERE CHAVENFE = V_CHAVE AND DTCANCEL IS NULL;' + sLineBreak +
    '  IF V_N > 0 THEN RAISE_APPLICATION_ERROR(-20004, ''HUGINN: nota já lançada.''); END IF;' + sLineBreak +
    '  DBMS_LOB.CREATETEMPORARY(V_XML, TRUE);' + sLineBreak +
    Blocos +
    '  INSERT INTO ' + P + 'PCNFENTXML (CNPJ, NUMNOTA, SERIE, DTEMISSAO, DADOSXML, DATA, CODFUNC,' + sLineBreak +
    '    CHAVENFE, SITUACAO, DTCADASTRO, TENTATIVAS, NATOPERNFE)' + sLineBreak +
    '  VALUES (V_CNPJ, V_NUM, V_SERIE, V_EMI, V_XML, SYSDATE, V_FUNC, V_CHAVE, ''A'', SYSDATE, 0, V_NAT);' + sLineBreak +
    '  INSERT INTO ' + P + 'PCMANIFDESTINATARIO (CODIGO, TIPODOCUMENTO, DATARECEBDOCUMENTO, CODFILIAL, UF,' + sLineBreak +
    '    CNPJCPF, IE, NOME, CHAVENFE, DATAEMISSAO, TIPONOTA, FINALIDADENFE, SITUACAONFE, SITCONFIRMACAODEST,' + sLineBreak +
    '    VLTOTALNFE, FEZDOWNLOADXML, AMBIENTE, MAQUINA, PROGRAMA, USUARIO)' + sLineBreak +
    '  SELECT ' + P + 'DFSEQ_PCMANIFDESTINATARIO.NEXTVAL, 0, SYSDATE, V_FIL, F.UF, V_CNPJ, V_IE, V_NOME,' + sLineBreak +
    '    V_CHAVE, V_EMI, V_TPNF, 0, 1, 4, V_VL, ''S'', ''P'', SYS_CONTEXT(''USERENV'', ''HOST''), V_PROG, USER' + sLineBreak +
    '    FROM ' + P + 'PCFILIAL F WHERE F.CODIGO = V_FIL;' + sLineBreak +
    '  IF SQL%ROWCOUNT <> 1 THEN RAISE_APPLICATION_ERROR(-20005, ''HUGINN: filial não encontrada.''); END IF;' + sLineBreak +
    '  DBMS_LOB.FREETEMPORARY(V_XML);' + sLineBreak +
    'END;';

  Q := TUniQuery.Create(nil);
  try
    Q.Connection := Conn;
    Q.SQL.Text := SQL;
    Q.ParamByName('CHAVE').AsString := Nota.Chave;
    Q.ParamByName('FIL').AsString := CodFilial;
    Q.ParamByName('CNPJ').AsString := SoDigitos(Nota.EmitCNPJ);
    Q.ParamByName('NUMNOTA').AsLargeInt := StrToInt64(Nota.Numero);
    Q.ParamByName('SERIE').AsString := Nota.Serie;
    Q.ParamByName('DTEMISSAO').AsDateTime := DataEmissao(Nota);
    Q.ParamByName('CODFUNC').AsInteger := CodFunc;
    Q.ParamByName('NATOP').AsString := Copy(Nota.NatOp, 1, 60);
    Q.ParamByName('IE').AsString := Copy(Nota.EmitIE, 1, 14);
    Q.ParamByName('NOME').AsString := Copy(Nota.EmitNome, 1, 60);
    Q.ParamByName('TPNF').AsInteger := StrToIntDef(Nota.TpNF, 1);
    Q.ParamByName('VLTOTAL').AsFloat := Nota.VNF;
    Q.ParamByName('PROGRAMA').AsString := PROGRAMA_HUGINN;
    for I := 0 to N - 1 do
      Q.ParamByName('B' + IntToStr(I)).AsString := Copy(Texto, I * TAM_BLOCO + 1, TAM_BLOCO);
    Conn.StartTransaction;
    try
      Q.Execute;
      Conn.Commit;
    except
      Conn.Rollback;
      raise;
    end;
    Result.Ok := True;
    Result.Mensagem := Format('XML enviado para a fila da 1321 (%d caracteres em %d bloco(s)).', [Length(Texto), N]);
  finally
    Q.Free;
  end;
end;

function ConsultarSituacao1321(Conn: TUniConnection; const Owner, Chave: string): TSituacao1321;
var
  P: string;
  Q: TUniQuery;
begin
  Result := Default(TSituacao1321);
  P := Prefixo(Owner);
  Q := TUniQuery.Create(nil);
  try
    Q.Connection := Conn;
    Q.SQL.Text := 'SELECT NVL(SITUACAO, ''A'') SITUACAO, NVL(TENTATIVAS, 0) TENTATIVAS, NUMTRANSENT, ' +
      'DBMS_LOB.SUBSTR(LOG_PROCESS, 3000, 1) LOG_PROCESS FROM ' + P + 'PCNFENTXML WHERE CHAVENFE = :CHAVE';
    Q.ParamByName('CHAVE').AsString := Chave;
    Q.Open;
    if not Q.Eof then
    begin
      Result.Encontrado := True;
      Result.Situacao := Q.FieldByName('SITUACAO').AsString;
      Result.Tentativas := Q.FieldByName('TENTATIVAS').AsInteger;
      Result.NumTransEnt := Q.FieldByName('NUMTRANSENT').AsString;
      Result.LogProcesso := Q.FieldByName('LOG_PROCESS').AsString;
    end;
    Q.Close;
    Q.SQL.Text := 'SELECT NUMTRANSENT FROM ' + P + 'PCNFENTPREENT WHERE CHAVENFE = :CHAVE AND ROWNUM = 1';
    Q.ParamByName('CHAVE').AsString := Chave;
    Q.Open;
    if not Q.Eof then
    begin
      Result.TemPreEntrada := True;
      Result.TransPreEntrada := Q.FieldByName('NUMTRANSENT').AsString;
    end;
  finally
    Q.Free;
  end;
end;

end.
