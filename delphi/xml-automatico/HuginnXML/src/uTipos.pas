unit uTipos;

{ HUGINN XML Automatico - tipos compartilhados entre leitura do XML, motor,
  provedores de dados e tela. Nenhuma unit deste projeto grava no WinThor. }

interface

uses
  System.SysUtils;

const
  VERSAO_APP   = '0.1.0';
  VERSAO_REGRA = 'R2-2026-11-21';   // muda quando a regra de conciliacao mudar

type
  { Resultado tecnico de uma consulta ao provedor (banco ou demonstracao). }
  TStatusConsulta = (scOk, scIndisponivel);

  { Gravidade, em ordem crescente. Bloqueio = falha tecnica que impede a analise. }
  TNivel = (nvOk, nvAlerta, nvPendencia, nvBloqueio);

  TSituacao = (siNaoAvaliado, siConfirmado, siPossivelDuplicidade, siAusente,
               siAmbiguo, siIndisponivel);

  { Formas de localizar o produto - as mesmas da tela de importacao da 1301. }
  TOrigemVinculo = (
    ovBarrasVenda,    // 1 - Codigo de Barras (UN Venda)   -> PCPRODUT.CODAUXILIAR
    ovBarrasMaster,   // 2 - Codigo de Barras (UN Master)  -> PCPRODUT.CODAUXILIAR2
    ovCodFab203,      // 3 - Codigo de Fab. (Rotina 203)   -> PCPRODUT.CODFAB
    ovCodFab253);     // 4 - Codigo de Fab. (Rotina 253)   -> PCCODFABRICA (por fornecedor)

  TModoPesquisa = (
    mpBarrasVenda, mpBarrasMaster, mpCodFab203, mpCodFab253,
    mpAutomatica,     // 5 - ordem a confirmar por trace (hoje: 203, 253, barras venda, barras master)
    mpEanDinamico);   // 6 - EAN Dinamico (Rotina 253): a homologar

  TJaLancada = (jlNao, jlSim, jlIndisponivel);

  { ---------- XML ---------- }

  TItemXML = record
    NItem: Integer;
    CProd, CEAN, CEANTrib, XProd, NCM, CEST, CFOP, UCom, UTrib: string;
    QCom, VUnCom, VProd, QTrib, VUnTrib: Double;
    VDesc, VFrete, VSeg, VOutro: Double;
    VICMS, VICMSST, VIPI: Double;
  end;

  TNotaXML = record
    Chave, Versao, Modelo, Serie, Numero, DataEmissao, TpNF, TpAmb: string;
    EmitCNPJ, EmitNome, EmitIE, EmitUF: string;
    DestCNPJ, DestNome, DestIE: string;
    TemProtocolo: Boolean;
    Protocolo, CStatProt, ChaveProt: string;
    VNF, VProdTotal, VICMSTotal, VSTTotal, VIPITotal: Double;
    Itens: TArray<TItemXML>;
    Sha256: string;          // hash dos bytes recebidos, em hexadecimal minusculo
    TamanhoBytes: Int64;
    Avisos: TArray<string>;  // inconsistencias de leitura que nao impedem a analise
  end;

  { ---------- Provedor de dados (somente leitura) ---------- }

  TFilial = record
    Codigo: string;          // PCFILIAL.CODIGO (texto no WinThor)
    Nome, CNPJ: string;
  end;

  TResultadoFiliais = record
    Status: TStatusConsulta;
    Mensagem: string;
    Filiais: TArray<TFilial>;
  end;

  TFornecedor = record
    Codigo: Integer;
    Nome, CNPJ: string;
    Bloqueado: Boolean;
    Revenda: Boolean;        // NVL(REVENDA,'S') IN ('S','O','X'), regra vista na 1301
  end;

  TResultadoFornecedores = record
    Status: TStatusConsulta;
    Mensagem: string;
    Fornecedores: TArray<TFornecedor>;
  end;

  TCandidatoProduto = record
    CodProd: Integer;
    Descricao, Unidade, Embalagem, NCM, CEST: string;
    QtUnitCx: Double;        // PCPRODUT.QTUNITCX (0/nulo = 1 na 1301)
    Origem: TOrigemVinculo;
    Identificador: string;   // o EAN ou o codigo de fabrica que casou
    CodFornec: Integer;      // so para Origem = ovCodFab253
    FatorVinculo: Double;    // fator de conversao da 253; 0 = desconhecido
  end;

  TResultadoCandidatos = record
    Status: TStatusConsulta;
    Mensagem: string;
    Candidatos: TArray<TCandidatoProduto>;
  end;

  { Restricao que a 1301 aponta na validacao dos produtos (consulta vista no trace). }
  TRestricao = record
    CodProd: Integer;
    Codigo: string;          // ex.: SEM_PCEST, FORA_DE_LINHA
    Mensagem, Acao: string;
  end;

  TResultadoRestricoes = record
    Status: TStatusConsulta;
    Mensagem: string;
    Restricoes: TArray<TRestricao>;
  end;

  { Custos da ultima entrada mantidos pelo WinThor em PCEST, por produto e filial. }
  TCustoReferencia = record
    CodProd: Integer;
    Filial: string;
    PLiqUltEnt: Double;      // preco liquido da ultima entrada (base da comparacao)
    CustoUltEnt: Double;
    CustoUltEntFin: Double;
  end;

  TResultadoCustos = record
    Status: TStatusConsulta;
    Mensagem: string;
    Custos: TArray<TCustoReferencia>;
  end;

  TResultadoLancada = record
    Resultado: TJaLancada;
    Mensagem: string;
    Referencia: string;
  end;

  { ---------- Resultado da analise ---------- }

  TAchado = record
    Nivel: TNivel;
    Campo, ValorXML, ValorWinThor, Origem, Mensagem, Acao: string;
  end;

  TResultadoItem = record
    Item: TItemXML;
    Situacao: TSituacao;
    Produto: TCandidatoProduto;      // valido se Situacao = siConfirmado
    Evidencia: string;
    TemCustoReferencia: Boolean;
    Custo: TCustoReferencia;
    CustoComparavel: Boolean;
    FatorAplicado: Double;
    CustoXMLNormalizado: Double;
    VariacaoPct: Double;
    MemoriaCalculo: string;
    Achados: TArray<TAchado>;
    Nivel: TNivel;
  end;

  TResultadoAnalise = record
    Nota: TNotaXML;
    Provedor: string;
    ModoPesquisa: TModoPesquisa;
    DataHora: TDateTime;
    FilialStatus: TSituacao;
    Filial: TFilial;
    FiliaisCandidatas: TArray<TFilial>;
    FornecedorStatus: TSituacao;
    Fornecedores: TArray<TFornecedor>;
    JaLancada: TResultadoLancada;
    AchadosNota: TArray<TAchado>;
    Itens: TArray<TResultadoItem>;
    TotalItens, Identificados, Divergencias, CadastrosPendentes, SemComparacao: Integer;
    Nivel: TNivel;
    PodeLiberar: Boolean;
    MotivoBloqueio: string;
  end;

