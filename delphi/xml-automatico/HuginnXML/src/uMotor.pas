unit uMotor;

{ HUGINN XML Automatico - motor de conciliacao (sem tela e sem banco).

  Regra principal: localizar o produto DO MESMO JEITO que a 1301 vai localizar
  (modo de pesquisa configurado), para que a conferencia do HUGINN e a validacao
  do WinThor nunca discordem. As outras formas de busca servem de evidencia e
  para detectar conflito de identificadores.

  Nenhuma decisao aqui grava no ERP. O resultado e orientativo. }

interface

uses
  uTipos, uProvedor;

type
  TParametrosMotor = record
    ModoPesquisa: TModoPesquisa;
    OrdemAutomatica: TArray<TOrigemVinculo>;  // ordem da "Pesquisa Automatica" (a confirmar)
    UsarFator253: Boolean;                    // espelha "Utilizar fator de conversao da rotina 253"
    ToleranciaCustoPct: Double;               // acima disso, alerta de custo
  end;

function ParametrosPadrao: TParametrosMotor;
function OrigensDoModo(const P: TParametrosMotor): TArray<TOrigemVinculo>;
function AnalisarNota(const Nota: TNotaXML; const Prov: IProvedorDados;
  const P: TParametrosMotor; const FilialEscolhida: string = ''): TResultadoAnalise;

implementation

uses
  System.SysUtils, System.Math, System.StrUtils, uValidacao;

function ParametrosPadrao: TParametrosMotor;
begin
  Result.ModoPesquisa := mpAutomatica;
  // Ordem observada no trace da 1301 (203 e depois 253). Barras: a confirmar.
  Result.OrdemAutomatica := [ovCodFab203, ovCodFab253, ovBarrasVenda, ovBarrasMaster];
  Result.UsarFator253 := True;
  Result.ToleranciaCustoPct := 5.0;
end;

function OrigensDoModo(const P: TParametrosMotor): TArray<TOrigemVinculo>;
begin
  case P.ModoPesquisa of
    mpBarrasVenda:  Result := [ovBarrasVenda];
    mpBarrasMaster: Result := [ovBarrasMaster];
    mpCodFab203:    Result := [ovCodFab203];
    mpCodFab253:    Result := [ovCodFab253];
    mpEanDinamico:  Result := [ovCodFab253, ovBarrasVenda, ovBarrasMaster]; // a homologar
  else
    Result := P.OrdemAutomatica;
  end;
end;

{ ---------- auxiliares ---------- }

procedure AddTexto(var L: TArray<string>; const S: string);
var
  X: string;
begin
  if Trim(S) = '' then
    Exit;
  for X in L do
    if SameText(X, S) then
      Exit;
  SetLength(L, Length(L) + 1);
  L[High(L)] := Trim(S);
end;

procedure AddInt(var L: TArray<Integer>; V: Integer);
var
  X: Integer;
begin
  for X in L do
    if X = V then
      Exit;
  SetLength(L, Length(L) + 1);
  L[High(L)] := V;
end;

procedure AddCandidatos(var Destino: TArray<TCandidatoProduto>; const R: TResultadoCandidatos);
var
  C: TCandidatoProduto;
begin
  for C in R.Candidatos do
  begin
    SetLength(Destino, Length(Destino) + 1);
    Destino[High(Destino)] := C;
  end;
end;

function GtinsDoItem(const It: TItemXML; Master: Boolean): TArray<string>;
begin
  Result := nil;
  if Master then
  begin
    if GTINValido(It.CEANTrib) then
      AddTexto(Result, It.CEANTrib);
    if GTINValido(It.CEAN) then
      AddTexto(Result, It.CEAN);
  end
  else
  begin
    if GTINValido(It.CEAN) then
      AddTexto(Result, It.CEAN);
    if GTINValido(It.CEANTrib) then
      AddTexto(Result, It.CEANTrib);
  end;
end;

