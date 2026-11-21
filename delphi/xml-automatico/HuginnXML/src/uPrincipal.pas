unit uPrincipal;

{ HUGINN XML Automatico - tela principal (montada em codigo, sem .dfm).
  Estilo HUGINN: azul-marinho, azul eletrico e ciano.

  Fluxo: Abrir XML -> Analisar -> revisar itens -> Liberar XML original para a 1301.
  Nada aqui grava no WinThor. }

interface

uses
  Winapi.Windows, System.SysUtils, System.Classes, System.UITypes,
  Vcl.Forms, Vcl.Controls, Vcl.StdCtrls, Vcl.ExtCtrls, Vcl.ComCtrls, Vcl.Graphics,
  Vcl.Dialogs,
  uTipos, uConfig, uProvedor, uRegistro, uMotor;

type
  TFrmPrincipal = class(TForm)
  private
    FCfg: TXmlConfig;
    FProv: IProvedorDados;
    FBytes: TBytes;
    FNota: TNotaXML;
    FTemNota: Boolean;
    FAnalise: TResultadoAnalise;
    FTemAnalise: Boolean;
    FFilialEscolhida: string;
    FRecebido: TResultadoRecebido;
    // controles
    Paginas: TPageControl;
    tabConf, tabHist: TTabSheet;
    btnAbrir, btnAnalisar, btnLiberar, btnConfig, btnHist: TButton;
    cmbModo: TComboBox;
    chkPendencias: TCheckBox;
    lblFonte, lblChave, lblNota, lblEmit, lblDest, lblFilial, lblStatus, lblResumo: TLabel;
    mmoNota, mmoDetalhe: TMemo;
    lvItens, lvHist: TListView;
    Rodape: TStatusBar;
    procedure MontarTela;
    function NovoLabel(AParent: TWinControl; const ATexto: string; AX, AY: Integer;
      ACor: TColor; ATam: Integer = 9; ABold: Boolean = False): TLabel;
    function NovoBotao(AParent: TWinControl; const ATexto: string; AX, AW: Integer;
      AClick: TNotifyEvent): TButton;
    function NovaLista(AParent: TWinControl): TListView;
    procedure Coluna(LV: TListView; const Titulo: string; Largura: Integer);
    procedure Status(const S: string);
    procedure Log(const Acao, Resultado, Detalhe: string);
    function Provedor: IProvedorDados;
    function Parametros: TParametrosMotor;
    procedure Analisar(Reanalise: Boolean);
    function EscolherFilial: Boolean;
    procedure MostrarCabecalho;
    procedure MostrarAnalise;
    procedure MostrarDetalhe(Indice: Integer);
    procedure CarregarHistorico;
    procedure BtnAbrirClick(Sender: TObject);
    procedure BtnAnalisarClick(Sender: TObject);
    procedure BtnLiberarClick(Sender: TObject);
    procedure BtnConfigClick(Sender: TObject);
    procedure BtnHistClick(Sender: TObject);
    procedure PaginasChange(Sender: TObject);
    procedure FiltroClick(Sender: TObject);
    procedure ModoChange(Sender: TObject);
    procedure LvItensSelect(Sender: TObject; Item: TListItem; Selected: Boolean);
    procedure LvItensDraw(Sender: TCustomListView; Item: TListItem;
      State: TCustomDrawState; var DefaultDraw: Boolean);
  public
    constructor Create(AOwner: TComponent); override;
  end;

var
  FrmPrincipal: TFrmPrincipal;

implementation

uses
  Winapi.ShellAPI, System.Math, System.StrUtils, Uni,
  uXmlNFe, uProvedorDemo, uProvedorOracle, uConexao, uLog, uFrmConexao;

const
  COR_FUNDO    = TColor($0026140B); // #0B1426 azul-marinho
  COR_PAINEL   = TColor($00100904); // #040910 quase preto
  COR_CAMPO    = TColor($00402A1A); // #1A2A40
  COR_TEXTO    = TColor($00F7EDE6); // #E6EDF7
  COR_SUAVE    = TColor($00B09A8A); // #8A9AB0
  COR_ELETRICO = TColor($00FF901E); // #1E90FF
  COR_CIANO    = TColor($00FFE500); // #00E5FF
  COR_OK       = TColor($0071CC2E); // #2ECC71
  COR_ALERTA   = TColor($000FC4F1); // #F1C40F
  COR_PEND     = TColor($00227EE6); // #E67E22
  COR_FALHA    = TColor($003C4CE7); // #E74C3C

{ TFrmPrincipal }

