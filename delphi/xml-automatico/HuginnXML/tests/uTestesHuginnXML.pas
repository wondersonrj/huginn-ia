unit uTestesHuginnXML;

{ Testes DUnitX do motor do HUGINN XML Automatico, sem banco (provedor de
  demonstracao e notas ficticias de ..\fixtures). }

interface

uses
  DUnitX.TestFramework, System.SysUtils, uTipos, uProvedor;

type
  [TestFixture]
  TTestesValidacao = class
  public
    [Test] procedure CNPJ;
    [Test] procedure GTIN;
    [Test] procedure ChaveNFe;
  end;

  [TestFixture]
  TTestesXml = class
  public
    [Test] procedure LeNotaValida;
    [Test] procedure HashDosBytesRecebidos;
    [Test] procedure RejeitaMalformado;
    [Test] procedure RejeitaDTD;
    [Test] procedure EventoForaDoEscopo;
    [Test] procedure RejeitaChaveComDVErrado;
    [Test] procedure LeXmlsReaisLocais;
  end;

  [TestFixture]
  TTestesMotor = class
  private
    function Analisar(const Fixture: string; const Filial: string = '';
      Falhar: Boolean = False): TResultadoAnalise;
  public
    [Test] procedure ItemOkPorCodFab203ConfirmadoPorGTIN;
    [Test] procedure ItemPorCodigo253ComAlertaDeCusto;
    [Test] procedure ConflitoEntreIdentificadores;
    [Test] procedure ProdutoNovo;
    [Test] procedure ConversaoPeloFator253;
    [Test] procedure FatorDesconhecidoImpedeComparacao;
    [Test] procedure SemEntradaAnteriorECEST;
    [Test] procedure NCMDivergenteERestricao1301;
    [Test] procedure GTINInvalidoNoXML;
    [Test] procedure UsaCustoDaFilialCorreta;
    [Test] procedure FilialAmbiguaPedeEscolha;
    [Test] procedure DestinatarioDeOutraEmpresa;
    [Test] procedure FornecedorAusente;
    [Test] procedure FornecedorDuplicado;
    [Test] procedure NotaJaLancadaBloqueiaLiberacao;
    [Test] procedure FalhaDeConexaoBloqueia;
    [Test] procedure ModoSo203NaoAchaVinculo253;
    [Test] procedure NotaMistaPodeSerLiberada;
  end;

  [TestFixture]
  TTestesRegistro = class
  public
    [Test] procedure IdempotenciaEConflitoDeHash;
    [Test] procedure LiberaComMesmoSha256;
  end;

implementation

uses
  System.IOUtils, uValidacao, uXmlNFe, uMotor, uProvedorDemo, uRegistro;

function PastaFixtures: string;
var
  D: string;
  I: Integer;
begin
  D := ExtractFilePath(ParamStr(0));
  for I := 0 to 6 do
  begin
    if TFile.Exists(TPath.Combine(D, 'fixtures\nfe_valida_mista.xml')) then
      Exit(TPath.Combine(D, 'fixtures'));
    D := TPath.GetFullPath(TPath.Combine(D, '..'));
  end;
  raise Exception.Create('Pasta fixtures não encontrada a partir de ' + ExtractFilePath(ParamStr(0)));
end;

function Fx(const Nome: string): string;
begin
  Result := TPath.Combine(PastaFixtures, Nome);
end;

function LerFixture(const Nome: string): TNotaXML;
var
  B: TBytes;
begin
  Result := LerNFeArquivo(Fx(Nome), B);
end;

{ TTestesValidacao }

procedure TTestesValidacao.CNPJ;
begin
  Assert.IsTrue(CNPJValido('11.222.333/0001-81'));
  Assert.IsFalse(CNPJValido('11222333000182'));
  Assert.IsFalse(CNPJValido('11111111111111'));
end;

procedure TTestesValidacao.GTIN;
begin
  Assert.IsTrue(GTINValido('2000001001004'));
  Assert.IsTrue(GTINValido('17896419716126'));   // DUN-14
  Assert.IsFalse(GTINValido('2000001001005'));
  Assert.IsFalse(GTINInformado('SEM GTIN'));
  Assert.IsFalse(GTINValido('SEM GTIN'));
end;