function IdentificadoresDoItem(const It: TItemXML; O: TOrigemVinculo): TArray<string>;
begin
  case O of
    ovBarrasVenda:  Result := GtinsDoItem(It, False);
    ovBarrasMaster: Result := GtinsDoItem(It, True);
  else
    Result := nil;
    AddTexto(Result, It.CProd);
  end;
end;

{ Candidatos de uma origem que casam com um item. }
function CandidatosDoItem(const It: TItemXML; O: TOrigemVinculo;
  const Todos: TArray<TCandidatoProduto>): TArray<TCandidatoProduto>;
var
  C: TCandidatoProduto;
  Ids: TArray<string>;
  Id: string;
begin
  Result := nil;
  Ids := IdentificadoresDoItem(It, O);
  for C in Todos do
    if C.Origem = O then
      for Id in Ids do
        if SameText(C.Identificador, Id) then
        begin
          SetLength(Result, Length(Result) + 1);
          Result[High(Result)] := C;
          Break;
        end;
end;

function ProdutosDistintos(const L: TArray<TCandidatoProduto>): TArray<Integer>;
var
  C: TCandidatoProduto;
begin
  Result := nil;
  for C in L do
    AddInt(Result, C.CodProd);
end;

function ListaCodigos(const L: TArray<Integer>): string;
var
  V: Integer;
begin
  Result := '';
  for V in L do
  begin
    if Result <> '' then
      Result := Result + ', ';
    Result := Result + IntToStr(V);
  end;
end;

procedure Achar(var R: TResultadoItem; Nivel: TNivel; const Campo, VXml, VWt,
  Origem, Msg, Acao: string);
begin
  AdicionarAchado(R.Achados, NovoAchado(Nivel, Campo, VXml, VWt, Origem, Msg, Acao));
  R.Nivel := MaiorNivel(R.Nivel, Nivel);
end;

procedure AcharNota(var A: TResultadoAnalise; Nivel: TNivel; const Campo, VXml, VWt,
  Origem, Msg, Acao: string);
begin
  AdicionarAchado(A.AchadosNota, NovoAchado(Nivel, Campo, VXml, VWt, Origem, Msg, Acao));
  A.Nivel := MaiorNivel(A.Nivel, Nivel);
end;

{ ---------- etapas ---------- }

procedure ResolverFilial(var A: TResultadoAnalise; const Prov: IProvedorDados;
  const FilialEscolhida: string);
var
  RF: TResultadoFiliais;
  F: TFilial;
begin
  RF := Prov.FiliaisPorCNPJ(SoDigitos(A.Nota.DestCNPJ));
  A.FiliaisCandidatas := RF.Filiais;
  if FilialEscolhida <> '' then
  begin
    A.FilialStatus := siConfirmado;
    A.Filial := Default(TFilial);
    A.Filial.Codigo := FilialEscolhida;
    for F in RF.Filiais do
      if F.Codigo = FilialEscolhida then
        A.Filial := F;
    if (RF.Status = scOk) and (A.Filial.CNPJ = '') then
      AcharNota(A, nvAlerta, 'Filial', A.Nota.DestCNPJ, FilialEscolhida, 'Operador',
        'A filial escolhida pelo operador não tem o CNPJ do destinatário da nota.',
        'Confirme se a nota é realmente desta filial.');
    Exit;
  end;
  if RF.Status <> scOk then
  begin
    A.FilialStatus := siIndisponivel;
    AcharNota(A, nvBloqueio, 'Filial', A.Nota.DestCNPJ, '', 'PCFILIAL',
      'Não foi possível consultar a filial: ' + RF.Mensagem, 'Verifique a conexão e reanalise.');
  end
  else if Length(RF.Filiais) = 0 then
  begin
    A.FilialStatus := siAusente;
    AcharNota(A, nvPendencia, 'Filial', A.Nota.DestCNPJ, '', 'PCFILIAL',
      'O CNPJ do destinatário não corresponde a nenhuma filial cadastrada.',
      'Confira se a nota foi emitida para esta empresa. Sem filial não há comparação de custo.');
  end
  else if Length(RF.Filiais) > 1 then
  begin
    A.FilialStatus := siAmbiguo;
    AcharNota(A, nvPendencia, 'Filial', A.Nota.DestCNPJ, IntToStr(Length(RF.Filiais)) + ' filiais',
      'PCFILIAL', 'Mais de uma filial tem o CNPJ do destinatário.',
      'Escolha a filial e clique em Reanalisar.');
  end
  else
  begin
    A.FilialStatus := siConfirmado;
    A.Filial := RF.Filiais[0];
  end;