constructor TFrmPrincipal.Create(AOwner: TComponent);
begin
  inherited CreateNew(AOwner);
  FCfg := CarregarConfig;
  MontarTela;
  Status('Pronto. Abra um XML de NF-e. Fonte de dados: ' + IfThen(FCfg.UsarOracle,
    'Oracle WinThor (somente leitura)', 'DEMONSTRAÇÃO (dados fictícios)') + '.');
end;

function TFrmPrincipal.NovoLabel(AParent: TWinControl; const ATexto: string;
  AX, AY: Integer; ACor: TColor; ATam: Integer; ABold: Boolean): TLabel;
begin
  Result := TLabel.Create(Self);
  Result.Parent := AParent;
  Result.Left := AX;
  Result.Top := AY;
  Result.Caption := ATexto;
  Result.Transparent := True;
  Result.ParentFont := False;
  Result.Font.Name := 'Segoe UI';
  Result.Font.Size := ATam;
  Result.Font.Color := ACor;
  if ABold then
    Result.Font.Style := [fsBold];
end;

function TFrmPrincipal.NovoBotao(AParent: TWinControl; const ATexto: string;
  AX, AW: Integer; AClick: TNotifyEvent): TButton;
begin
  Result := TButton.Create(Self);
  Result.Parent := AParent;
  Result.SetBounds(AX, 8, AW, 32);
  Result.Caption := ATexto;
  Result.OnClick := AClick;
end;

function TFrmPrincipal.NovaLista(AParent: TWinControl): TListView;
begin
  Result := TListView.Create(Self);
  Result.Parent := AParent;
  Result.ViewStyle := vsReport;
  Result.ReadOnly := True;
  Result.RowSelect := True;
  Result.HideSelection := False;
  Result.GridLines := True;
  Result.Color := COR_CAMPO;
  Result.Font.Color := COR_TEXTO;
  Result.Font.Name := 'Segoe UI';
end;

procedure TFrmPrincipal.Coluna(LV: TListView; const Titulo: string; Largura: Integer);
var
  C: TListColumn;
begin
  C := LV.Columns.Add;
  C.Caption := Titulo;
  C.Width := Largura;
end;

procedure TFrmPrincipal.MontarTela;
var
  Topo, Barra, Cab, Base: TPanel;
  Faixa: TShape;
  Div1: TSplitter;
  M: TModoPesquisa;
