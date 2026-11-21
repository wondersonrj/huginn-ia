unit uProvedor;

{ HUGINN XML Automatico - contrato do provedor de dados.

  O motor de conciliacao so conversa com esta interface. Existem duas
  implementacoes: TProvedorDemo (dados ficticios, sem banco) e TProvedorOracle
  (UniDAC, somente SELECT). Toda consulta devolve Status/Mensagem: uma falha de
  conexao ou de permissao vira "consulta indisponivel", nunca "nao encontrado". }

interface

uses
  uTipos;

type
  IProvedorDados = interface
    ['{6A1F2C40-9B3E-4C7A-8D21-5E4F0B9C7A11}']
    function Nome: string;
    function EhDemonstracao: Boolean;
    function FiliaisPorCNPJ(const CNPJ: string): TResultadoFiliais;
    function FornecedoresPorCNPJ(const CNPJ: string): TResultadoFornecedores;
    { Busca em lote, uma consulta por forma de pesquisa (nao uma por item). }
    function ProdutosPorBarras(const Filial: string; const Codigos: TArray<string>;
      Master: Boolean): TResultadoCandidatos;
    function ProdutosPorCodFab203(const Filial: string; const Codigos: TArray<string>): TResultadoCandidatos;
    function ProdutosPorCodFab253(const Filial: string; CodFornec: Integer;
      const Codigos: TArray<string>): TResultadoCandidatos;
    { Mesma validacao que a 1301 faz antes de importar (produto x filial x fornecedor). }
    function RestricoesImportacao(const Filial: string; CodFornec: Integer;
      const CodProds: TArray<Integer>): TResultadoRestricoes;
    function CustosReferencia(const Filial: string; const CodProds: TArray<Integer>): TResultadoCustos;
    { Nota ja lancada (PCNFENT) ou com pre-entrada (PCNFENTPREENT). }
    function NotaJaLancada(const Chave: string; CodFornec: Integer; const Numero, Serie: string): TResultadoLancada;
  end;

function Indisponivel(const Msg: string): TResultadoCandidatos;

implementation

function Indisponivel(const Msg: string): TResultadoCandidatos;
begin
  Result := Default(TResultadoCandidatos);
  Result.Status := scIndisponivel;
  Result.Mensagem := Msg;
end;

end.
