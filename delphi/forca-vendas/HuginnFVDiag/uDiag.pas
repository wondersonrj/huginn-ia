unit uDiag;

{ HUGINN IA - Forca de Vendas - Diagnostico v0.1 (SOMENTE LEITURA)

  Objetivo: confirmar no banco do cliente, sem gravar nada, a estrutura da
  integradora do WinThor (PCPEDCFV / PCPEDIFV / PCCLIENTFV e demais tabelas
  PC*FV*) e das tabelas que o app vai ler (produtos, precos, estoque, clientes,
  RCA), e como o forca de vendas atual usa a integradora hoje.

  Regras:
  - Toda instrucao executada passa por SqlSomenteLeitura (so SELECT / WITH).
  - Nomes de tabelas candidatas NAO sao assumidos como existentes: o diagnostico
    apenas verifica se existem e registra "existe / nao existe".
  - Amostras de dados sao opcionais (LGPD). }

interface

uses
  System.SysUtils, System.Classes, System.Generics.Collections, Data.DB, Uni;

const
  VERSAO_DIAG = '0.1';

type
  TLogProc = reference to procedure(const AMsg: string);

  TColunaInfo = record
    Tabela, Coluna, Tipo: string;
  end;

  TFVDiagnostico = class
  private
    FConn: TUniConnection;
    FOwner: string;
    FServidor: string;
    FLog: TLogProc;
    FDir: string;
    FManifesto: TStringList;
    FErros: Integer;
    FExistentes: TStringList;   // tabelas/views encontradas (Name=tipo)
    FIntegradora: TStringList;  // subconjunto PC*FV*
    FColunasFV: TList<TColunaInfo>;
    FAmostraPedidos: Boolean;
    FAmostraClientes: Boolean;
    procedure Log(const S: string);
    function Q(const S: string): string;
    function ListaIn(AList: TStrings): string;
    function NovaQuery(const ASQL: string): TUniQuery;
    function Exportar(const AArquivo, ADescricao, ASQL: string): Integer;
    procedure Coletar(const ASQL, APrefixo: string; ADestino: TStrings);
    procedure GravarCsv(const AArquivo, ADescricao: string; ALinhas: TStrings);
    procedure Ambiente;
    procedure LocalizarTabelas;
    procedure Dicionario;
    procedure UsoDaIntegradora;
    procedure CarregarColunasFV;
    procedure PerfilIntegradora;
    procedure Amostras;
    procedure GravarManifesto(AInicio: TDateTime);
  public
    constructor Create(AConn: TUniConnection; const AOwner, AServidor: string;
      ALog: TLogProc);
    destructor Destroy; override;
    function Executar(const APastaBase: string): string; // retorna o ZIP
    property AmostraPedidos: Boolean read FAmostraPedidos write FAmostraPedidos;
    property AmostraClientes: Boolean read FAmostraClientes write FAmostraClientes;
    property Erros: Integer read FErros;
  end;

function SqlSomenteLeitura(const ASQL: string): Boolean;

implementation

uses
  System.IOUtils, System.Zip, System.StrUtils, System.DateUtils,
  System.RegularExpressions;

const
  // Confirmadas em documentacao TDN / uso no WinThor (ver skill HUGINN)
  TAB_CONFIRMADAS: array[0..12] of string = (
    'PCPEDCFV', 'PCPEDIFV', 'PCCLIENTFV',
    'PCPEDC', 'PCPEDI', 'PCCLIENT', 'PCPRODUT', 'PCPRODFILIAL',
    'PCEMBALAGEM', 'PCTABTRIB', 'PCEMPR', 'PCUSUARI', 'PCNFSAID');

  // Candidatas: o diagnostico so VERIFICA se existem. Nada e assumido.
  TAB_CANDIDATAS: array[0..16] of string = (
    'PCTABPR', 'PCEST', 'PCPREST', 'PCPRACA', 'PCREGIAO', 'PCFILIAL',
    'PCPLPAG', 'PCCOB', 'PCMETA', 'PCMETARCA', 'PCSUPERV', 'PCATIVI',
    'PCCIDADE', 'PCDEPTO', 'PCSECAO', 'PCMARCA', 'PCFORNEC');

  // Pedacos de nome de coluna que costumam indicar status/erro (heuristica
  // so para escolher quais colunas perfilar; as colunas vem do dicionario).
  PISTAS_STATUS: array[0..13] of string = (
    'STATUS', 'IMPORT', 'INTEGR', 'ORIGEM', 'SITUAC', 'POSICAO', 'TIPO',
    'ERRO', 'CRITICA', 'MOTIVO', 'MENSAGEM', 'OBSERVACAO_PC', 'PROCESS', 'ENVIO');

  MAX_LINHAS_FONTE = 5000;
  MAX_AMOSTRA = 50;