begin
  Caption := 'HUGINN XML Automático v' + VERSAO_APP + ' — conferência de NF-e de entrada (somente leitura)';
  Width := 1280;
  Height := 820;
  Position := poScreenCenter;
  Color := COR_FUNDO;
  Font.Name := 'Segoe UI';
  Font.Size := 9;
  Font.Color := COR_TEXTO;
  Constraints.MinWidth := 1000;
  Constraints.MinHeight := 640;

  Topo := TPanel.Create(Self);
  Topo.Parent := Self;
  Topo.Align := alTop;
  Topo.Height := 64;
  Topo.BevelOuter := bvNone;
  Topo.ParentBackground := False;
  Topo.Color := COR_PAINEL;
  NovoLabel(Topo, 'HUGINN', 20, 8, COR_CIANO, 20, True);
  NovoLabel(Topo, 'XML Automático · conferência antes da importação na 1301', 146, 12, COR_TEXTO, 11);
  NovoLabel(Topo, 'Seu ERP registra. HUGINN antecipa.   Nada é gravado no WinThor.', 146, 36, COR_SUAVE, 9);

  Faixa := TShape.Create(Self);
  Faixa.Parent := Self;
  Faixa.Align := alTop;
  Faixa.Top := 70;
  Faixa.Height := 3;
  Faixa.Pen.Style := psClear;
  Faixa.Brush.Color := COR_ELETRICO;

  Barra := TPanel.Create(Self);
  Barra.Parent := Self;
  Barra.Align := alTop;
  Barra.Top := 80;
  Barra.Height := 48;
  Barra.BevelOuter := bvNone;
  Barra.ParentBackground := False;
  Barra.Color := COR_FUNDO;
  btnAbrir := NovoBotao(Barra, 'Abrir XML…', 16, 120, BtnAbrirClick);
  btnAnalisar := NovoBotao(Barra, 'Analisar', 144, 110, BtnAnalisarClick);
  btnLiberar := NovoBotao(Barra, 'Liberar XML original', 262, 170, BtnLiberarClick);
  btnConfig := NovoBotao(Barra, 'Configuração…', 440, 120, BtnConfigClick);
  btnAnalisar.Enabled := False;
  btnLiberar.Enabled := False;
  NovoLabel(Barra, 'Pesquisa (igual à 1301):', 580, 16, COR_SUAVE);
  cmbModo := TComboBox.Create(Self);
  cmbModo.Parent := Barra;
  cmbModo.Style := csDropDownList;
  cmbModo.SetBounds(724, 12, 250, 24);
  for M := Low(TModoPesquisa) to High(TModoPesquisa) do
    cmbModo.Items.Add(ModoPesquisaTexto(M));
  cmbModo.ItemIndex := Ord(FCfg.ModoPesquisa);
  cmbModo.OnChange := ModoChange;
  chkPendencias := TCheckBox.Create(Self);
  chkPendencias.Parent := Barra;
  chkPendencias.SetBounds(992, 16, 17, 17);
  chkPendencias.OnClick := FiltroClick;
  NovoLabel(Barra, 'Só itens com pendência/alerta', 1012, 15, COR_TEXTO);

  Rodape := TStatusBar.Create(Self);
  Rodape.Parent := Self;
  Rodape.SimplePanel := True;

  Paginas := TPageControl.Create(Self);
  Paginas.Parent := Self;
  Paginas.Align := alClient;
  tabConf := TTabSheet.Create(Self);
  tabConf.PageControl := Paginas;
  tabConf.Caption := 'Conferência';
  tabHist := TTabSheet.Create(Self);
  tabHist.PageControl := Paginas;
  tabHist.Caption := 'Histórico (log de operações)';
  Paginas.OnChange := PaginasChange;

  // ---- Conferencia: cabecalho ----
  Cab := TPanel.Create(Self);
  Cab.Parent := tabConf;
  Cab.Align := alTop;
  Cab.Height := 150;
  Cab.BevelOuter := bvNone;
  Cab.ParentBackground := False;
  Cab.Color := COR_FUNDO;
  lblFonte := NovoLabel(Cab, '', 12, 6, COR_CIANO, 9, True);
  lblChave := NovoLabel(Cab, 'Chave: —', 12, 26, COR_TEXTO, 10, True);
  lblNota := NovoLabel(Cab, 'Número/série: —', 12, 48, COR_TEXTO);
  lblEmit := NovoLabel(Cab, 'Emitente: —', 12, 68, COR_TEXTO);
  lblDest := NovoLabel(Cab, 'Destinatário: —', 12, 88, COR_TEXTO);
  lblFilial := NovoLabel(Cab, 'Filial: —', 12, 108, COR_TEXTO);
  lblStatus := NovoLabel(Cab, '', 12, 128, COR_SUAVE, 10, True);
  lblResumo := NovoLabel(Cab, '', 620, 26, COR_TEXTO, 10);
  mmoNota := TMemo.Create(Self);
  mmoNota.Parent := Cab;
  mmoNota.SetBounds(620, 50, 600, 94);
  mmoNota.Anchors := [akLeft, akTop, akRight];
  mmoNota.ReadOnly := True;
  mmoNota.ScrollBars := ssVertical;
  mmoNota.Color := COR_CAMPO;
  mmoNota.Font.Color := COR_TEXTO;

  // ---- Conferencia: detalhe (embaixo) ----
  Base := TPanel.Create(Self);
  Base.Parent := tabConf;
  Base.Align := alBottom;
  Base.Height := 220;
  Base.BevelOuter := bvNone;
  mmoDetalhe := TMemo.Create(Self);
  mmoDetalhe.Parent := Base;
  mmoDetalhe.Align := alClient;
  mmoDetalhe.ReadOnly := True;
  mmoDetalhe.ScrollBars := ssVertical;
  mmoDetalhe.Color := COR_CAMPO;
  mmoDetalhe.Font.Color := COR_TEXTO;
  mmoDetalhe.Font.Name := 'Consolas';
  mmoDetalhe.Lines.Text := 'Selecione um item para ver a evidência, o cálculo e a orientação.';

  Div1 := TSplitter.Create(Self);
  Div1.Parent := tabConf;
  Div1.Align := alBottom;
  Div1.Height := 5;

  // ---- Conferencia: grade ----
  lvItens := NovaLista(tabConf);
  lvItens.Align := alClient;
  Coluna(lvItens, 'Item', 45);
  Coluna(lvItens, 'Descrição no XML', 250);
  Coluna(lvItens, 'Produto WinThor', 250);
  Coluna(lvItens, 'Vínculo', 150);
  Coluna(lvItens, 'Qtd / Un', 100);
  Coluna(lvItens, 'Custo XML (un. WinThor)', 140);
  Coluna(lvItens, 'Última entrada', 105);
  Coluna(lvItens, 'Dif. %', 70);
  Coluna(lvItens, 'Status', 140);
  lvItens.OnSelectItem := LvItensSelect;
  lvItens.OnCustomDrawItem := LvItensDraw;

  // ---- Historico ----
  Barra := TPanel.Create(Self);
  Barra.Parent := tabHist;
  Barra.Align := alTop;
  Barra.Height := 48;
  Barra.BevelOuter := bvNone;
  btnHist := NovoBotao(Barra, 'Atualizar', 8, 110, BtnHistClick);
  lvHist := NovaLista(tabHist);
  lvHist.Align := alClient;
  Coluna(lvHist, 'Data/hora', 170);
  Coluna(lvHist, 'Ação', 110);
  Coluna(lvHist, 'Usuário', 110);
  Coluna(lvHist, 'Máquina', 120);
  Coluna(lvHist, 'Chave', 330);
  Coluna(lvHist, 'Filial', 50);
  Coluna(lvHist, 'Resultado', 160);
  Coluna(lvHist, 'Detalhe', 400);
