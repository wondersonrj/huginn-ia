unit uProvedorDemo;

{ HUGINN XML Automatico - provedor de DEMONSTRACAO (dados ficticios, sem banco).
  Os valores casam com as notas de fixtures/ (geradas por gerar_fixtures.py).
  Com AFalhar = True, toda consulta responde "indisponivel" (simula queda de
  conexao ou falta de permissao). }

interface

uses
  uTipos, uProvedor;

type
  TProdutoDemo = record
    CodProd: Integer;
    Descricao, Unidade, Embalagem, NCM, CEST: string;
    CodAuxiliar, CodAuxiliar2, CodFab: string;
    QtUnitCx: Double;
  end;

  TVinculo253Demo = record
    CodFornec: Integer;
    CodFab: string;
    CodProd: Integer;
    Fator: Double;
  end;

  TProvedorDemo = class(TInterfacedObject, IProvedorDados)
  private
    FFalhar: Boolean;
    FFiliais: TArray<TFilial>;
    FFornecedores: TArray<TFornecedor>;
    FProdutos: TArray<TProdutoDemo>;
    FVinculos: TArray<TVinculo253Demo>;
    FCustos: TArray<TCustoReferencia>;
    FRestricoes: TArray<TRestricao>;
    FChavesLancadas: TArray<string>;
    procedure Carregar;
    function Candidato(const P: TProdutoDemo; O: TOrigemVinculo; const Id: string): TCandidatoProduto;
    function ProdutoPorCodigo(CodProd: Integer; out P: TProdutoDemo): Boolean;
  public
    constructor Create(AFalhar: Boolean = False);
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
  // Mesmos valores de fixtures/gerar_fixtures.py
  CNPJ_FILIAL_1       = '11222333000181';
  CNPJ_FILIAL_2       = '11222333000262';
  CNPJ_FILIAL_AMBIGUA = '11222333000343';
  CNPJ_FORNEC_101     = '44555666000181';
  CNPJ_FORNEC_DUP     = '44555666000262';
  GTIN_1001 = '2000001001004';
  GTIN_1003 = '2000001003008';
  GTIN_1006 = '2000001006009';
  GTIN_1007 = '2000001007006';
  GTIN_1008 = '2000001008003';
  CHAVE_JA_LANCADA = '35261144555666000181550010000040011123456782';
  MSG_FALHA = 'SIMULAÇÃO de falha de conexão (provedor de demonstração).';

implementation

uses
  System.SysUtils;

function Filial(const Cod, Nome, CNPJ: string): TFilial;
begin
  Result.Codigo := Cod;
  Result.Nome := Nome;
  Result.CNPJ := CNPJ;
end;

function Fornec(Cod: Integer; const Nome, CNPJ: string): TFornecedor;
begin
  Result.Codigo := Cod;
  Result.Nome := Nome;
  Result.CNPJ := CNPJ;
  Result.Bloqueado := False;
  Result.Revenda := True;
end;

function Prod(Cod: Integer; const Desc, Un, NCM, CEST, Aux, Aux2, CodFab: string;
  QtCx: Double): TProdutoDemo;
begin
  Result.CodProd := Cod;
  Result.Descricao := Desc;
  Result.Unidade := Un;
  Result.Embalagem := '1' + Un;
  Result.NCM := NCM;
  Result.CEST := CEST;
  Result.CodAuxiliar := Aux;
  Result.CodAuxiliar2 := Aux2;
  Result.CodFab := CodFab;
  Result.QtUnitCx := QtCx;
end;

function Vinc(Fornec: Integer; const CodFab: string; CodProd: Integer; Fator: Double): TVinculo253Demo;
begin
  Result.CodFornec := Fornec;
  Result.CodFab := CodFab;
  Result.CodProd := CodProd;
  Result.Fator := Fator;
end;

function Custo(CodProd: Integer; const Fil: string; PLiq: Double): TCustoReferencia;
begin
  Result.CodProd := CodProd;
  Result.Filial := Fil;
  Result.PLiqUltEnt := PLiq;
  Result.CustoUltEnt := PLiq * 1.12;
  Result.CustoUltEntFin := PLiq * 1.12;
end;

function Restr(CodProd: Integer; const Cod, Msg, Acao: string): TRestricao;
begin
  Result.CodProd := CodProd;
  Result.Codigo := Cod;
  Result.Mensagem := Msg;
  Result.Acao := Acao;
end;

{ TProvedorDemo }

constructor TProvedorDemo.Create(AFalhar: Boolean);
begin
  inherited Create;
  FFalhar := AFalhar;
  Carregar;
end;