{ utilitarios }

function SqlSomenteLeitura(const ASQL: string): Boolean;
var
  S: string;
begin
  S := UpperCase(TrimLeft(ASQL));
  Result := (StartsStr('SELECT', S) or StartsStr('WITH', S)) and
    (Pos(';', S) = 0);
end;

function CsvCampo(const S: string): string;
begin
  Result := '"' + StringReplace(S, '"', '""', [rfReplaceAll]) + '"';
end;

function ValorCampo(F: TField): string;
begin
  if F.IsNull then
    Exit('');
  case F.DataType of
    ftDate, ftDateTime, ftTimeStamp, ftOraTimeStamp:
      Result := FormatDateTime('yyyy-mm-dd hh:nn:ss', F.AsDateTime);
    ftFloat, ftBCD, ftFMTBcd, ftExtended, ftCurrency, ftSingle:
      Result := StringReplace(F.AsString, FormatSettings.DecimalSeparator, '.', []);
    ftBlob, ftOraBlob, ftBytes, ftVarBytes, ftGraphic:
      Result := '[binario]';
  else
    Result := F.AsString;
  end;
end;

function UmaLinha(const S: string): string;
begin
  Result := StringReplace(StringReplace(S, #13, ' ', [rfReplaceAll]), #10, ' ',
    [rfReplaceAll]);
end;

{ TFVDiagnostico }

constructor TFVDiagnostico.Create(AConn: TUniConnection; const AOwner,
  AServidor: string; ALog: TLogProc);
begin
  inherited Create;
  FConn := AConn;
  FOwner := UpperCase(AOwner);
  FServidor := AServidor;
  FLog := ALog;
  FManifesto := TStringList.Create;
  FExistentes := TStringList.Create;
  FExistentes.Sorted := True;
  FExistentes.Duplicates := dupIgnore;
  FIntegradora := TStringList.Create;
  FIntegradora.Sorted := True;
  FIntegradora.Duplicates := dupIgnore;
  FColunasFV := TList<TColunaInfo>.Create;
  FAmostraPedidos := True;
  FAmostraClientes := False;
end;

destructor TFVDiagnostico.Destroy;
begin
  FColunasFV.Free;
  FIntegradora.Free;
  FExistentes.Free;
  FManifesto.Free;
  inherited;
end;

procedure TFVDiagnostico.Log(const S: string);
begin
  if Assigned(FLog) then
    FLog(S);
end;

function TFVDiagnostico.Q(const S: string): string;
begin
  Result := QuotedStr(S);
end;

function TFVDiagnostico.ListaIn(AList: TStrings): string;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to AList.Count - 1 do
  begin
    if Result <> '' then
      Result := Result + ',';
    Result := Result + Q(AList[I]);
  end;
  if Result = '' then
    Result := Q('#NENHUMA#');
end;

function TFVDiagnostico.NovaQuery(const ASQL: string): TUniQuery;
begin
  if not SqlSomenteLeitura(ASQL) then
    raise Exception.Create('Bloqueado pela HUGINN: instrucao nao e consulta (SELECT).');
  Result := TUniQuery.Create(nil);
  Result.Connection := FConn;
  Result.ReadOnly := True;
  Result.UniDirectional := True;
  Result.SQL.Text := ASQL;
end;

function TFVDiagnostico.Exportar(const AArquivo, ADescricao, ASQL: string): Integer;
var
  Qry: TUniQuery;
  W: TStreamWriter;
  Linha: TStringBuilder;
  I: Integer;
  T0: TDateTime;
begin
  Result := 0;
  T0 := Now;
  Log('> ' + AArquivo + ' - ' + ADescricao);
  try
    Qry := NovaQuery(ASQL);
    try
      Qry.Open;
      W := TStreamWriter.Create(TPath.Combine(FDir, AArquivo), False, TEncoding.UTF8);
      Linha := TStringBuilder.Create;
      try
        for I := 0 to Qry.FieldCount - 1 do
        begin
          if I > 0 then
            Linha.Append(';');
          Linha.Append(CsvCampo(Qry.Fields[I].FieldName));
        end;
        W.WriteLine(Linha.ToString);
        while not Qry.Eof do
        begin
          Linha.Clear;
          for I := 0 to Qry.FieldCount - 1 do
          begin
            if I > 0 then
              Linha.Append(';');
            Linha.Append(CsvCampo(ValorCampo(Qry.Fields[I])));
          end;
          W.WriteLine(Linha.ToString);
          Inc(Result);
          Qry.Next;
        end;
      finally
        Linha.Free;
        W.Free;
      end;
    finally
      Qry.Free;
    end;
    Log(Format('  ok: %d linha(s) em %d s', [Result, SecondsBetween(Now, T0)]));
    FManifesto.Add(Format('%s;%d;OK;%s', [AArquivo, Result, ADescricao]));
  except
    on E: Exception do
    begin
      Inc(FErros);
      Log('  ERRO: ' + UmaLinha(E.Message));
      FManifesto.Add(Format('%s;0;ERRO: %s;%s',
        [AArquivo, UmaLinha(E.Message), ADescricao]));
      Result := -1;
    end;
  end;
end;

procedure TFVDiagnostico.Coletar(const ASQL, APrefixo: string; ADestino: TStrings);
var
  Qry: TUniQuery;
  Linha: TStringBuilder;
  I: Integer;
begin
  try
    Qry := NovaQuery(ASQL);
    Linha := TStringBuilder.Create;
    try
      Qry.Open;
      while not Qry.Eof do
      begin
        Linha.Clear;
        Linha.Append(APrefixo);
        for I := 0 to Qry.FieldCount - 1 do
          Linha.Append(';').Append(CsvCampo(ValorCampo(Qry.Fields[I])));
        ADestino.Add(Linha.ToString);
        Qry.Next;
      end;
    finally
      Linha.Free;
      Qry.Free;
    end;
  except
    on E: Exception do
    begin
      Inc(FErros);
      Log('  ERRO: ' + UmaLinha(E.Message));
      ADestino.Add(APrefixo + ';' + CsvCampo('ERRO: ' + UmaLinha(E.Message)));
    end;
  end;
end;

procedure TFVDiagnostico.GravarCsv(const AArquivo, ADescricao: string;
  ALinhas: TStrings);
begin
  ALinhas.WriteBOM := True;
  ALinhas.SaveToFile(TPath.Combine(FDir, AArquivo), TEncoding.UTF8);
  FManifesto.Add(Format('%s;%d;OK;%s', [AArquivo, ALinhas.Count - 1, ADescricao]));
  Log(Format('> %s - %s: %d linha(s)', [AArquivo, ADescricao, ALinhas.Count - 1]));
end;

procedure TFVDiagnostico.Ambiente;
begin
  Exportar('00_ambiente.csv', 'Sessao e banco',
    'SELECT SYS_CONTEXT(''USERENV'',''DB_NAME'') AS DB_NAME, ' +
    'SYS_CONTEXT(''USERENV'',''SERVICE_NAME'') AS SERVICE_NAME, ' +
    'SYS_CONTEXT(''USERENV'',''SESSION_USER'') AS SESSION_USER, ' +
    'SYS_CONTEXT(''USERENV'',''CURRENT_SCHEMA'') AS CURRENT_SCHEMA, ' +
    'SYS_CONTEXT(''USERENV'',''LANGUAGE'') AS NLS_LANGUAGE, ' +
    'TO_CHAR(SYSDATE,''YYYY-MM-DD HH24:MI:SS'') AS DATA_HORA_BANCO, ' +
    'DBTIMEZONE AS DB_TIMEZONE FROM DUAL');
  Exportar('00_versao_oracle.csv', 'Versao do Oracle (pode falhar sem privilegio)',
    'SELECT BANNER FROM V$VERSION');
  Exportar('00_nls.csv', 'Parametros NLS do banco',
    'SELECT PARAMETER, VALUE FROM NLS_DATABASE_PARAMETERS ' +
    'WHERE PARAMETER IN (''NLS_CHARACTERSET'',''NLS_NCHAR_CHARACTERSET'',' +
    '''NLS_NUMERIC_CHARACTERS'',''NLS_DATE_FORMAT'',''NLS_LANGUAGE'',''NLS_TERRITORY'')');
end;

procedure TFVDiagnostico.LocalizarTabelas;
var
  Alvos, Linhas: TStringList;
  Qry: TUniQuery;
  I: Integer;
  Nome, Origem, Info: string;
  Info2: TStringList;

  function Origem_(const N: string): string;
  var
    S: string;
  begin
    for S in TAB_CONFIRMADAS do
      if S = N then
        Exit('confirmada');
    for S in TAB_CANDIDATAS do
      if S = N then
        Exit('candidata');
    Result := 'descoberta (PC*FV*)';
  end;

begin
  Alvos := TStringList.Create;
  Linhas := TStringList.Create;
  Info2 := TStringList.Create;
  try
    for Nome in TAB_CONFIRMADAS do
      Alvos.Add(Nome);
    for Nome in TAB_CANDIDATAS do
      Alvos.Add(Nome);

    Log('> Localizando tabelas no schema ' + FOwner + ' ...');
    try
      Qry := NovaQuery(
        'SELECT O.OBJECT_NAME, O.OBJECT_TYPE, O.STATUS, T.NUM_ROWS, ' +
        'TO_CHAR(T.LAST_ANALYZED,''YYYY-MM-DD'') AS LAST_ANALYZED ' +
        'FROM ALL_OBJECTS O LEFT JOIN ALL_TABLES T ' +
        '  ON T.OWNER = O.OWNER AND T.TABLE_NAME = O.OBJECT_NAME ' +
        'WHERE O.OWNER = ' + Q(FOwner) +
        ' AND O.OBJECT_TYPE IN (''TABLE'',''VIEW'') ' +
        ' AND (O.OBJECT_NAME IN (' + ListaIn(Alvos) + ') ' +
        '      OR O.OBJECT_NAME LIKE ''PC%FV%'') ' +
        'ORDER BY O.OBJECT_NAME');
      try
        Qry.Open;
        while not Qry.Eof do
        begin
          Nome := Qry.Fields[0].AsString;
          FExistentes.Add(Nome);
          Info2.Values[Nome] := Qry.Fields[1].AsString + ';' +
            CsvCampo(Qry.Fields[2].AsString) + ';' +
            CsvCampo(Qry.Fields[3].AsString) + ';' +
            CsvCampo(Qry.Fields[4].AsString);
          if StartsStr('PC', Nome) and (Pos('FV', Nome) > 2) and
            TRegEx.IsMatch(Nome, '^[A-Z][A-Z0-9_$#]{0,127}$') then
            FIntegradora.Add(Nome);
          if Alvos.IndexOf(Nome) < 0 then
            Alvos.Add(Nome);
          Qry.Next;
        end;
      finally
        Qry.Free;
      end;
    except
      on E: Exception do
      begin
        Inc(FErros);
        Log('  ERRO ao localizar tabelas: ' + UmaLinha(E.Message));
      end;
    end;

    Linhas.Add('"TABELA";"ORIGEM";"EXISTE";"TIPO";"STATUS";"NUM_ROWS_ESTATISTICA";"LAST_ANALYZED"');
    for I := 0 to Alvos.Count - 1 do
    begin
      Nome := Alvos[I];
      Origem := Origem_(Nome);
      if FExistentes.IndexOf(Nome) >= 0 then
      begin
        Info := Info2.Values[Nome];
        Linhas.Add(CsvCampo(Nome) + ';' + CsvCampo(Origem) + ';"S";' + Info);
      end
      else
        Linhas.Add(CsvCampo(Nome) + ';' + CsvCampo(Origem) + ';"N";"";"";"";""');
    end;
    GravarCsv('01_tabelas_alvo.csv', 'Tabelas verificadas (existe S/N)', Linhas);
    Log(Format('  %d tabela(s)/view(s) encontrada(s); integradora: %s',
      [FExistentes.Count, IfThen(FIntegradora.Count = 0, 'NENHUMA', FIntegradora.CommaText)]));
  finally
    Info2.Free;
    Linhas.Free;
    Alvos.Free;
  end;
end;

procedure TFVDiagnostico.Dicionario;
var
  W, O: string;
begin
  O := Q(FOwner);
  W := ListaIn(FExistentes);

  Exportar('02_colunas.csv', 'Colunas + comentarios',
    'SELECT C.TABLE_NAME, C.COLUMN_ID, C.COLUMN_NAME, C.DATA_TYPE, C.DATA_LENGTH, ' +
    'C.DATA_PRECISION, C.DATA_SCALE, C.NULLABLE, C.DATA_DEFAULT, CC.COMMENTS ' +
    'FROM ALL_TAB_COLUMNS C LEFT JOIN ALL_COL_COMMENTS CC ' +
    '  ON CC.OWNER = C.OWNER AND CC.TABLE_NAME = C.TABLE_NAME AND CC.COLUMN_NAME = C.COLUMN_NAME ' +
    'WHERE C.OWNER = ' + O + ' AND C.TABLE_NAME IN (' + W + ') ' +
    'ORDER BY C.TABLE_NAME, C.COLUMN_ID');

  Exportar('03_comentarios_tabelas.csv', 'Comentarios das tabelas',
    'SELECT TABLE_NAME, TABLE_TYPE, COMMENTS FROM ALL_TAB_COMMENTS ' +
    'WHERE OWNER = ' + O + ' AND TABLE_NAME IN (' + W + ') ORDER BY TABLE_NAME');

  Exportar('04_constraints.csv', 'PK, FK, unique e check',
    'SELECT K.TABLE_NAME, K.CONSTRAINT_NAME, K.CONSTRAINT_TYPE, K.STATUS, ' +
    'CC.COLUMN_NAME, CC.POSITION, R.TABLE_NAME AS TABELA_REFERENCIADA, ' +
    'K.R_CONSTRAINT_NAME, K.DELETE_RULE, K.SEARCH_CONDITION ' +
    'FROM ALL_CONSTRAINTS K ' +
    'JOIN ALL_CONS_COLUMNS CC ON CC.OWNER = K.OWNER AND CC.CONSTRAINT_NAME = K.CONSTRAINT_NAME ' +
    '  AND CC.TABLE_NAME = K.TABLE_NAME ' +
    'LEFT JOIN ALL_CONSTRAINTS R ON R.OWNER = K.R_OWNER AND R.CONSTRAINT_NAME = K.R_CONSTRAINT_NAME ' +
    'WHERE K.OWNER = ' + O + ' AND K.TABLE_NAME IN (' + W + ') ' +
    'ORDER BY K.TABLE_NAME, K.CONSTRAINT_TYPE, K.CONSTRAINT_NAME, CC.POSITION');

  Exportar('05_indices.csv', 'Indices e colunas',
    'SELECT I.TABLE_NAME, I.INDEX_NAME, I.UNIQUENESS, I.INDEX_TYPE, I.STATUS, ' +
    'IC.COLUMN_NAME, IC.COLUMN_POSITION, IC.DESCEND ' +
    'FROM ALL_INDEXES I JOIN ALL_IND_COLUMNS IC ' +
    '  ON IC.INDEX_OWNER = I.OWNER AND IC.INDEX_NAME = I.INDEX_NAME ' +
    'WHERE I.TABLE_OWNER = ' + O + ' AND I.TABLE_NAME IN (' + W + ') ' +
    'ORDER BY I.TABLE_NAME, I.INDEX_NAME, IC.COLUMN_POSITION');

  Exportar('06_triggers.csv', 'Triggers (com corpo)',
    'SELECT TABLE_NAME, OWNER, TRIGGER_NAME, TRIGGER_TYPE, TRIGGERING_EVENT, ' +
    'STATUS, WHEN_CLAUSE, TRIGGER_BODY FROM ALL_TRIGGERS ' +
    'WHERE TABLE_OWNER = ' + O + ' AND TABLE_NAME IN (' + W + ') ' +
    'ORDER BY TABLE_NAME, TRIGGER_NAME');

  Exportar('07_sequencias.csv', 'Sequences do schema (numeracao)',
    'SELECT SEQUENCE_NAME, MIN_VALUE, MAX_VALUE, INCREMENT_BY, CYCLE_FLAG, ' +
    'CACHE_SIZE, LAST_NUMBER FROM ALL_SEQUENCES WHERE SEQUENCE_OWNER = ' + O +
    ' ORDER BY SEQUENCE_NAME');
end;

procedure TFVDiagnostico.UsoDaIntegradora;
var
  O, W, Filtro: string;
  I: Integer;
begin
  O := Q(FOwner);
  W := ListaIn(FIntegradora);

  Exportar('08_dependencias_integradora.csv',
    'Objetos (packages, procedures, views, triggers) que usam a integradora',
    'SELECT OWNER, NAME, TYPE, REFERENCED_NAME, REFERENCED_TYPE, DEPENDENCY_TYPE ' +
    'FROM ALL_DEPENDENCIES WHERE REFERENCED_OWNER = ' + O +
    ' AND REFERENCED_NAME IN (' + W + ') ' +
    'ORDER BY REFERENCED_NAME, TYPE, NAME');

  // Linhas de codigo PL/SQL que citam as tabelas da integradora
  Filtro := '';
  for I := 0 to FIntegradora.Count - 1 do
  begin
    if Filtro <> '' then
      Filtro := Filtro + ' OR ';
    Filtro := Filtro + 'UPPER(TEXT) LIKE ' + Q('%' + FIntegradora[I] + '%');
  end;
  if Filtro <> '' then
    Exportar('09_fonte_cita_integradora.csv',
      Format('Linhas de PL/SQL que citam a integradora (max %d)', [MAX_LINHAS_FONTE]),
      'SELECT * FROM (SELECT OWNER, NAME, TYPE, LINE, TEXT FROM ALL_SOURCE ' +
      'WHERE (' + Filtro + ') ORDER BY OWNER, NAME, TYPE, LINE) ' +
      'WHERE ROWNUM <= ' + IntToStr(MAX_LINHAS_FONTE))
  else
    Log('  integradora nao encontrada: fonte PL/SQL nao pesquisada');

  Exportar('10_jobs_scheduler.csv', 'Jobs do Scheduler (rotinas automaticas)',
    'SELECT OWNER, JOB_NAME, JOB_TYPE, JOB_ACTION, REPEAT_INTERVAL, ENABLED, ' +
    'STATE, LAST_START_DATE, NEXT_RUN_DATE, FAILURE_COUNT FROM ALL_SCHEDULER_JOBS ' +
    'ORDER BY OWNER, JOB_NAME');
  Exportar('10_jobs_antigos.csv', 'Jobs DBMS_JOB',
    'SELECT JOB, LOG_USER, SCHEMA_USER, WHAT, INTERVAL, LAST_DATE, NEXT_DATE, ' +
    'BROKEN, FAILURES FROM ALL_JOBS ORDER BY JOB');
end;

procedure TFVDiagnostico.CarregarColunasFV;
var
  Qry: TUniQuery;
  C: TColunaInfo;
begin
  FColunasFV.Clear;
  if FIntegradora.Count = 0 then
    Exit;
  try
    Qry := NovaQuery(
      'SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS ' +
      'WHERE OWNER = ' + Q(FOwner) + ' AND TABLE_NAME IN (' + ListaIn(FIntegradora) + ') ' +
      'ORDER BY TABLE_NAME, COLUMN_ID');
    try
      Qry.Open;
      while not Qry.Eof do
      begin
        C.Tabela := Qry.Fields[0].AsString;
        C.Coluna := Qry.Fields[1].AsString;
        C.Tipo := Qry.Fields[2].AsString;
        FColunasFV.Add(C);
        Qry.Next;
      end;
    finally
      Qry.Free;
    end;
  except
    on E: Exception do
    begin
      Inc(FErros);
      Log('  ERRO ao ler colunas da integradora: ' + UmaLinha(E.Message));
    end;
  end;
end;

procedure TFVDiagnostico.PerfilIntegradora;
var
  Datas, Valores: TStringList;
  C: TColunaInfo;
  P, Tab, Col: string;
  EhPista: Boolean;
begin
  if FIntegradora.Count = 0 then
    Exit;
  Datas := TStringList.Create;
  Valores := TStringList.Create;
  try
    Datas.Add('"TABELA";"COLUNA";"QTD_LINHAS_OU_NAO_NULAS";"MENOR";"MAIOR"');
    Valores.Add('"TABELA";"COLUNA";"VALOR";"QTD"');

    for Tab in FIntegradora do
    begin
      Log('> Perfil de ' + Tab + ' ...');
      Coletar('SELECT COUNT(*), NULL, NULL FROM ' + FOwner + '.' + Tab,
        CsvCampo(Tab) + ';"*"', Datas);
    end;

    for C in FColunasFV do
    begin
      Tab := C.Tabela;
      Col := C.Coluna;
      if (C.Tipo = 'DATE') or StartsStr('TIMESTAMP', C.Tipo) then
        Coletar(Format('SELECT COUNT(%0:s), TO_CHAR(MIN(%0:s),''YYYY-MM-DD HH24:MI:SS''), ' +
          'TO_CHAR(MAX(%0:s),''YYYY-MM-DD HH24:MI:SS'') FROM %1:s.%2:s',
          ['"' + Col + '"', FOwner, Tab]),
          CsvCampo(Tab) + ';' + CsvCampo(Col), Datas);

      EhPista := False;
      for P in PISTAS_STATUS do
        if Pos(P, Col) > 0 then
        begin
          EhPista := True;
          Break;
        end;
      if EhPista and ((C.Tipo = 'VARCHAR2') or (C.Tipo = 'CHAR') or
        (C.Tipo = 'NUMBER') or (C.Tipo = 'NVARCHAR2')) then
        Coletar(Format('SELECT * FROM (SELECT SUBSTR(TO_CHAR(%0:s),1,200) AS VALOR, ' +
          'COUNT(*) AS QTD FROM %1:s.%2:s GROUP BY SUBSTR(TO_CHAR(%0:s),1,200) ' +
          'ORDER BY 2 DESC) WHERE ROWNUM <= 30',
          ['"' + Col + '"', FOwner, Tab]),
          CsvCampo(Tab) + ';' + CsvCampo(Col), Valores);
    end;

    GravarCsv('11_integradora_volumes_e_datas.csv',
      'Linhas por tabela e periodo das colunas de data', Datas);
    GravarCsv('12_integradora_valores_status.csv',
      'Valores mais frequentes das colunas de status/erro', Valores);
  finally
    Valores.Free;
    Datas.Free;
  end;
end;

procedure TFVDiagnostico.Amostras;

  function ColunaOrdem(const ATab: string): string;
  var
    C: TColunaInfo;
  begin
    for C in FColunasFV do
      if (C.Tabela = ATab) and ((C.Tipo = 'DATE') or StartsStr('TIMESTAMP', C.Tipo)) then
        Exit('"' + C.Coluna + '" DESC NULLS LAST');
    Result := 'ROWID DESC';
  end;

  procedure Amostrar(const ATab, ADesc: string);
  begin
    if FIntegradora.IndexOf(ATab) < 0 then
      Exit;
    Exportar('20_amostra_' + ATab + '.csv', ADesc,
      'SELECT * FROM (SELECT * FROM ' + FOwner + '.' + ATab +
      ' ORDER BY ' + ColunaOrdem(ATab) + ') WHERE ROWNUM <= ' + IntToStr(MAX_AMOSTRA));
  end;

begin
  if FAmostraPedidos then
  begin
    Amostrar('PCPEDCFV', Format('Ultimos %d cabecalhos de pedido da integradora', [MAX_AMOSTRA]));
    Amostrar('PCPEDIFV', Format('Ultimos %d itens de pedido da integradora', [MAX_AMOSTRA]));
  end
  else
    Log('  amostra de pedidos desligada');
  if FAmostraClientes then
    Amostrar('PCCLIENTFV', Format('Ultimos %d cadastros da integradora (DADOS PESSOAIS)', [MAX_AMOSTRA]))
  else
    Log('  amostra de clientes desligada (LGPD)');
end;

procedure TFVDiagnostico.GravarManifesto(AInicio: TDateTime);
var
  M: TStringList;
begin
  M := TStringList.Create;
  try
    M.Add('HUGINN IA - Forca de Vendas - Diagnostico v' + VERSAO_DIAG);
    M.Add('Inteligencia antes da decisao.');
    M.Add('');
    M.Add('Gerado em .......: ' + FormatDateTime('dd/mm/yyyy hh:nn:ss', Now));
    M.Add('Duracao .........: ' + IntToStr(SecondsBetween(Now, AInicio)) + ' s');
    M.Add('Computador ......: ' + GetEnvironmentVariable('COMPUTERNAME'));
    M.Add('Usuario Windows .: ' + GetEnvironmentVariable('USERNAME'));
    M.Add('Servidor ........: ' + FServidor);
    M.Add('Versao Oracle ...: ' + FConn.ServerVersion);
    M.Add('Schema WinThor ..: ' + FOwner);
    M.Add('Integradora .....: ' + IfThen(FIntegradora.Count = 0, 'NAO ENCONTRADA', FIntegradora.CommaText));
    M.Add('Amostra pedidos .: ' + IfThen(FAmostraPedidos, 'sim', 'nao'));
    M.Add('Amostra clientes : ' + IfThen(FAmostraClientes, 'sim (contem dados pessoais)', 'nao'));
    M.Add('Erros ...........: ' + IntToStr(FErros));
    M.Add('');
    M.Add('SOMENTE LEITURA: todas as instrucoes foram SELECT; nada foi gravado no banco.');
    M.Add('Senha: nao consta neste pacote.');
    M.Add('');
    M.Add('ARQUIVO;LINHAS;RESULTADO;DESCRICAO');
    M.AddStrings(FManifesto);
    M.WriteBOM := True;
    M.SaveToFile(TPath.Combine(FDir, 'manifesto.txt'), TEncoding.UTF8);
  finally
    M.Free;
  end;
end;

function TFVDiagnostico.Executar(const APastaBase: string): string;
var
  Inicio: TDateTime;
  Carimbo: string;
begin
  if not TRegEx.IsMatch(FOwner, '^[A-Z][A-Z0-9_$#]{0,127}$') then
    raise Exception.Create('Schema WinThor invalido: ' + FOwner);
  Inicio := Now;
  FErros := 0;
  FManifesto.Clear;
  FExistentes.Clear;
  FIntegradora.Clear;
  Carimbo := FormatDateTime('yyyymmdd_hhnnss', Inicio);
  FDir := TPath.Combine(APastaBase, 'Diagnostico_FV_' + Carimbo);
  ForceDirectories(FDir);
  Log('HUGINN FV Diagnostico v' + VERSAO_DIAG + ' - pasta: ' + FDir);

  Ambiente;
  LocalizarTabelas;
  if FExistentes.Count = 0 then
    Log('ATENCAO: nenhuma tabela encontrada no schema ' + FOwner +
      '. Confira o campo "Schema WinThor".')
  else
  begin
    Dicionario;
    UsoDaIntegradora;
    CarregarColunasFV;
    PerfilIntegradora;
    Amostras;
  end;
  GravarManifesto(Inicio);

  Result := TPath.Combine(APastaBase, 'Diagnostico_FV_' + Carimbo + '.zip');
  TZipFile.ZipDirectoryContents(Result, FDir);
  Log(Format('Concluido com %d erro(s). ZIP: %s', [FErros, Result]));
end;

end.
