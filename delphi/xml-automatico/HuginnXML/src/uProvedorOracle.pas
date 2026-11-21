unit uProvedorOracle;

{ HUGINN XML Automatico - provedor Oracle (UniDAC), SOMENTE LEITURA.

  As tabelas e colunas usadas aqui foram confirmadas nos traces da rotina 1301
  (ver docs/MATRIZ_CONSULTAS.md). As consultas foram escritas pela HUGINN a partir
  dessas colunas; nao sao copia do SQL da TOTVS.

  Regras:
  - So SELECT (a trava ExecutarSelect recusa qualquer outro comando).
  - Textos sempre por parametro (bind). Listas de inteiros validadas e montadas em lote.
  - Falha de conexao/permissao vira Status = scIndisponivel, nunca "nao encontrado".

  PENDENTE de homologacao: coluna de fator da PCCODFABRICA, coluna de CEST do
  produto, regras de tributacao/tabela de preco/enderecamento da validacao da 1301. }

interface

uses
  System.SysUtils, Uni, uTipos, uProvedor;

type
  TProvedorOracle = class(TInterfacedObject, IProvedorDados)
  private
    FConn: TUniConnection;
    FDonoConexao: Boolean;
    FOwner: string;            // prefixo "OWNER." ou vazio (sinonimos)
    function T(const Tabela: string): string;
    function NovaQuery(const SQL: string): TUniQuery;
    function ListaBinds(const Prefixo: string; N: Integer): string;
    function CandidatosDe(Q: TUniQuery; O: TOrigemVinculo; const Entradas: TArray<string>;
      const CampoId: string; Numerico: Boolean; CodFornec: Integer): TArray<TCandidatoProduto>;
  public
    constructor Create(AConn: TUniConnection; const AOwner: string; ADonoConexao: Boolean);
    destructor Destroy; override;
    function Nome: string;
    function EhDemonstracao: Boolean;
    function FiliaisPorCNPJ(const CNPJ: string): TResultadoFiliais;
    function FornecedoresPorCNPJ(const CNPJ: string): TResultadoFornecedores;
    function ProdutosPorBarras(const Filial: string; const Codigos: TArray<string>;
      Master: Boolean): TResultadoCandidatos;
    function ProdutosPorCodFab203(const Filial: string; const Codigos: TArray<string>): TResultadoCandidatos;
    function ProdutosPorCodFab253(const Filial: string; CodFornec: Integer;
      const Codigos: TArray<string>): TResultadoCandidatos;
    function RestricoesImportacao(const Filial: string; CodFornec: Integer;
      const CodProds: TArray<Integer>): TResultadoRestricoes;
    function CustosReferencia(const Filial: string; const CodProds: TArray<Integer>): TResultadoCustos;
    function NotaJaLancada(const Chave: string; CodFornec: Integer; const Numero, Serie: string): TResultadoLancada;
  end;

const
  MAX_LOTE = 200;   // itens por consulta IN (Oracle aceita ate 1000)

implementation

uses
  System.StrUtils, Data.DB, uValidacao, uConfig;