function NivelTexto(N: TNivel): string;
function SituacaoTexto(S: TSituacao): string;
function OrigemTexto(O: TOrigemVinculo): string;
function ModoPesquisaTexto(M: TModoPesquisa): string;
function MaiorNivel(A, B: TNivel): TNivel;
function NovoAchado(ANivel: TNivel; const ACampo, AValorXML, AValorWinThor,
  AOrigem, AMensagem, AAcao: string): TAchado;
procedure AdicionarAchado(var Lista: TArray<TAchado>; const A: TAchado);
function FmtNum(V: Double; Casas: Integer = 2): string;

implementation

function NivelTexto(N: TNivel): string;
begin
  case N of
    nvOk:        Result := 'OK';
    nvAlerta:    Result := 'Alerta';
    nvPendencia: Result := 'Pendência';
    nvBloqueio:  Result := 'Falha técnica';
  else
    Result := '?';
  end;
end;

function SituacaoTexto(S: TSituacao): string;
begin
  case S of
    siNaoAvaliado:         Result := 'Não avaliado';
    siConfirmado:          Result := 'Confirmado';
    siPossivelDuplicidade: Result := 'Possível duplicidade';
    siAusente:             Result := 'Não encontrado';
    siAmbiguo:             Result := 'Ambíguo';
    siIndisponivel:        Result := 'Consulta indisponível';
  else
    Result := '?';
  end;
end;

function OrigemTexto(O: TOrigemVinculo): string;
begin
  case O of
    ovBarrasVenda:  Result := 'Cód. barras UN venda';
    ovBarrasMaster: Result := 'Cód. barras UN master';
    ovCodFab203:    Result := 'Cód. fábrica (203)';
    ovCodFab253:    Result := 'Cód. fábrica (253)';
  else
    Result := '?';
  end;
end;

function ModoPesquisaTexto(M: TModoPesquisa): string;
begin
  case M of
    mpBarrasVenda:  Result := '1 - Código de Barras (UN - Venda)';
    mpBarrasMaster: Result := '2 - Código de Barras (UN - Master)';
    mpCodFab203:    Result := '3 - Código de Fab. (Rotina 203)';
    mpCodFab253:    Result := '4 - Código de Fab. (Rotina 253)';
    mpAutomatica:   Result := '5 - Pesquisa Automática';
    mpEanDinamico:  Result := '6 - EAN Dinâmico (Rotina 253)';
  else
    Result := '?';
  end;
end;

function MaiorNivel(A, B: TNivel): TNivel;
begin
  if Ord(A) >= Ord(B) then
    Result := A
  else
    Result := B;
end;

function NovoAchado(ANivel: TNivel; const ACampo, AValorXML, AValorWinThor,
  AOrigem, AMensagem, AAcao: string): TAchado;
begin
  Result.Nivel := ANivel;
  Result.Campo := ACampo;
  Result.ValorXML := AValorXML;
  Result.ValorWinThor := AValorWinThor;
  Result.Origem := AOrigem;
  Result.Mensagem := AMensagem;
  Result.Acao := AAcao;
end;

procedure AdicionarAchado(var Lista: TArray<TAchado>; const A: TAchado);
begin
  SetLength(Lista, Length(Lista) + 1);
  Lista[High(Lista)] := A;
end;

function FmtNum(V: Double; Casas: Integer): string;
begin
  if Casas <= 0 then
    Result := FormatFloat('#,##0', V)
  else
    Result := FormatFloat('#,##0.' + StringOfChar('0', Casas), V);
end;

end.