end;

procedure ResolverFornecedor(var A: TResultadoAnalise; const Prov: IProvedorDados);
var
  RF: TResultadoFornecedores;
  F: TFornecedor;
  Codigos: string;
begin
  RF := Prov.FornecedoresPorCNPJ(SoDigitos(A.Nota.EmitCNPJ));
  A.Fornecedores := RF.Fornecedores;
  if RF.Status <> scOk then
  begin
    A.FornecedorStatus := siIndisponivel;
    AcharNota(A, nvBloqueio, 'Fornecedor', A.Nota.EmitCNPJ, '', 'PCFORNEC',
      'Não foi possível consultar o fornecedor: ' + RF.Mensagem, 'Verifique a conexão e reanalise.');
    Exit;
  end;
  if Length(RF.Fornecedores) = 0 then
  begin
    A.FornecedorStatus := siAusente;
    AcharNota(A, nvPendencia, 'Fornecedor', A.Nota.EmitCNPJ + ' - ' + A.Nota.EmitNome, '',
      'PCFORNEC', 'Fornecedor não cadastrado no WinThor.',
      Format('Cadastre na rotina nativa com os dados do XML: CNPJ %s, razão social %s, IE %s, UF %s. Depois clique em Reanalisar.',
        [A.Nota.EmitCNPJ, A.Nota.EmitNome, A.Nota.EmitIE, A.Nota.EmitUF]));
    Exit;
  end;
  if Length(RF.Fornecedores) > 1 then
  begin
    A.FornecedorStatus := siPossivelDuplicidade;
    Codigos := '';
    for F in RF.Fornecedores do
      Codigos := Codigos + IfThen(Codigos <> '', ', ', '') + IntToStr(F.Codigo);
    AcharNota(A, nvAlerta, 'Fornecedor', A.Nota.EmitCNPJ, Codigos, 'PCFORNEC',
      'O CNPJ está em mais de um cadastro de fornecedor (possível duplicidade).',
      'Confira qual código a 1301 vai usar e revise os cadastros repetidos.');
  end
  else
    A.FornecedorStatus := siConfirmado;
  for F in RF.Fornecedores do
  begin
    if F.Bloqueado then
      AcharNota(A, nvAlerta, 'Fornecedor', '', IntToStr(F.Codigo) + ' bloqueado', 'PCFORNEC.BLOQUEIO',
        'Fornecedor bloqueado no WinThor.', 'Confira o motivo do bloqueio antes da entrada.');
    if not F.Revenda then
      AcharNota(A, nvPendencia, 'Fornecedor', '', IntToStr(F.Codigo), 'PCFORNEC.REVENDA',
        'A 1301 recusa: fornecedor não está cadastrado como Revenda = SIM.',
        'Ajuste o cadastro do fornecedor na rotina nativa.');
  end;
end;

procedure AvaliarCusto(var R: TResultadoItem; const A: TResultadoAnalise;
  const Custos: TResultadoCustos; const P: TParametrosMotor);
var
  C: TCustoReferencia;
  Base: Double;
  Achou: Boolean;