procedure TTestesValidacao.ChaveNFe;
begin
  Assert.IsTrue(ChaveNFeValida('35261144555666000181550010000010011123456789'));
  Assert.IsFalse(ChaveNFeValida('35261144555666000181550010000010011123456780'));
  Assert.IsFalse(ChaveNFeValida('123'));
end;

{ TTestesXml }

procedure TTestesXml.LeNotaValida;
var
  N: TNotaXML;
begin
  N := LerFixture('nfe_valida_mista.xml');
  Assert.AreEqual('35261144555666000181550010000010011123456789', N.Chave);
  Assert.AreEqual('44555666000181', N.EmitCNPJ);
  Assert.AreEqual('11222333000181', N.DestCNPJ);
  Assert.AreEqual(9, Length(N.Itens));
  Assert.AreEqual('CX', N.Itens[4].UCom);
  Assert.AreEqual(2.0, N.Itens[4].QCom, 0.0001);
  Assert.AreEqual(248.0, N.Itens[4].VProd, 0.001);
  Assert.IsTrue(N.TemProtocolo);
end;

procedure TTestesXml.HashDosBytesRecebidos;
var
  N: TNotaXML;
begin
  N := LerFixture('nfe_valida_mista.xml');
  Assert.AreEqual('8ef108ac5c7cac94a517b8022af87e8989bc7f653e7b677f02d31a53edde3e30', N.Sha256);
end;

procedure TTestesXml.RejeitaMalformado;
begin
  Assert.WillRaise(procedure begin LerFixture('nfe_invalida.xml'); end, EXmlNFe);
end;

procedure TTestesXml.RejeitaDTD;
begin
  Assert.WillRaise(procedure begin LerFixture('nfe_com_dtd.xml'); end, EXmlNFe);
end;

procedure TTestesXml.EventoForaDoEscopo;
begin
  Assert.WillRaise(procedure begin LerFixture('evento_cancelamento.xml'); end, EForaEscopo);
end;

procedure TTestesXml.RejeitaChaveComDVErrado;
begin
  Assert.WillRaise(procedure begin LerFixture('nfe_chave_dv_invalida.xml'); end, EXmlNFe);
end;

procedure TTestesXml.LeXmlsReaisLocais;
var
  Pasta, Arq: string;
  N: TNotaXML;
  B: TBytes;
  Qtd: Integer;
begin
  // XMLs reais ficam em fixtures\real (fora do Git). Sem a pasta, o teste so registra.
  Pasta := TPath.Combine(PastaFixtures, 'real');
  Qtd := 0;
  if TDirectory.Exists(Pasta) then
    for Arq in TDirectory.GetFiles(Pasta, '*.xml') do
    begin
      N := LerNFeArquivo(Arq, B);
      Assert.AreEqual(44, Length(N.Chave), Arq);
      Assert.IsTrue(Length(N.Itens) > 0, Arq);
      Assert.AreEqual(Sha256Hex(B), N.Sha256, Arq);
      Inc(Qtd);
    end;
  System.Writeln(Format('  %d XML(s) reais lidos de %s', [Qtd, Pasta]));
end;

{ TTestesMotor }

function TTestesMotor.Analisar(const Fixture, Filial: string; Falhar: Boolean): TResultadoAnalise;
var
  Prov: IProvedorDados;
begin
  Prov := TProvedorDemo.Create(Falhar);
  Result := AnalisarNota(LerFixture(Fixture), Prov, ParametrosPadrao, Filial);
end;

procedure TTestesMotor.ItemOkPorCodFab203ConfirmadoPorGTIN;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[0];
  Assert.IsTrue(R.Situacao = siConfirmado);
  Assert.AreEqual(1001, R.Produto.CodProd);
  Assert.IsTrue(R.Produto.Origem = ovCodFab203);
  Assert.Contains(R.Evidencia, 'confirmado por');
  Assert.IsTrue(R.CustoComparavel);
  Assert.AreEqual(1.9685, R.VariacaoPct, 0.001);
  Assert.IsTrue(R.Nivel = nvOk);
end;

procedure TTestesMotor.ItemPorCodigo253ComAlertaDeCusto;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[1];
  Assert.IsTrue(R.Situacao = siConfirmado);
  Assert.AreEqual(1002, R.Produto.CodProd);
  Assert.IsTrue(R.Produto.Origem = ovCodFab253);
  Assert.AreEqual(18.3099, R.VariacaoPct, 0.001);   // 8,40 / 7,10
  Assert.IsTrue(R.Nivel = nvAlerta);