procedure TProvedorDemo.Carregar;
begin
  FFiliais := [
    Filial('1', 'HUGINN DEMO MATRIZ', CNPJ_FILIAL_1),
    Filial('2', 'HUGINN DEMO FILIAL 2', CNPJ_FILIAL_2),
    Filial('3', 'HUGINN DEMO CD A', CNPJ_FILIAL_AMBIGUA),
    Filial('4', 'HUGINN DEMO CD B', CNPJ_FILIAL_AMBIGUA)];

  FFornecedores := [
    Fornec(101, 'FORNECEDOR DEMO ALIMENTOS LTDA', CNPJ_FORNEC_101),
    Fornec(102, 'FORNECEDOR DUPLICADO DEMO', CNPJ_FORNEC_DUP),
    Fornec(103, 'FORNECEDOR DUPLICADO DEMO (2)', CNPJ_FORNEC_DUP)];

  FProdutos := [
    Prod(1001, 'ARROZ DEMO T1 5KG', 'UN', '10063021', '', GTIN_1001, '', 'F-ARROZ', 1),
    Prod(1002, 'FEIJAO DEMO CARIOCA 1KG', 'UN', '07133319', '', '', '', '', 1),
    Prod(1003, 'MILHO DEMO 500G', 'UN', '10059010', '', GTIN_1003, '', '', 1),
    Prod(1004, 'MILHO DEMO 500G (OUTRO CADASTRO)', 'UN', '10059010', '', '', '', '', 1),
    Prod(1005, 'OLEO DEMO SOJA 900ML', 'UN', '15079011', '', '', '', '', 20),
    Prod(1006, 'ACUCAR DEMO 1KG', 'UN', '17019900', '', GTIN_1006, '', '', 10),
    Prod(1007, 'CAFE DEMO 500G', 'UN', '09012100', '1709700', GTIN_1007, '', '', 1),
    Prod(1008, 'MACARRAO DEMO 500G', 'UN', '19021900', '', GTIN_1008, '', '', 1)];

  FVinculos := [
    Vinc(101, 'FAB-200', 1002, 1),
    Vinc(101, 'FAB-300', 1004, 1),
    Vinc(101, 'FAB-500', 1005, 20),
    Vinc(101, 'FAB-700', 1007, 1),
    Vinc(101, 'FAB-800', 1008, 1)];

  FCustos := [
    Custo(1001, '1', 25.40), Custo(1001, '2', 30.00),
    Custo(1002, '1', 7.10),
    Custo(1005, '1', 6.00),
    Custo(1006, '1', 4.00),
    Custo(1007, '1', 0),
    Custo(1008, '1', 3.50)];

  FRestricoes := [
    Restr(1008, 'FORA_DE_LINHA', 'produto fora de linha na filial.',
      'Reative o produto na filial (ou marque "Aceita produtos fora de linha" na 1301, se for o caso).')];

  FChavesLancadas := [CHAVE_JA_LANCADA];
end;

function TProvedorDemo.Nome: string;
begin
  if FFalhar then
    Result := 'Demonstração (simulando falha)'
  else
    Result := 'Demonstração (dados fictícios, sem banco)';
end;

function TProvedorDemo.EhDemonstracao: Boolean;
begin
  Result := True;
end;

function TProvedorDemo.ProdutoPorCodigo(CodProd: Integer; out P: TProdutoDemo): Boolean;
var
  X: TProdutoDemo;
begin
  for X in FProdutos do
    if X.CodProd = CodProd then
    begin
      P := X;
      Exit(True);
    end;
  Result := False;
end;

function TProvedorDemo.Candidato(const P: TProdutoDemo; O: TOrigemVinculo; const Id: string): TCandidatoProduto;
begin
  Result := Default(TCandidatoProduto);
  Result.CodProd := P.CodProd;
  Result.Descricao := P.Descricao;
  Result.Unidade := P.Unidade;
  Result.Embalagem := P.Embalagem;
  Result.NCM := P.NCM;
  Result.CEST := P.CEST;
  Result.QtUnitCx := P.QtUnitCx;
  Result.Origem := O;
  Result.Identificador := Id;
end;

function TProvedorDemo.FiliaisPorCNPJ(const CNPJ: string): TResultadoFiliais;
var
  F: TFilial;
begin
  Result := Default(TResultadoFiliais);
  if FFalhar then
  begin
    Result.Status := scIndisponivel;
    Result.Mensagem := MSG_FALHA;
    Exit;
  end;
  for F in FFiliais do
    if F.CNPJ = CNPJ then
    begin
      SetLength(Result.Filiais, Length(Result.Filiais) + 1);
      Result.Filiais[High(Result.Filiais)] := F;
    end;
end;

function TProvedorDemo.FornecedoresPorCNPJ(const CNPJ: string): TResultadoFornecedores;
var
  F: TFornecedor;