const
  // Mesmo criterio da 1301: CNPJ comparado sem pontuacao.
  CGC_LIMPO = 'REPLACE(REPLACE(REPLACE(%s, ''.'', ''''), ''/'', ''''), ''-'', '''')';
  CAMPOS_PRODUTO = 'P.CODPROD, P.DESCRICAO, P.UNIDADE, P.EMBALAGEM, P.CODNCMEX, P.QTUNITCX';

procedure ExigirSomenteLeitura(const SQL: string);
var
  S: string;
begin
  S := UpperCase(TrimLeft(SQL));
  if not (S.StartsWith('SELECT') or S.StartsWith('WITH')) then
    raise Exception.Create('HUGINN: comando recusado (somente SELECT é permitido).');
end;

function ListaInteiros(const L: TArray<Integer>): string;
var
  V: Integer;
begin
  Result := '';
  for V in L do
    Result := Result + IfThen(Result <> '', ',', '') + IntToStr(V);  // inteiros: sem injecao possivel
end;

{ TProvedorOracle }

constructor TProvedorOracle.Create(AConn: TUniConnection; const AOwner: string; ADonoConexao: Boolean);
begin
  inherited Create;
  FConn := AConn;
  FDonoConexao := ADonoConexao;
  if Trim(AOwner) = '' then
    FOwner := ''
  else if IdentificadorValido(UpperCase(Trim(AOwner))) then
    FOwner := UpperCase(Trim(AOwner)) + '.'
  else
    raise Exception.Create('Schema (owner) inválido.');
end;

destructor TProvedorOracle.Destroy;
begin
  if FDonoConexao then
    FConn.Free;
  inherited;
end;

function TProvedorOracle.Nome: string;
begin
  Result := 'Oracle WinThor (somente leitura)';
end;

function TProvedorOracle.EhDemonstracao: Boolean;
begin
  Result := False;
end;

function TProvedorOracle.T(const Tabela: string): string;
begin
  Result := FOwner + Tabela;
end;

function TProvedorOracle.NovaQuery(const SQL: string): TUniQuery;
begin
  ExigirSomenteLeitura(SQL);
  Result := TUniQuery.Create(nil);
  Result.Connection := FConn;
  Result.SQL.Text := SQL;
end;

function TProvedorOracle.ListaBinds(const Prefixo: string; N: Integer): string;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to N - 1 do
    Result := Result + IfThen(I > 0, ', ', '') + ':' + Prefixo + IntToStr(I);
end;

{ Converte as linhas da consulta em candidatos. O identificador devolvido e o
  do XML (texto original), para o motor casar item a item. }
function TProvedorOracle.CandidatosDe(Q: TUniQuery; O: TOrigemVinculo;
  const Entradas: TArray<string>; const CampoId: string; Numerico: Boolean;
  CodFornec: Integer): TArray<TCandidatoProduto>;
var
  C: TCandidatoProduto;
  Valor, E: string;
  VNum: Int64;
begin
  Result := nil;
  while not Q.Eof do
  begin
    Valor := Trim(Q.FieldByName(CampoId).AsString);
    C := Default(TCandidatoProduto);
    C.CodProd := Q.FieldByName('CODPROD').AsInteger;
    C.Descricao := Q.FieldByName('DESCRICAO').AsString;
    C.Unidade := Q.FieldByName('UNIDADE').AsString;
    C.Embalagem := Q.FieldByName('EMBALAGEM').AsString;
    C.NCM := Q.FieldByName('CODNCMEX').AsString;
    C.QtUnitCx := Q.FieldByName('QTUNITCX').AsFloat;
    C.Origem := O;
    C.CodFornec := CodFornec;
    C.FatorVinculo := 0;   // PENDENTE: coluna de fator da PCCODFABRICA
    C.Identificador := Valor;
    for E in Entradas do
      if Numerico then
      begin
        if TryStrToInt64(Valor, VNum) and (StrToInt64Def(E, -1) = VNum) then
          C.Identificador := E;
      end
      else if SameText(E, Valor) then
        C.Identificador := E;
    SetLength(Result, Length(Result) + 1);
    Result[High(Result)] := C;
    Q.Next;
  end;
end;

function TProvedorOracle.FiliaisPorCNPJ(const CNPJ: string): TResultadoFiliais;
var
  Q: TUniQuery;
  F: TFilial;
begin
  Result := Default(TResultadoFiliais);
  try
    Q := NovaQuery('SELECT CODIGO, RAZAOSOCIAL, CGC FROM ' + T('PCFILIAL') +
      ' WHERE CODIGO <> ''99'' AND ' + Format(CGC_LIMPO, ['CGC']) + ' = :CNPJ');
    try
      Q.ParamByName('CNPJ').AsString := SoDigitos(CNPJ);
      Q.Open;
      while not Q.Eof do
      begin
        F.Codigo := Trim(Q.Fields[0].AsString);
        F.Nome := Q.Fields[1].AsString;
        F.CNPJ := SoDigitos(Q.Fields[2].AsString);
        SetLength(Result.Filiais, Length(Result.Filiais) + 1);
        Result.Filiais[High(Result.Filiais)] := F;
        Q.Next;
      end;
    finally
      Q.Free;
    end;
  except
    on E: Exception do
    begin
      Result.Status := scIndisponivel;
      Result.Mensagem := E.Message;
    end;
  end;
end;

function TProvedorOracle.FornecedoresPorCNPJ(const CNPJ: string): TResultadoFornecedores;
var
  Q: TUniQuery;
  F: TFornecedor;
begin
  Result := Default(TResultadoFornecedores);
  try
    Q := NovaQuery('SELECT CODFORNEC, FORNECEDOR, CGC, NVL(BLOQUEIO, ''N'') BLOQUEIO, ' +
      'NVL(REVENDA, ''S'') REVENDA FROM ' + T('PCFORNEC') +
      ' WHERE ' + Format(CGC_LIMPO, ['CGC']) + ' = :CNPJ');
    try
      Q.ParamByName('CNPJ').AsString := SoDigitos(CNPJ);
      Q.Open;
      while not Q.Eof do
      begin
        F.Codigo := Q.FieldByName('CODFORNEC').AsInteger;
        F.Nome := Q.FieldByName('FORNECEDOR').AsString;
        F.CNPJ := SoDigitos(Q.FieldByName('CGC').AsString);
        F.Bloqueado := UpperCase(Q.FieldByName('BLOQUEIO').AsString) = 'S';
        F.Revenda := MatchStr(UpperCase(Q.FieldByName('REVENDA').AsString), ['S', 'O', 'X']);
        SetLength(Result.Fornecedores, Length(Result.Fornecedores) + 1);
        Result.Fornecedores[High(Result.Fornecedores)] := F;
        Q.Next;
      end;
    finally
      Q.Free;
    end;
  except
    on E: Exception do
    begin
      Result.Status := scIndisponivel;
      Result.Mensagem := E.Message;
    end;
  end;
end;

function TProvedorOracle.ProdutosPorBarras(const Filial: string; const Codigos: TArray<string>;
  Master: Boolean): TResultadoCandidatos;
var
  Q: TUniQuery;
  Campo, Filtro: string;
  Lote: TArray<string>;
  I, J: Integer;
  O: TOrigemVinculo;
begin
  Result := Default(TResultadoCandidatos);
  if Master then
  begin
    Campo := 'CODAUXILIAR2';
    O := ovBarrasMaster;
  end
  else
  begin
    Campo := 'CODAUXILIAR';
    O := ovBarrasVenda;
  end;
  Filtro := '';
  if Filial <> '' then
    Filtro := ' AND (P.CODFILIAL = :FIL OR NVL(P.CODFILIAL, ''99'') = ''99'')';
  try
    I := 0;
    while I < Length(Codigos) do
    begin
      Lote := Copy(Codigos, I, MAX_LOTE);
      // CODAUXILIAR/CODAUXILIAR2 sao numericos no WinThor: o bind texto so com digitos e convertido pelo Oracle.
      Q := NovaQuery('SELECT ' + CAMPOS_PRODUTO + ', P.' + Campo + ' IDENT FROM ' + T('PCPRODUT') + ' P' +
        ' WHERE P.' + Campo + ' IN (' + ListaBinds('C', Length(Lote)) + ')' + Filtro);
      try
        for J := 0 to High(Lote) do
          Q.ParamByName('C' + IntToStr(J)).AsString := SoDigitos(Lote[J]);
        if Filial <> '' then
          Q.ParamByName('FIL').AsString := Filial;
        Q.Open;
        for var C in CandidatosDe(Q, O, Lote, 'IDENT', True, 0) do
        begin
          SetLength(Result.Candidatos, Length(Result.Candidatos) + 1);
          Result.Candidatos[High(Result.Candidatos)] := C;
        end;
      finally
        Q.Free;
      end;
      Inc(I, MAX_LOTE);
    end;
  except
    on E: Exception do
      Result := Indisponivel(E.Message);
  end;
end;

function TProvedorOracle.ProdutosPorCodFab203(const Filial: string;
  const Codigos: TArray<string>): TResultadoCandidatos;
var
  Q: TUniQuery;
  Filtro: string;
  Lote: TArray<string>;
  I, J: Integer;
begin
  Result := Default(TResultadoCandidatos);
  Filtro := '';
  if Filial <> '' then
    Filtro := ' AND (P.CODFILIAL = :FIL OR NVL(P.CODFILIAL, ''99'') = ''99'')';
  try
    I := 0;
    while I < Length(Codigos) do
    begin
      Lote := Copy(Codigos, I, MAX_LOTE);
      Q := NovaQuery('SELECT ' + CAMPOS_PRODUTO + ', P.CODFAB IDENT FROM ' + T('PCPRODUT') + ' P' +
        ' WHERE UPPER(P.CODFAB) IN (' + ListaBinds('C', Length(Lote)) + ')' + Filtro);
      try
        for J := 0 to High(Lote) do
          Q.ParamByName('C' + IntToStr(J)).AsString := UpperCase(Trim(Lote[J]));
        if Filial <> '' then
          Q.ParamByName('FIL').AsString := Filial;
        Q.Open;
        for var C in CandidatosDe(Q, ovCodFab203, Lote, 'IDENT', False, 0) do
        begin
          SetLength(Result.Candidatos, Length(Result.Candidatos) + 1);
          Result.Candidatos[High(Result.Candidatos)] := C;
        end;
      finally
        Q.Free;
      end;
      Inc(I, MAX_LOTE);
    end;
  except
    on E: Exception do
      Result := Indisponivel(E.Message);
  end;
end;

function TProvedorOracle.ProdutosPorCodFab253(const Filial: string; CodFornec: Integer;
  const Codigos: TArray<string>): TResultadoCandidatos;
var
  Q: TUniQuery;
  Filtro: string;
  Lote: TArray<string>;
  I, J: Integer;
begin
  Result := Default(TResultadoCandidatos);
  Filtro := '';
  if Filial <> '' then
    Filtro := ' AND (P.CODFILIAL = :FIL OR NVL(P.CODFILIAL, ''99'') = ''99'')';
  try
    I := 0;
    while I < Length(Codigos) do
    begin
      Lote := Copy(Codigos, I, MAX_LOTE);
      Q := NovaQuery('SELECT ' + CAMPOS_PRODUTO + ', CF.CODFAB IDENT FROM ' + T('PCCODFABRICA') + ' CF, ' +
        T('PCPRODUT') + ' P WHERE P.CODPROD = CF.CODPROD AND CF.CODFORNEC = :FORN' +
        ' AND UPPER(CF.CODFAB) IN (' + ListaBinds('C', Length(Lote)) + ')' + Filtro);
      try
        Q.ParamByName('FORN').AsInteger := CodFornec;
        for J := 0 to High(Lote) do
          Q.ParamByName('C' + IntToStr(J)).AsString := UpperCase(Trim(Lote[J]));
        if Filial <> '' then
          Q.ParamByName('FIL').AsString := Filial;
        Q.Open;
        for var C in CandidatosDe(Q, ovCodFab253, Lote, 'IDENT', False, CodFornec) do
        begin
          SetLength(Result.Candidatos, Length(Result.Candidatos) + 1);
          Result.Candidatos[High(Result.Candidatos)] := C;
        end;
      finally
        Q.Free;
      end;
      Inc(I, MAX_LOTE);
    end;
  except
    on E: Exception do
      Result := Indisponivel(E.Message);
  end;
end;

function TProvedorOracle.RestricoesImportacao(const Filial: string; CodFornec: Integer;
  const CodProds: TArray<Integer>): TResultadoRestricoes;

  procedure Add(CodProd: Integer; const Cod, Msg, Acao: string);
  var
    R: TRestricao;
  begin
    R.CodProd := CodProd;
    R.Codigo := Cod;
    R.Mensagem := Msg;
    R.Acao := Acao;
    SetLength(Result.Restricoes, Length(Result.Restricoes) + 1);
    Result.Restricoes[High(Result.Restricoes)] := R;
  end;

var
  Q: TUniQuery;
  Cod: Integer;
begin
  Result := Default(TResultadoRestricoes);
  if Length(CodProds) = 0 then
    Exit;
  try
    // Subconjunto da validacao de produtos da 1301 com colunas confirmadas no trace.
    // Tributacao, tabela de preco e enderecamento: proxima versao (consultas maiores).
    Q := NovaQuery(
      'SELECT P.CODPROD,' +
      ' CASE WHEN E.CODPROD IS NULL THEN 1 ELSE 0 END SEM_PCEST,' +
      ' CASE WHEN PF.CODPROD IS NULL THEN 1 ELSE 0 END SEM_PCPRODFILIAL,' +
      ' CASE WHEN P.DTEXCLUSAO IS NOT NULL THEN 1 ELSE 0 END EXCLUIDO,' +
      ' CASE WHEN NVL(P.OBS, ''X'') = ''PV'' OR NVL(PF.PROIBIDAVENDA, ''N'') <> ''N'' THEN 1 ELSE 0 END PROIBIDO,' +
      ' CASE WHEN NVL(P.OBS2, ''X'') = ''FL'' OR NVL(PF.FORALINHA, ''N'') <> ''N'' THEN 1 ELSE 0 END FORA_LINHA,' +
      ' CASE WHEN NVL(P.PRECIFICESTRANGEIRA, ''N'') = ''S'' THEN 1 ELSE 0 END MOEDA_ESTR,' +
      ' CASE WHEN NVL(P.CODFILIAL, ''99'') <> ''99'' AND P.CODFILIAL <> :FIL1 THEN 1 ELSE 0 END OUTRA_FILIAL' +
      ' FROM ' + T('PCPRODUT') + ' P' +
      ' LEFT JOIN ' + T('PCEST') + ' E ON E.CODPROD = P.CODPROD AND E.CODFILIAL = :FIL2' +
      ' LEFT JOIN ' + T('PCPRODFILIAL') + ' PF ON PF.CODPROD = P.CODPROD AND PF.CODFILIAL = :FIL3' +
      ' WHERE P.CODPROD IN (' + ListaInteiros(CodProds) + ')');
    try
      Q.ParamByName('FIL1').AsString := Filial;
      Q.ParamByName('FIL2').AsString := Filial;
      Q.ParamByName('FIL3').AsString := Filial;
      Q.Open;
      while not Q.Eof do
      begin
        Cod := Q.FieldByName('CODPROD').AsInteger;
        if Q.FieldByName('SEM_PCEST').AsInteger = 1 then
          Add(Cod, 'SEM_PCEST', 'produto sem registro de estoque (PCEST) na filial.', 'Libere o produto para a filial na rotina nativa.');
        if Q.FieldByName('SEM_PCPRODFILIAL').AsInteger = 1 then
          Add(Cod, 'SEM_PCPRODFILIAL', 'produto sem cadastro por filial (PCPRODFILIAL).', 'Complete o cadastro do produto para a filial.');
        if Q.FieldByName('EXCLUIDO').AsInteger = 1 then
          Add(Cod, 'EXCLUIDO', 'produto excluído do cadastro.', 'Confira se o vínculo está apontando para o produto certo.');
        if Q.FieldByName('PROIBIDO').AsInteger = 1 then
          Add(Cod, 'PROIBIDO_VENDA', 'produto proibido para venda.', 'Confira o cadastro antes da entrada.');
        if Q.FieldByName('FORA_LINHA').AsInteger = 1 then
          Add(Cod, 'FORA_DE_LINHA', 'produto fora de linha.', 'Reative o produto ou marque "Aceita produtos fora de linha" na 1301, se for o caso.');
        if Q.FieldByName('MOEDA_ESTR').AsInteger = 1 then
          Add(Cod, 'PRECIFIC_ESTRANGEIRA', 'produto com precificação em moeda estrangeira.', 'Marque a opção correspondente na 1301 e informe a cotação.');
        if Q.FieldByName('OUTRA_FILIAL').AsInteger = 1 then
          Add(Cod, 'OUTRA_FILIAL', 'produto exclusivo de outra filial.', 'Confira a filial da nota e do produto.');
        Q.Next;
      end;
    finally
      Q.Free;
    end;
  except
    on E: Exception do
    begin
      Result.Status := scIndisponivel;
      Result.Mensagem := E.Message;
    end;
  end;
end;

function TProvedorOracle.CustosReferencia(const Filial: string;
  const CodProds: TArray<Integer>): TResultadoCustos;
var
  Q: TUniQuery;
  C: TCustoReferencia;
begin
  Result := Default(TResultadoCustos);
  if Length(CodProds) = 0 then
    Exit;
  try
    Q := NovaQuery('SELECT CODPROD, CODFILIAL, NVL(PLIQULTENT, 0) PLIQULTENT, ' +
      'NVL(CUSTOULTENT, 0) CUSTOULTENT, NVL(CUSTOULTENTFIN, 0) CUSTOULTENTFIN FROM ' + T('PCEST') +
      ' WHERE CODFILIAL = :FIL AND CODPROD IN (' + ListaInteiros(CodProds) + ')');
    try
      Q.ParamByName('FIL').AsString := Filial;
      Q.Open;
      while not Q.Eof do
      begin
        C.CodProd := Q.FieldByName('CODPROD').AsInteger;
        C.Filial := Trim(Q.FieldByName('CODFILIAL').AsString);
        C.PLiqUltEnt := Q.FieldByName('PLIQULTENT').AsFloat;
        C.CustoUltEnt := Q.FieldByName('CUSTOULTENT').AsFloat;
        C.CustoUltEntFin := Q.FieldByName('CUSTOULTENTFIN').AsFloat;
        SetLength(Result.Custos, Length(Result.Custos) + 1);
        Result.Custos[High(Result.Custos)] := C;
        Q.Next;
      end;
    finally
      Q.Free;
    end;
  except
    on E: Exception do
    begin
      Result.Status := scIndisponivel;
      Result.Mensagem := E.Message;
    end;
  end;
end;

function TProvedorOracle.NotaJaLancada(const Chave: string; CodFornec: Integer;
  const Numero, Serie: string): TResultadoLancada;
var
  Q: TUniQuery;
begin
  Result := Default(TResultadoLancada);
  Result.Resultado := jlNao;
  try
    // 1) Pre-entrada com a mesma chave (PCNFENTPREENT.CHAVENFE, confirmada no trace de gravacao).
    Q := NovaQuery('SELECT NUMTRANSENT, NVL(STATUS, ''-'') STATUS FROM ' + T('PCNFENTPREENT') +
      ' WHERE CHAVENFE = :CHAVE AND ROWNUM <= 5');
    try
      Q.ParamByName('CHAVE').AsString := Chave;
      Q.Open;
      if not Q.Eof then
      begin
        Result.Resultado := jlSim;
        Result.Mensagem := 'já existe pré-entrada (status ' + Q.FieldByName('STATUS').AsString + ').';
        Result.Referencia := 'Transação ' + Q.FieldByName('NUMTRANSENT').AsString;
        Exit;
      end;
    finally
      Q.Free;
    end;
    // 2) Nota de entrada ativa do mesmo fornecedor, numero e serie (exclui canceladas em PCNFCAN).
    if CodFornec > 0 then
    begin
      Q := NovaQuery('SELECT N.NUMTRANSENT, N.CODFILIAL FROM ' + T('PCNFENT') + ' N' +
        ' WHERE N.CODFORNEC = :FORN AND N.NUMNOTA = :NUM AND N.SERIE = :SERIE AND N.VLTOTAL > 0' +
        ' AND NOT EXISTS (SELECT 1 FROM ' + T('PCNFCAN') + ' C WHERE C.NUMTRANSENT = N.NUMTRANSENT)' +
        ' AND ROWNUM <= 5');
      try
        Q.ParamByName('FORN').AsInteger := CodFornec;
        Q.ParamByName('NUM').AsLargeInt := StrToInt64Def(Numero, -1);
        Q.ParamByName('SERIE').AsString := Serie;
        Q.Open;
        if not Q.Eof then
        begin
          Result.Resultado := jlSim;
          Result.Mensagem := 'nota de entrada já lançada na filial ' + Q.FieldByName('CODFILIAL').AsString + '.';
          Result.Referencia := 'Transação ' + Q.FieldByName('NUMTRANSENT').AsString;
        end;
      finally
        Q.Free;
      end;
    end;
  except
    on E: Exception do
    begin
      Result.Resultado := jlIndisponivel;
      Result.Mensagem := E.Message;
    end;
  end;
end;

end.