end;

procedure TFrmPrincipal.Status(const S: string);
begin
  Rodape.SimpleText := '  ' + S;
end;

procedure TFrmPrincipal.Log(const Acao, Resultado, Detalhe: string);
begin
  try
    RegistrarOperacao(FCfg.PastaBase, Acao, FNota.Chave, FNota.Sha256,
      IfThen(FTemAnalise, FAnalise.Filial.Codigo, ''), Resultado, Detalhe);
  except
    on E: Exception do
      Status(E.Message);
  end;
end;

function TFrmPrincipal.Provedor: IProvedorDados;
var
  Con: TUniConnection;
  Senha: string;
begin
  if FProv <> nil then
    Exit(FProv);
  if not FCfg.UsarOracle then
    FProv := TProvedorDemo.Create
  else
  begin
    if FCfg.Senha = '' then
    begin
      Senha := '';
      // #31 no inicio do prompt = campo de senha (InputQuery da VCL).
      if not InputQuery('HUGINN — Oracle', #31'Senha do usuário ' + FCfg.Usuario + ':', Senha) then
        Abort;
      FCfg.Senha := Senha;
    end;
    Con := CriarConexao(FCfg);
    try
      Con.Connect;
    except
      Con.Free;
      FCfg.Senha := '';
      raise;
    end;
    FProv := TProvedorOracle.Create(Con, FCfg.Owner, True);
  end;
  Result := FProv;
end;

function TFrmPrincipal.Parametros: TParametrosMotor;
begin
  Result := ParametrosPadrao;
  Result.ModoPesquisa := TModoPesquisa(Max(0, cmbModo.ItemIndex));
  Result.UsarFator253 := FCfg.UsarFator253;
  Result.ToleranciaCustoPct := FCfg.ToleranciaCustoPct;
end;

procedure TFrmPrincipal.BtnAbrirClick(Sender: TObject);
var
  Dlg: TOpenDialog;
  Arq: string;
begin
  Dlg := TOpenDialog.Create(Self);
  try
    Dlg.Title := 'Selecione o XML da NF-e';
    Dlg.Filter := 'XML da NF-e (*.xml)|*.xml|Todos os arquivos (*.*)|*.*';
    Dlg.Options := [ofFileMustExist, ofPathMustExist];
    if not Dlg.Execute then
      Exit;
    Arq := Dlg.FileName;
  finally
    Dlg.Free;
  end;

  FTemNota := False;
  FTemAnalise := False;
  FFilialEscolhida := '';
  btnAnalisar.Enabled := False;
  btnLiberar.Enabled := False;
  lvItens.Items.Clear;
  mmoNota.Clear;
  try
    FNota := LerNFeArquivo(Arq, FBytes);
  except
    on E: Exception do
    begin
      FNota := Default(TNotaXML);
      Log('erro_leitura', 'XML rejeitado', E.ClassName + ': ' + E.Message);
      MostrarCabecalho;
      lblStatus.Font.Color := COR_FALHA;
      lblStatus.Caption := 'XML NÃO ACEITO: ' + E.Message;
      Status('Escolha outro arquivo.');
      Exit;
    end;
  end;
  FTemNota := True;
  try
    FRecebido := RegistrarRecebido(FCfg.PastaBase, FNota.Chave, FNota.Sha256, FBytes);
  except
    on E: Exception do
    begin
      FRecebido := Default(TResultadoRecebido);
      Status('Aviso: não foi possível guardar a cópia recebida: ' + E.Message);
    end;
  end;
  Log('abrir', IfThen(FRecebido.Status = rgConflito, 'CONFLITO de hash', 'ok'),
    ExtractFileName(Arq) + ' (' + IntToStr(FNota.TamanhoBytes) + ' bytes)');
  MostrarCabecalho;
  btnAnalisar.Enabled := True;
  Analisar(False);
end;

function TFrmPrincipal.EscolherFilial: Boolean;
var
  F: TForm;
  L: TListBox;
  B: TButton;
  X: TFilial;
begin
  Result := False;
  F := TForm.CreateNew(Self);
  try
    F.Caption := 'Filial ambígua — escolha a filial desta nota';
    F.BorderStyle := bsDialog;
    F.Position := poMainFormCenter;
    F.ClientWidth := 520;
    F.ClientHeight := 260;
    L := TListBox.Create(F);
    L.Parent := F;
    L.SetBounds(12, 12, 496, 190);
    for X in FAnalise.FiliaisCandidatas do
      L.Items.Add(X.Codigo + ' - ' + X.Nome + ' (CNPJ ' + X.CNPJ + ')');
    if L.Items.Count > 0 then
      L.ItemIndex := 0;
    B := TButton.Create(F);
    B.Parent := F;
    B.SetBounds(296, 214, 100, 30);
    B.Caption := 'Confirmar';
    B.ModalResult := mrOk;
    B.Default := True;
    B := TButton.Create(F);
    B.Parent := F;
    B.SetBounds(408, 214, 100, 30);
    B.Caption := 'Agora não';
    B.ModalResult := mrCancel;
    if (F.ShowModal = mrOk) and (L.ItemIndex >= 0) then
    begin
      FFilialEscolhida := FAnalise.FiliaisCandidatas[L.ItemIndex].Codigo;
      Log('escolher_filial', FFilialEscolhida, 'Filial escolhida pelo operador');
      Result := True;
    end;
  finally
    F.Free;
  end;
end;

procedure TFrmPrincipal.Analisar(Reanalise: Boolean);
var
  OutroHash: string;
begin
  if not FTemNota then
    Exit;
  Screen.Cursor := crHourGlass;
  try
    try
      FAnalise := AnalisarNota(FNota, Provedor, Parametros, FFilialEscolhida);
      FTemAnalise := True;
    except
      on E: EAbort do
        Exit;
      on E: Exception do
      begin
        FProv := nil;  // forca reconectar na proxima tentativa
        Log('erro_analise', 'falha técnica', E.Message);
        Screen.Cursor := crDefault;
        MessageDlg('Não foi possível analisar: ' + E.Message, mtError, [mbOK], 0);
        Exit;
      end;
    end;
  finally
    Screen.Cursor := crDefault;
  end;

  if (FAnalise.FilialStatus = siAmbiguo) and (FFilialEscolhida = '') and EscolherFilial then
  begin
    Analisar(True);
    Exit;
  end;

  // Mesma chave recebida antes com bytes diferentes: evidencia guardada e liberacao bloqueada.
  if FRecebido.Status = rgConflito then
  begin
    OutroHash := String.Join(', ', FRecebido.OutrosHashes);
    AdicionarAchado(FAnalise.AchadosNota, NovoAchado(nvPendencia, 'XML', FNota.Sha256, OutroHash,
      'Recebidos', 'Esta chave já foi recebida com conteúdo DIFERENTE (outro SHA-256).',
      'Compare as versões na pasta Recebidos e confirme com o fornecedor qual é a autorizada.'));
    FAnalise.Nivel := MaiorNivel(FAnalise.Nivel, nvPendencia);
    FAnalise.PodeLiberar := False;
    FAnalise.MotivoBloqueio := 'Mesma chave recebida com conteúdo diferente: revisar antes de liberar.';
  end;

  Log(IfThen(Reanalise, 'reanalisar', 'analisar'), NivelTexto(FAnalise.Nivel),
    Format('provedor=%s; modo=%s; itens=%d; identificados=%d; divergencias=%d; pendentes=%d; sem_comparacao=%d; libera=%s',
      [FAnalise.Provedor, ModoPesquisaTexto(FAnalise.ModoPesquisa), FAnalise.TotalItens,
       FAnalise.Identificados, FAnalise.Divergencias, FAnalise.CadastrosPendentes,
       FAnalise.SemComparacao, BoolToStr(FAnalise.PodeLiberar, True)]));
  btnAnalisar.Caption := 'Reanalisar';
  MostrarAnalise;
end;

procedure TFrmPrincipal.MostrarCabecalho;
begin
  if FTemNota then
  begin
    lblChave.Caption := 'Chave: ' + FNota.Chave + IfThen(FNota.TemProtocolo,
      '   Protocolo ' + FNota.Protocolo + ' (cStat ' + FNota.CStatProt + ')', '   SEM protocolo');
    lblNota.Caption := Format('Número/série: %s / %s    Emissão: %s    Valor: R$ %s    Itens: %d',
      [FNota.Numero, FNota.Serie, Copy(FNota.DataEmissao, 1, 10), FmtNum(FNota.VNF), Length(FNota.Itens)]);
    lblEmit.Caption := 'Emitente: ' + FNota.EmitCNPJ + ' - ' + FNota.EmitNome + ' (' + FNota.EmitUF + ')';
    lblDest.Caption := 'Destinatário: ' + FNota.DestCNPJ + ' - ' + FNota.DestNome;
  end
  else
  begin
    lblChave.Caption := 'Chave: —';
    lblNota.Caption := 'Número/série: —';
    lblEmit.Caption := 'Emitente: —';
    lblDest.Caption := 'Destinatário: —';
  end;
  lblFilial.Caption := 'Filial: —';
  lblResumo.Caption := '';
  lblStatus.Caption := '';
  lblFonte.Caption := 'Fonte: ' + IfThen(FCfg.UsarOracle, 'Oracle WinThor (somente leitura)',
    'DEMONSTRAÇÃO — dados fictícios, sem banco');
end;

function CorNivel(N: TNivel): TColor;
begin
  case N of
    nvOk:        Result := COR_OK;
    nvAlerta:    Result := COR_ALERTA;
    nvPendencia: Result := COR_PEND;
  else
    Result := COR_FALHA;
  end;
end;

procedure TFrmPrincipal.MostrarAnalise;
var
  I: Integer;
  R: TResultadoItem;
  LI: TListItem;
  A: TAchado;
  F: TFornecedor;
  Forn: string;
begin
  MostrarCabecalho;
  Forn := '';
  for F in FAnalise.Fornecedores do
    Forn := Forn + IfThen(Forn <> '', ', ', '') + IntToStr(F.Codigo);
  lblEmit.Caption := lblEmit.Caption + '   → fornecedor WinThor: ' +
    IfThen(Forn <> '', Forn, SituacaoTexto(FAnalise.FornecedorStatus));
  lblFilial.Caption := 'Filial: ' + IfThen(FAnalise.FilialStatus = siConfirmado,
    FAnalise.Filial.Codigo + ' - ' + FAnalise.Filial.Nome, SituacaoTexto(FAnalise.FilialStatus));
  lblResumo.Caption := Format('Itens: %d   Identificados: %d   Divergências: %d   Cadastros pendentes: %d   Sem comparação: %d',
    [FAnalise.TotalItens, FAnalise.Identificados, FAnalise.Divergencias,
     FAnalise.CadastrosPendentes, FAnalise.SemComparacao]);
  lblStatus.Font.Color := CorNivel(FAnalise.Nivel);
  if FAnalise.PodeLiberar then
    lblStatus.Caption := 'Resultado: ' + NivelTexto(FAnalise.Nivel) + ' — pode liberar o XML original' +
      IfThen(FAnalise.Nivel >= nvAlerta, ' (após revisar os avisos)', '')
  else
    lblStatus.Caption := 'Resultado: ' + NivelTexto(FAnalise.Nivel) + ' — LIBERAÇÃO BLOQUEADA: ' + FAnalise.MotivoBloqueio;

  mmoNota.Lines.BeginUpdate;
  try
    mmoNota.Clear;
    if Length(FAnalise.AchadosNota) = 0 then
      mmoNota.Lines.Add('Sem observações na nota.');
    for A in FAnalise.AchadosNota do
      mmoNota.Lines.Add(Format('[%s] %s: %s → %s', [NivelTexto(A.Nivel), A.Campo, A.Mensagem, A.Acao]));
  finally
    mmoNota.Lines.EndUpdate;
  end;

  lvItens.Items.BeginUpdate;
  try
    lvItens.Items.Clear;
    for I := 0 to High(FAnalise.Itens) do
    begin
      R := FAnalise.Itens[I];
      if chkPendencias.Checked and (R.Nivel = nvOk) then
        Continue;
      LI := lvItens.Items.Add;
      LI.Caption := IntToStr(R.Item.NItem);
      LI.Data := Pointer(NativeInt(I));
      LI.SubItems.Add(R.Item.XProd);
      if R.Situacao = siConfirmado then
      begin
        LI.SubItems.Add(IntToStr(R.Produto.CodProd) + ' - ' + R.Produto.Descricao);
        LI.SubItems.Add(OrigemTexto(R.Produto.Origem));
      end
      else
      begin
        LI.SubItems.Add('(' + SituacaoTexto(R.Situacao) + ')');
        LI.SubItems.Add('—');
      end;
      LI.SubItems.Add(FmtNum(R.Item.QCom, 3) + ' ' + R.Item.UCom);
      LI.SubItems.Add(IfThen(R.CustoXMLNormalizado > 0, FmtNum(R.CustoXMLNormalizado, 4), '—'));
      LI.SubItems.Add(IfThen(R.TemCustoReferencia and (R.Custo.PLiqUltEnt > 0), FmtNum(R.Custo.PLiqUltEnt, 4), '—'));
      LI.SubItems.Add(IfThen(R.CustoComparavel, FmtNum(R.VariacaoPct, 2) + '%', '—'));
      LI.SubItems.Add(NivelTexto(R.Nivel) + IfThen(R.Situacao <> siConfirmado, ' · ' + SituacaoTexto(R.Situacao), ''));
    end;
  finally
    lvItens.Items.EndUpdate;
  end;
  mmoDetalhe.Lines.Text := 'Selecione um item para ver a evidência, o cálculo e a orientação.';
  btnLiberar.Enabled := FAnalise.PodeLiberar;
  Status(Format('Análise concluída em %s (%s). Regra %s.',
    [FormatDateTime('dd/mm/yyyy hh:nn:ss', FAnalise.DataHora), FAnalise.Provedor, VERSAO_REGRA]));
end;

procedure TFrmPrincipal.MostrarDetalhe(Indice: Integer);
var
  R: TResultadoItem;
  A: TAchado;
  L: TStrings;
begin
  if (Indice < 0) or (Indice > High(FAnalise.Itens)) then
    Exit;
  R := FAnalise.Itens[Indice];
  L := mmoDetalhe.Lines;
  L.BeginUpdate;
  try
    L.Clear;
    L.Add(Format('ITEM %d — %s', [R.Item.NItem, R.Item.XProd]));
    L.Add(Format('  XML: cProd %s | cEAN %s | cEANTrib %s | NCM %s | CEST %s | CFOP %s',
      [R.Item.CProd, R.Item.CEAN, R.Item.CEANTrib, R.Item.NCM, R.Item.CEST, R.Item.CFOP]));
    L.Add(Format('       %s %s x %s = %s | desc %s | ICMS %s | ST %s | IPI %s',
      [FmtNum(R.Item.QCom, 4), R.Item.UCom, FmtNum(R.Item.VUnCom, 4), FmtNum(R.Item.VProd),
       FmtNum(R.Item.VDesc), FmtNum(R.Item.VICMS), FmtNum(R.Item.VICMSST), FmtNum(R.Item.VIPI)]));
    L.Add('');
    L.Add('IDENTIFICAÇÃO: ' + SituacaoTexto(R.Situacao));
    if R.Evidencia <> '' then
      L.Add('  Evidência: ' + R.Evidencia);
    if R.Situacao = siConfirmado then
      L.Add(Format('  WinThor: %d - %s | unidade %s | embalagem %s | NCM %s | QTUNITCX %s',
        [R.Produto.CodProd, R.Produto.Descricao, R.Produto.Unidade, R.Produto.Embalagem,
         R.Produto.NCM, FmtNum(R.Produto.QtUnitCx, 0)]));
    if R.MemoriaCalculo <> '' then
    begin
      L.Add('');
      L.Add('CUSTO:');
      L.Add('  ' + StringReplace(R.MemoriaCalculo, sLineBreak, sLineBreak + '  ', [rfReplaceAll]));
    end;
    L.Add('');
    if Length(R.Achados) = 0 then
      L.Add('Sem divergências.')
    else
      for A in R.Achados do
      begin
        L.Add(Format('[%s] %s — %s', [NivelTexto(A.Nivel), A.Campo, A.Mensagem]));
        if (A.ValorXML <> '') or (A.ValorWinThor <> '') then
          L.Add(Format('     XML: %s | WinThor: %s | origem: %s', [A.ValorXML, A.ValorWinThor, A.Origem]));
        L.Add('     Ação: ' + A.Acao);
      end;
  finally
    L.EndUpdate;
  end;
end;

procedure TFrmPrincipal.LvItensSelect(Sender: TObject; Item: TListItem; Selected: Boolean);
begin
  if Selected and (Item <> nil) then
    MostrarDetalhe(Integer(NativeInt(Item.Data)));
end;

procedure TFrmPrincipal.LvItensDraw(Sender: TCustomListView; Item: TListItem;
  State: TCustomDrawState; var DefaultDraw: Boolean);
var
  I: Integer;
begin
  I := Integer(NativeInt(Item.Data));
  if FTemAnalise and (I >= 0) and (I <= High(FAnalise.Itens)) then
    Sender.Canvas.Font.Color := CorNivel(FAnalise.Itens[I].Nivel);
  DefaultDraw := True;
end;

procedure TFrmPrincipal.FiltroClick(Sender: TObject);
begin
  if FTemAnalise then
    MostrarAnalise;
end;

procedure TFrmPrincipal.ModoChange(Sender: TObject);
begin
  FCfg.ModoPesquisa := TModoPesquisa(Max(0, cmbModo.ItemIndex));
  try
    SalvarConfig(FCfg);
  except
    // configuracao em pasta sem escrita: segue com o valor em memoria
  end;
  if FTemNota then
    Analisar(True);
end;

procedure TFrmPrincipal.BtnAnalisarClick(Sender: TObject);
begin
  Analisar(FTemAnalise);
end;

procedure TFrmPrincipal.BtnLiberarClick(Sender: TObject);
var
  Msg, Destino: string;
begin
  if not (FTemNota and FTemAnalise) then
    Exit;
  if not FAnalise.PodeLiberar then
  begin
    MessageDlg('Liberação bloqueada: ' + FAnalise.MotivoBloqueio, mtWarning, [mbOK], 0);
    Exit;
  end;
  Msg := Format('Liberar o XML ORIGINAL (SHA-256 %s…) para importação na 1301?' + sLineBreak + sLineBreak +
    'Itens: %d | identificados: %d | divergências: %d | cadastros pendentes: %d | sem comparação: %d' + sLineBreak +
    'Resultado: %s' + sLineBreak + sLineBreak +
    'A 1301 fará a validação final e a pré-entrada. Pendências de cadastro devem ser resolvidas nas rotinas nativas.',
    [Copy(FNota.Sha256, 1, 16), FAnalise.TotalItens, FAnalise.Identificados, FAnalise.Divergencias,
     FAnalise.CadastrosPendentes, FAnalise.SemComparacao, NivelTexto(FAnalise.Nivel)]);
  if FAnalise.Nivel >= nvAlerta then
    Msg := Msg + sLineBreak + sLineBreak + 'ATENÇÃO: há alertas/pendências. Confirme que você os revisou.';
  if MessageDlg(Msg, mtConfirmation, [mbYes, mbNo], 0) <> mrYes then
  begin
    Log('liberar_cancelado', NivelTexto(FAnalise.Nivel), 'Operador não confirmou');
    Exit;
  end;
  try
    Destino := LiberarOriginal(FCfg.PastaLiberados, FNota.Chave, FNota.Sha256, FBytes);
  except
    on E: Exception do
    begin
      Log('erro_liberar', 'falha', E.Message);
      MessageDlg(E.Message, mtError, [mbOK], 0);
      Exit;
    end;
  end;
  Log('liberar', NivelTexto(FAnalise.Nivel), 'Operador confirmou após revisão; arquivo=' + Destino);
  Status('XML original liberado (mesmo SHA-256): ' + Destino);
  if MessageDlg('XML liberado em:' + sLineBreak + Destino + sLineBreak + sLineBreak +
    'Na 1301, use "Arquivo em pasta" com este arquivo.' + sLineBreak + 'Abrir a pasta agora?',
    mtInformation, [mbYes, mbNo], 0) = mrYes then
    ShellExecute(0, 'open', 'explorer.exe', PChar('/select,"' + Destino + '"'), nil, SW_SHOWNORMAL);
end;

procedure TFrmPrincipal.BtnConfigClick(Sender: TObject);
begin
  if EditarConfiguracao(FCfg) then
  begin
    FProv := nil;  // nova fonte de dados na proxima analise
    cmbModo.ItemIndex := Ord(FCfg.ModoPesquisa);
    MostrarCabecalho;
    Status('Configuração salva.');
  end;
end;

procedure TFrmPrincipal.CarregarHistorico;
var
  R: TRegistroLog;
  LI: TListItem;
begin
  lvHist.Items.BeginUpdate;
  try
    lvHist.Items.Clear;
    try
      for R in LerHistorico(FCfg.PastaBase, 500) do
      begin
        LI := lvHist.Items.Add;
        LI.Caption := R.DataHora;
        LI.SubItems.Add(R.Acao);
        LI.SubItems.Add(R.Usuario);
        LI.SubItems.Add(R.Maquina);
        LI.SubItems.Add(R.Chave);
        LI.SubItems.Add(R.Filial);
        LI.SubItems.Add(R.Resultado);
        LI.SubItems.Add(R.Detalhe);
      end;
    except
      on E: Exception do
        Status('Não foi possível ler o histórico: ' + E.Message);
    end;
  finally
    lvHist.Items.EndUpdate;
  end;
end;

procedure TFrmPrincipal.BtnHistClick(Sender: TObject);
begin
  CarregarHistorico;
end;

procedure TFrmPrincipal.PaginasChange(Sender: TObject);
begin
  if Paginas.ActivePage = tabHist then
    CarregarHistorico;
end;

end.