begin
  Result := Default(TResultadoFornecedores);
  if FFalhar then
  begin
    Result.Status := scIndisponivel;
    Result.Mensagem := MSG_FALHA;
    Exit;
  end;
  for F in FFornecedores do
    if F.CNPJ = CNPJ then
    begin
      SetLength(Result.Fornecedores, Length(Result.Fornecedores) + 1);
      Result.Fornecedores[High(Result.Fornecedores)] := F;
    end;
end;

function TProvedorDemo.ProdutosPorBarras(const Filial: string; const Codigos: TArray<string>;
  Master: Boolean): TResultadoCandidatos;
var
  P: TProdutoDemo;
  C, Campo: string;
  O: TOrigemVinculo;
begin
  if FFalhar then
    Exit(Indisponivel(MSG_FALHA));
  Result := Default(TResultadoCandidatos);
  if Master then
    O := ovBarrasMaster
  else
    O := ovBarrasVenda;
  for P in FProdutos do
  begin
    if Master then
      Campo := P.CodAuxiliar2
    else
      Campo := P.CodAuxiliar;
    if Campo = '' then
      Continue;
    for C in Codigos do
      if C = Campo then
      begin
        SetLength(Result.Candidatos, Length(Result.Candidatos) + 1);
        Result.Candidatos[High(Result.Candidatos)] := Candidato(P, O, C);
      end;
  end;
end;

function TProvedorDemo.ProdutosPorCodFab203(const Filial: string;
  const Codigos: TArray<string>): TResultadoCandidatos;
var
  P: TProdutoDemo;
  C: string;
begin
  if FFalhar then
    Exit(Indisponivel(MSG_FALHA));
  Result := Default(TResultadoCandidatos);
  for P in FProdutos do
    if P.CodFab <> '' then
      for C in Codigos do
        if SameText(C, P.CodFab) then
        begin
          SetLength(Result.Candidatos, Length(Result.Candidatos) + 1);
          Result.Candidatos[High(Result.Candidatos)] := Candidato(P, ovCodFab203, C);
        end;
end;

function TProvedorDemo.ProdutosPorCodFab253(const Filial: string; CodFornec: Integer;
  const Codigos: TArray<string>): TResultadoCandidatos;
var
  V: TVinculo253Demo;
  P: TProdutoDemo;
  C: string;
  Cand: TCandidatoProduto;
begin
  if FFalhar then
    Exit(Indisponivel(MSG_FALHA));
  Result := Default(TResultadoCandidatos);
  for V in FVinculos do
    if V.CodFornec = CodFornec then
      for C in Codigos do
        if SameText(C, V.CodFab) and ProdutoPorCodigo(V.CodProd, P) then
        begin
          Cand := Candidato(P, ovCodFab253, C);
          Cand.CodFornec := CodFornec;
          Cand.FatorVinculo := V.Fator;
          SetLength(Result.Candidatos, Length(Result.Candidatos) + 1);
          Result.Candidatos[High(Result.Candidatos)] := Cand;
        end;
end;

function TProvedorDemo.RestricoesImportacao(const Filial: string; CodFornec: Integer;
  const CodProds: TArray<Integer>): TResultadoRestricoes;
var
  R: TRestricao;
  C: Integer;
begin
  Result := Default(TResultadoRestricoes);
  if FFalhar then
  begin
    Result.Status := scIndisponivel;
    Result.Mensagem := MSG_FALHA;
    Exit;
  end;
  for R in FRestricoes do
    for C in CodProds do
      if R.CodProd = C then
      begin
        SetLength(Result.Restricoes, Length(Result.Restricoes) + 1);
        Result.Restricoes[High(Result.Restricoes)] := R;
      end;
end;

function TProvedorDemo.CustosReferencia(const Filial: string;
  const CodProds: TArray<Integer>): TResultadoCustos;
var
  K: TCustoReferencia;
  C: Integer;
begin
  Result := Default(TResultadoCustos);
  if FFalhar then
  begin
    Result.Status := scIndisponivel;
    Result.Mensagem := MSG_FALHA;
    Exit;
  end;
  for K in FCustos do
    if K.Filial = Filial then
      for C in CodProds do
        if K.CodProd = C then
        begin
          SetLength(Result.Custos, Length(Result.Custos) + 1);
          Result.Custos[High(Result.Custos)] := K;
        end;
end;

function TProvedorDemo.NotaJaLancada(const Chave: string; CodFornec: Integer;
  const Numero, Serie: string): TResultadoLancada;
var
  C: string;
begin
  Result := Default(TResultadoLancada);
  if FFalhar then
  begin
    Result.Resultado := jlIndisponivel;
    Result.Mensagem := MSG_FALHA;
    Exit;
  end;
  Result.Resultado := jlNao;
  for C in FChavesLancadas do
    if C = Chave then
    begin
      Result.Resultado := jlSim;
      Result.Mensagem := 'pré-entrada encerrada (simulação).';
      Result.Referencia := 'Transação 9999 (demo)';
    end;
end;

end.