begin
  R.CustoComparavel := False;
  // 1) Fator de conversao da unidade do XML para a unidade do produto no WinThor.
  R.FatorAplicado := 0;
  if (R.Produto.Origem = ovCodFab253) and P.UsarFator253 and (R.Produto.FatorVinculo > 0) then
  begin
    R.FatorAplicado := R.Produto.FatorVinculo;
    R.MemoriaCalculo := Format('Fator %s da rotina 253 (código %s).',
      [FmtNum(R.FatorAplicado, 4), R.Produto.Identificador]);
  end
  else if MesmaUnidade(R.Item.UCom, R.Produto.Unidade) then
  begin
    R.FatorAplicado := 1;
    R.MemoriaCalculo := Format('Unidade do XML (%s) igual à do produto: fator 1.', [R.Item.UCom]);
  end
  else if (R.Produto.Origem = ovBarrasMaster) and (R.Produto.QtUnitCx > 0) then
  begin
    R.FatorAplicado := R.Produto.QtUnitCx;
    R.MemoriaCalculo := Format('Código de barras master: fator QTUNITCX = %s.', [FmtNum(R.FatorAplicado, 4)]);
  end;

  if R.FatorAplicado <= 0 then
  begin
    Achar(R, nvAlerta, 'Unidade', R.Item.UCom, R.Produto.Unidade, 'PCPRODUT.UNIDADE',
      Format('Comparação de custo indisponível: a unidade do XML (%s) é diferente da do produto (%s) e não há fator homologado.%s',
        [R.Item.UCom, R.Produto.Unidade,
         IfThen(R.Produto.QtUnitCx > 1, Format(' O cadastro tem QTUNITCX = %s, que pode ser o fator.', [FmtNum(R.Produto.QtUnitCx, 0)]), '')]),
      'Cadastre o fator de conversão na rotina 253 (código de fábrica) e reanalise.');
    Exit;
  end;
  if (R.Item.QCom <= 0) then
  begin
    Achar(R, nvAlerta, 'Quantidade', FmtNum(R.Item.QCom, 4), '', 'XML',
      'Quantidade zerada: comparação de custo indisponível.', 'Confira o XML.');
    Exit;
  end;

  // 2) Custo do XML na unidade do produto. v0.1: valor do produto menos desconto.
  Base := R.Item.VProd - R.Item.VDesc;
  R.CustoXMLNormalizado := Base / (R.Item.QCom * R.FatorAplicado);
  R.MemoriaCalculo := R.MemoriaCalculo + sLineBreak + Format(
    'Custo XML = (vProd %s - vDesc %s) / (qCom %s x fator %s) = %s por %s. ' +
    'Frete, seguro, outras despesas, IPI e ST não incluídos nesta versão.',
    [FmtNum(R.Item.VProd), FmtNum(R.Item.VDesc), FmtNum(R.Item.QCom, 4),
     FmtNum(R.FatorAplicado, 4), FmtNum(R.CustoXMLNormalizado, 4), R.Produto.Unidade]);

  // 3) Referencia: PCEST da filial (mantido pelo proprio WinThor a cada entrada).
  if A.FilialStatus <> siConfirmado then
  begin
    Achar(R, nvAlerta, 'Custo', FmtNum(R.CustoXMLNormalizado, 4), '', 'PCEST',
      'Comparação de custo indisponível: filial não confirmada.', 'Confirme a filial e reanalise.');
    Exit;
  end;
  if Custos.Status <> scOk then
  begin
    Achar(R, nvBloqueio, 'Custo', FmtNum(R.CustoXMLNormalizado, 4), '', 'PCEST',
      'Não foi possível consultar o custo da última entrada: ' + Custos.Mensagem, 'Verifique a conexão e reanalise.');
    Exit;
  end;
  Achou := False;
  for C in Custos.Custos do
    if (C.CodProd = R.Produto.CodProd) and (C.Filial = A.Filial.Codigo) then
    begin
      R.Custo := C;
      Achou := True;
      Break;
    end;
  R.TemCustoReferencia := Achou;
  if (not Achou) or (R.Custo.PLiqUltEnt <= 0) then
  begin
    Achar(R, nvAlerta, 'Custo', FmtNum(R.CustoXMLNormalizado, 4), 'sem entrada anterior', 'PCEST.PLIQULTENT',
      'Sem preço da última entrada nesta filial (primeira compra ou custo zerado): comparação indisponível.',
      'Confira o preço com o pedido ou a negociação.');
    Exit;
  end;
  R.CustoComparavel := True;
  R.VariacaoPct := (R.CustoXMLNormalizado / R.Custo.PLiqUltEnt - 1) * 100;
  R.MemoriaCalculo := R.MemoriaCalculo + sLineBreak + Format(
    'Última entrada (PCEST.PLIQULTENT, filial %s) = %s. Variação = (%s / %s - 1) x 100 = %s%%.',
    [A.Filial.Codigo, FmtNum(R.Custo.PLiqUltEnt, 4), FmtNum(R.CustoXMLNormalizado, 4),
     FmtNum(R.Custo.PLiqUltEnt, 4), FmtNum(R.VariacaoPct, 2)]);
  if Abs(R.VariacaoPct) > P.ToleranciaCustoPct then
    Achar(R, nvAlerta, 'Custo', FmtNum(R.CustoXMLNormalizado, 4), FmtNum(R.Custo.PLiqUltEnt, 4),
      'PCEST.PLIQULTENT',
      Format('Custo %s%% %s da última entrada (tolerância %s%%).',
        [FmtNum(Abs(R.VariacaoPct), 2), IfThen(R.VariacaoPct > 0, 'acima', 'abaixo'),
         FmtNum(P.ToleranciaCustoPct, 1)]),
      'Confira com o comprador antes da entrada. O HUGINN não altera custo nem preço.');