end;

procedure TTestesMotor.ConflitoEntreIdentificadores;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[2];
  // A 1301 (automatica: 203, 253...) usaria o 1004 pelo codigo 253; o EAN aponta para o 1003.
  Assert.AreEqual(1004, R.Produto.CodProd);
  Assert.IsTrue(R.Nivel = nvPendencia);
end;

procedure TTestesMotor.ProdutoNovo;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[3];
  Assert.IsTrue(R.Situacao = siAusente);
  Assert.IsTrue(R.Nivel = nvPendencia);
end;

procedure TTestesMotor.ConversaoPeloFator253;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[4];
  Assert.AreEqual(1005, R.Produto.CodProd);
  Assert.AreEqual(20.0, R.FatorAplicado, 0.0001);
  Assert.AreEqual(6.20, R.CustoXMLNormalizado, 0.0001);   // 248 / (2 x 20)
  Assert.AreEqual(3.3333, R.VariacaoPct, 0.001);
  Assert.IsTrue(R.Nivel = nvOk);
end;

procedure TTestesMotor.FatorDesconhecidoImpedeComparacao;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[5];
  Assert.AreEqual(1006, R.Produto.CodProd);
  Assert.IsFalse(R.CustoComparavel);
  Assert.AreEqual(0.0, R.FatorAplicado, 0.0001);
  Assert.IsTrue(R.Nivel = nvAlerta);
end;

procedure TTestesMotor.SemEntradaAnteriorECEST;
var
  R: TResultadoItem;
  A: TAchado;
  TemCEST: Boolean;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[6];
  Assert.AreEqual(1007, R.Produto.CodProd);
  Assert.IsFalse(R.CustoComparavel);
  TemCEST := False;
  for A in R.Achados do
    if A.Campo = 'CEST' then
      TemCEST := True;
  Assert.IsTrue(TemCEST);
end;

procedure TTestesMotor.NCMDivergenteERestricao1301;
var
  R: TResultadoItem;
  A: TAchado;
  TemNCM, TemRestricao: Boolean;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[7];
  TemNCM := False;
  TemRestricao := False;
  for A in R.Achados do
  begin
    if A.Campo = 'NCM' then
      TemNCM := True;
    if A.ValorWinThor = 'FORA_DE_LINHA' then
      TemRestricao := True;
  end;
  Assert.IsTrue(TemNCM);
  Assert.IsTrue(TemRestricao);
  Assert.IsTrue(R.Nivel = nvPendencia);
end;

procedure TTestesMotor.GTINInvalidoNoXML;
var
  R: TResultadoItem;
begin
  R := Analisar('nfe_valida_mista.xml').Itens[8];
  Assert.IsTrue(R.Situacao = siAusente);
  Assert.AreEqual('cEAN', R.Achados[0].Campo);
end;

procedure TTestesMotor.UsaCustoDaFilialCorreta;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_filial_2.xml');
  Assert.AreEqual('2', A.Filial.Codigo);
  Assert.AreEqual(30.0, A.Itens[0].Custo.PLiqUltEnt, 0.0001);   // filial 1 seria 25,40
  Assert.IsTrue(A.Itens[0].Nivel = nvAlerta);                     // -13,67%
end;

procedure TTestesMotor.FilialAmbiguaPedeEscolha;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_filial_ambigua.xml');
  Assert.IsTrue(A.FilialStatus = siAmbiguo);
  Assert.AreEqual(2, Length(A.FiliaisCandidatas));
  Assert.IsFalse(A.Itens[0].CustoComparavel);
  A := Analisar('nfe_filial_ambigua.xml', '3');
  Assert.IsTrue(A.FilialStatus = siConfirmado);
  Assert.AreEqual('3', A.Filial.Codigo);
end;

procedure TTestesMotor.DestinatarioDeOutraEmpresa;
begin
  Assert.IsTrue(Analisar('nfe_destinatario_outra_empresa.xml').FilialStatus = siAusente);
end;