end;

procedure ConferirCadastro(var R: TResultadoItem);
begin
  // PCPRODUT.CODNCMEX pode trazer a excecao depois do NCM: compara os 8 primeiros digitos.
  if (SoDigitos(R.Item.NCM) <> '') and (SoDigitos(R.Produto.NCM) <> '') and
     (Copy(SoDigitos(R.Item.NCM), 1, 8) <> Copy(SoDigitos(R.Produto.NCM), 1, 8)) then
    Achar(R, nvAlerta, 'NCM', R.Item.NCM, R.Produto.NCM, 'PCPRODUT.CODNCMEX',
      'NCM do XML diferente do cadastro.',
      'Orientativo: confirme a classificação com o fiscal. O HUGINN não altera o cadastro.');
  // CEST so e comparado quando o provedor informa o do cadastro (coluna a confirmar no Oracle).
  if (SoDigitos(R.Item.CEST) <> '') and (SoDigitos(R.Produto.CEST) <> '') and
     (SoDigitos(R.Item.CEST) <> SoDigitos(R.Produto.CEST)) then
    Achar(R, nvAlerta, 'CEST', R.Item.CEST, R.Produto.CEST,
      'Cadastro', 'CEST do XML diferente do cadastro.',
      'Orientativo: confirme com o fiscal.');
end;

procedure IdentificarItem(var R: TResultadoItem; const A: TResultadoAnalise;
  const Origens: TArray<TOrigemVinculo>; const Todos: TArray<TCandidatoProduto>;
  const Indisp: TArray<TOrigemVinculo>; const P: TParametrosMotor);
var
  O, OPrincipal: TOrigemVinculo;
  Cands, CandsPrinc, Outros: TArray<TCandidatoProduto>;
  Prods, ProdsOutros: TArray<Integer>;
  C: TCandidatoProduto;
  TemPrincipal, OrigemIndisp: Boolean;
  Ev, Conflitos: string;
  X: TOrigemVinculo;
begin
  CandsPrinc := nil;
  TemPrincipal := False;
  OPrincipal := ovCodFab203;
  OrigemIndisp := False;
  // Primeira origem (na ordem do modo da 1301) que localiza o item.
  for O in Origens do
  begin
    Cands := CandidatosDoItem(R.Item, O, Todos);
    if Length(Cands) > 0 then
    begin
      CandsPrinc := Cands;
      OPrincipal := O;
      TemPrincipal := True;
      Break;
    end;
    for X in Indisp do
      if (X = O) and (Length(IdentificadoresDoItem(R.Item, O)) > 0) then
        OrigemIndisp := True;
  end;

  // Demais origens: evidencia complementar ou conflito.
  Outros := nil;
  for O := Low(TOrigemVinculo) to High(TOrigemVinculo) do
    if (not TemPrincipal) or (O <> OPrincipal) then
    begin
      Cands := CandidatosDoItem(R.Item, O, Todos);
      for C in Cands do
      begin
        SetLength(Outros, Length(Outros) + 1);
        Outros[High(Outros)] := C;
      end;
    end;

  if GTINInformado(R.Item.CEAN) and not GTINValido(R.Item.CEAN) then
    Achar(R, nvAlerta, 'cEAN', R.Item.CEAN, '', 'XML',
      'Código de barras do XML com dígito verificador inválido: não usado na busca.',
      'Informe o fornecedor; a busca usa o código de fábrica.');

  if not TemPrincipal then
  begin
    if OrigemIndisp then
    begin
      R.Situacao := siIndisponivel;
      Achar(R, nvBloqueio, 'Produto', R.Item.CProd, '', 'Consulta',
        'Não foi possível concluir a busca do produto (consulta indisponível).',
        'Verifique a conexão e reanalise.');
      Exit;
    end;
    ProdsOutros := ProdutosDistintos(Outros);
    if Length(ProdsOutros) > 0 then
    begin
      // Existe por outra forma de pesquisa que NAO e a usada pela 1301.
      R.Situacao := siAusente;
      Ev := '';
      for C in Outros do
        Ev := Ev + Format('%s %s -> produto %d; ', [OrigemTexto(C.Origem), C.Identificador, C.CodProd]);
      R.Evidencia := Ev;
      Achar(R, nvPendencia, 'Produto', R.Item.CProd, ListaCodigos(ProdsOutros), 'Pesquisa',
        Format('A 1301 (modo "%s") não vai localizar este item, mas ele existe por outra forma: %s',
          [ModoPesquisaTexto(P.ModoPesquisa), Ev]),
        'Vincule o código de fábrica do fornecedor na rotina 253 (ou ajuste o modo de pesquisa) e reanalise.');
      Exit;
    end;
    R.Situacao := siAusente;
    if A.FornecedorStatus = siAusente then
      Achar(R, nvPendencia, 'Produto', R.Item.CProd + ' / ' + R.Item.CEAN, '', 'Pesquisa',
        'Produto não localizado. O vínculo por código de fábrica (253) só pode ser verificado depois de cadastrar o fornecedor.',
        'Cadastre o fornecedor, reanalise e, se continuar, cadastre ou vincule o produto na rotina nativa.')
    else
      Achar(R, nvPendencia, 'Produto', R.Item.CProd + ' / ' + R.Item.CEAN, '', 'Pesquisa',
        'Candidato a produto novo: não localizado por código de fábrica nem por código de barras.',
        Format('Se já existir, vincule o código %s na rotina 253; se for novo, cadastre na rotina nativa ' +
          '(descrição "%s", NCM %s, unidade %s). Depois clique em Reanalisar.',
          [R.Item.CProd, R.Item.XProd, R.Item.NCM, R.Item.UCom]));
    Exit;
  end;

  Prods := ProdutosDistintos(CandsPrinc);
  if Length(Prods) > 1 then
  begin
    R.Situacao := siAmbiguo;
    Achar(R, nvPendencia, 'Produto', R.Item.CProd, ListaCodigos(Prods), OrigemTexto(OPrincipal),
      'O mesmo identificador aponta para mais de um produto: nenhum vínculo automático.',
      'Corrija os cadastros duplicados e reanalise.');
    Exit;
  end;

  R.Situacao := siConfirmado;
  R.Produto := CandsPrinc[0];
  Ev := Format('%s %s -> produto %d', [OrigemTexto(OPrincipal), R.Produto.Identificador, R.Produto.CodProd]);
  Conflitos := '';
  for C in Outros do
    if C.CodProd = R.Produto.CodProd then
      Ev := Ev + Format('; confirmado por %s %s', [OrigemTexto(C.Origem), C.Identificador])
    else
      Conflitos := Conflitos + Format('%s %s -> produto %d; ', [OrigemTexto(C.Origem), C.Identificador, C.CodProd]);
  R.Evidencia := Ev;
  if Conflitos <> '' then
    Achar(R, nvPendencia, 'Produto', R.Item.CProd, IntToStr(R.Produto.CodProd), 'Pesquisa',
      Format('Conflito: a 1301 vai usar o produto %d (%s), mas outro identificador aponta para outro produto: %s',
        [R.Produto.CodProd, OrigemTexto(OPrincipal), Conflitos]),
      'Confira qual é o produto correto antes da entrada e corrija o vínculo errado.');