procedure TTestesMotor.FornecedorAusente;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_fornecedor_ausente.xml');
  Assert.IsTrue(A.FornecedorStatus = siAusente);
  Assert.IsTrue(A.Itens[0].Situacao = siConfirmado);   // 203 nao depende do fornecedor
  Assert.IsTrue(A.Itens[1].Situacao = siAusente);      // 253 depende do fornecedor
  Assert.AreEqual(2, A.CadastrosPendentes);            // item 2 + fornecedor
end;

procedure TTestesMotor.FornecedorDuplicado;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_fornecedor_duplicado.xml');
  Assert.IsTrue(A.FornecedorStatus = siPossivelDuplicidade);
  Assert.AreEqual(2, Length(A.Fornecedores));
end;

procedure TTestesMotor.NotaJaLancadaBloqueiaLiberacao;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_ja_lancada.xml');
  Assert.IsTrue(A.JaLancada.Resultado = jlSim);
  Assert.IsFalse(A.PodeLiberar);
end;

procedure TTestesMotor.FalhaDeConexaoBloqueia;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_valida_mista.xml', '', True);
  Assert.IsTrue(A.Nivel = nvBloqueio);
  Assert.IsFalse(A.PodeLiberar);
  Assert.IsTrue(A.FornecedorStatus = siIndisponivel);
end;

procedure TTestesMotor.ModoSo203NaoAchaVinculo253;
var
  P: TParametrosMotor;
  Prov: IProvedorDados;
  R: TResultadoItem;
begin
  P := ParametrosPadrao;
  P.ModoPesquisa := mpCodFab203;
  Prov := TProvedorDemo.Create;
  R := AnalisarNota(LerFixture('nfe_valida_mista.xml'), Prov, P).Itens[1];
  Assert.IsTrue(R.Situacao = siAusente);
  Assert.IsTrue(R.Nivel = nvPendencia);
  Assert.Contains(R.Evidencia, '1002');
end;

procedure TTestesMotor.NotaMistaPodeSerLiberada;
var
  A: TResultadoAnalise;
begin
  A := Analisar('nfe_valida_mista.xml');
  Assert.IsTrue(A.PodeLiberar);
  Assert.AreEqual(9, A.TotalItens);
  Assert.AreEqual(7, A.Identificados);
  Assert.AreEqual(2, A.CadastrosPendentes);
end;

{ TTestesRegistro }

procedure TTestesRegistro.IdempotenciaEConflitoDeHash;
var
  Base: string;
  B1, B2: TBytes;
  N1, N2: TNotaXML;
begin
  Base := TPath.Combine(TPath.GetTempPath, 'huginn_xml_teste_' + IntToStr(Random(MaxInt)));
  N1 := LerNFeArquivo(Fx('nfe_valida_mista.xml'), B1);
  N2 := LerNFeArquivo(Fx('nfe_mesma_chave_bytes_diferentes.xml'), B2);
  Assert.AreEqual(N1.Chave, N2.Chave);
  Assert.AreNotEqual(N1.Sha256, N2.Sha256);
  Assert.IsTrue(RegistrarRecebido(Base, N1.Chave, N1.Sha256, B1).Status = rgNovo);
  Assert.IsTrue(RegistrarRecebido(Base, N1.Chave, N1.Sha256, B1).Status = rgMesmoArquivo);
  Assert.IsTrue(RegistrarRecebido(Base, N2.Chave, N2.Sha256, B2).Status = rgConflito);
  TDirectory.Delete(Base, True);
end;

procedure TTestesRegistro.LiberaComMesmoSha256;
var
  Base, Arq: string;
  B: TBytes;
  N: TNotaXML;
begin
  Base := TPath.Combine(TPath.GetTempPath, 'huginn_xml_lib_' + IntToStr(Random(MaxInt)));
  N := LerNFeArquivo(Fx('nfe_valida_mista.xml'), B);
  Arq := LiberarOriginal(Base, N.Chave, N.Sha256, B);
  Assert.AreEqual(N.Sha256, Sha256Hex(TFile.ReadAllBytes(Arq)));
  Assert.AreEqual(Arq, LiberarOriginal(Base, N.Chave, N.Sha256, B));   // idempotente
  TDirectory.Delete(Base, True);
end;

initialization
  Randomize;
  TDUnitX.RegisterTestFixture(TTestesValidacao);
  TDUnitX.RegisterTestFixture(TTestesXml);
  TDUnitX.RegisterTestFixture(TTestesMotor);
  TDUnitX.RegisterTestFixture(TTestesRegistro);

end.