end;

{ ---------- analise completa ---------- }

function AnalisarNota(const Nota: TNotaXML; const Prov: IProvedorDados;
  const P: TParametrosMotor; const FilialEscolhida: string): TResultadoAnalise;
var
  A: TResultadoAnalise;
  Origens, Indisp: TArray<TOrigemVinculo>;
  Todos: TArray<TCandidatoProduto>;
  CodsFab, GtinsV, GtinsM: TArray<string>;
  It: TItemXML;
  F: TFornecedor;
  RC: TResultadoCandidatos;
  RR: TResultadoRestricoes;
  RCustos: TResultadoCustos;
  CodProds: TArray<Integer>;
  I, J: Integer;
  S: string;
  Filial: string;
  CodFornecUnico: Integer;
  Restr: TRestricao;

  procedure Registrar(O: TOrigemVinculo; const R: TResultadoCandidatos);
  begin
    if R.Status = scOk then
      AddCandidatos(Todos, R)
    else
    begin
      SetLength(Indisp, Length(Indisp) + 1);
      Indisp[High(Indisp)] := O;
      AcharNota(A, nvAlerta, 'Pesquisa', '', '', OrigemTexto(O),
        'Busca por ' + OrigemTexto(O) + ' indisponível: ' + R.Mensagem, 'Verifique a conexão.');
    end;
  end;

begin
  A := Default(TResultadoAnalise);
  A.Nota := Nota;
  A.Provedor := Prov.Nome;
  A.ModoPesquisa := P.ModoPesquisa;
  A.DataHora := Now;
  A.Nivel := nvOk;

  for S in Nota.Avisos do
    AcharNota(A, nvAlerta, 'XML', '', '', 'Leitura do XML', S, 'Confira o documento.');

  ResolverFilial(A, Prov, FilialEscolhida);
  ResolverFornecedor(A, Prov);
  if A.FilialStatus = siConfirmado then
    Filial := A.Filial.Codigo
  else
    Filial := '';

  CodFornecUnico := 0;
  if A.FornecedorStatus = siConfirmado then
    CodFornecUnico := A.Fornecedores[0].Codigo;

  // Nota ja lancada / pre-entrada existente.
  A.JaLancada := Prov.NotaJaLancada(Nota.Chave, CodFornecUnico, Nota.Numero, Nota.Serie);
  case A.JaLancada.Resultado of
    jlSim:
      AcharNota(A, nvPendencia, 'Nota', Nota.Chave, A.JaLancada.Referencia, 'PCNFENT / PCNFENTPREENT',
        'Esta nota já consta no WinThor: ' + A.JaLancada.Mensagem,
        'Não importe de novo. Confira a entrada/pré-entrada existente.');
    jlIndisponivel:
      AcharNota(A, nvAlerta, 'Nota', Nota.Chave, '', 'PCNFENT / PCNFENTPREENT',
        'Não foi possível verificar se a nota já foi lançada: ' + A.JaLancada.Mensagem,
        'A 1301 fará a própria verificação.');
  end;

  // Buscas em lote: todas as formas, para evidencia e deteccao de conflito.
  Origens := OrigensDoModo(P);
  CodsFab := nil;
  GtinsV := nil;
  GtinsM := nil;
  for It in Nota.Itens do
  begin
    AddTexto(CodsFab, It.CProd);
    for S in GtinsDoItem(It, False) do
      AddTexto(GtinsV, S);
    for S in GtinsDoItem(It, True) do
      AddTexto(GtinsM, S);
  end;
  Todos := nil;
  Indisp := nil;
  if Length(CodsFab) > 0 then
  begin
    Registrar(ovCodFab203, Prov.ProdutosPorCodFab203(Filial, CodsFab));
    for F in A.Fornecedores do
      Registrar(ovCodFab253, Prov.ProdutosPorCodFab253(Filial, F.Codigo, CodsFab));
  end;
  if Length(GtinsV) > 0 then
    Registrar(ovBarrasVenda, Prov.ProdutosPorBarras(Filial, GtinsV, False));
  if Length(GtinsM) > 0 then
    Registrar(ovBarrasMaster, Prov.ProdutosPorBarras(Filial, GtinsM, True));

  SetLength(A.Itens, Length(Nota.Itens));
  CodProds := nil;
  for I := 0 to High(Nota.Itens) do
  begin
    A.Itens[I] := Default(TResultadoItem);
    A.Itens[I].Item := Nota.Itens[I];
    A.Itens[I].Nivel := nvOk;
    IdentificarItem(A.Itens[I], A, Origens, Todos, Indisp, P);
    if A.Itens[I].Situacao = siConfirmado then
      AddInt(CodProds, A.Itens[I].Produto.CodProd);
  end;

  // Restricoes da 1301 e custos de referencia: uma consulta cada.
  RR := Default(TResultadoRestricoes);
  RCustos := Default(TResultadoCustos);
  if (Length(CodProds) > 0) and (Filial <> '') then
  begin
    RR := Prov.RestricoesImportacao(Filial, CodFornecUnico, CodProds);
    RCustos := Prov.CustosReferencia(Filial, CodProds);
    if RR.Status <> scOk then
      AcharNota(A, nvAlerta, 'Validação 1301', '', '', 'Consulta',
        'Não foi possível antecipar as validações da 1301: ' + RR.Mensagem, 'A 1301 fará a própria validação.');
  end;

  for I := 0 to High(A.Itens) do
  begin
    if A.Itens[I].Situacao <> siConfirmado then
      Continue;
    ConferirCadastro(A.Itens[I]);
    if RR.Status = scOk then
      for Restr in RR.Restricoes do
        if Restr.CodProd = A.Itens[I].Produto.CodProd then
          Achar(A.Itens[I], nvPendencia, 'Validação 1301', '', Restr.Codigo, 'Validação de produtos da 1301',
            'A 1301 vai apontar: ' + Restr.Mensagem, Restr.Acao);
    AvaliarCusto(A.Itens[I], A, RCustos, P);
  end;

  // Totalizadores.
  A.TotalItens := Length(A.Itens);
  for I := 0 to High(A.Itens) do
  begin
    A.Nivel := MaiorNivel(A.Nivel, A.Itens[I].Nivel);
    case A.Itens[I].Situacao of
      siConfirmado:
        begin
          Inc(A.Identificados);
          if not A.Itens[I].CustoComparavel then
            Inc(A.SemComparacao);
          for J := 0 to High(A.Itens[I].Achados) do
            if A.Itens[I].Achados[J].Nivel >= nvAlerta then
            begin
              Inc(A.Divergencias);
              Break;
            end;
        end;
      siAusente:
        Inc(A.CadastrosPendentes);
    else
      Inc(A.SemComparacao);
    end;
  end;
  if A.FornecedorStatus = siAusente then
    Inc(A.CadastrosPendentes);

  // Regra de liberacao do XML original (documentada no LEIA-ME).
  A.PodeLiberar := True;
  A.MotivoBloqueio := '';
  if A.Nivel = nvBloqueio then
  begin
    A.PodeLiberar := False;
    A.MotivoBloqueio := 'Há falha técnica: a análise não foi concluída.';
  end
  else if A.JaLancada.Resultado = jlSim then
  begin
    A.PodeLiberar := False;
    A.MotivoBloqueio := 'A nota já consta como lançada ou com pré-entrada no WinThor.';
  end;
  Result := A;
end;

end.
