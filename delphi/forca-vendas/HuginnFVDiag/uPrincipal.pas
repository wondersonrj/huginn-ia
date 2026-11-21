unit uPrincipal;

{ HUGINN IA - Forca de Vendas - Diagnostico v0.1
  Tela montada em codigo (sem .dfm). Estilo HUGINN: azul-marinho, azul eletrico, ciano. }

interface

uses
  Winapi.Windows, Winapi.ShellAPI, System.SysUtils, System.Classes, System.IOUtils,
  System.UITypes,
  Vcl.Forms, Vcl.Controls, Vcl.StdCtrls, Vcl.ExtCtrls, Vcl.Graphics, Vcl.Dialogs,
  uConfig;

type
  TFrmPrincipal = class(TForm)
  private
    edtHost, edtPorta, edtServico, edtUsuario, edtSenha, edtOwner, edtPasta: TEdit;
    chkSID, chkSalvarSenha, chkAmostraPed, chkAmostraCli: TCheckBox;
    btnTestar, btnGerar, btnPasta: TButton;
    mmoLog: TMemo;
    FUltimoZip: string;
    FTopo: Integer;
    procedure MontarTela;
    function NovoLabel(AParent: TWinControl; const ATexto: string;
      AX, AY: Integer; ACor: TColor; ATam: Integer = 9; ABold: Boolean = False): TLabel;
    function NovoCampo(const ARotulo: string; ALargura: Integer = 260;
      ASenha: Boolean = False): TEdit;
    function NovaOpcao(const ARotulo: string; AX, AY: Integer): TCheckBox;
    function NovoBotao(const ATexto: string; AX: Integer; AClick: TNotifyEvent): TButton;
    procedure Log(const S: string);
    procedure Habilitar(A: Boolean);
    procedure CarregarTela;
    function LerTela(out C: TFVConfig): Boolean;
    procedure BtnTestarClick(Sender: TObject);
    procedure BtnGerarClick(Sender: TObject);
    procedure BtnPastaClick(Sender: TObject);
  public
    constructor Create(AOwner: TComponent); override;
  end;

var
  FrmPrincipal: TFrmPrincipal;

implementation

uses
  Uni, uConexao, uDiag;

const
  COR_FUNDO   = TColor($0026140B); // #0B1426 azul-marinho
  COR_PAINEL  = TColor($00100904); // #040910 quase preto
  COR_CAMPO   = TColor($00402A1A); // #1A2A40
  COR_TEXTO   = TColor($00F7EDE6); // #E6EDF7
  COR_SUAVE   = TColor($00B09A8A); // #8A9AB0
  COR_ELETRICO= TColor($00FF901E); // #1E90FF
  COR_CIANO   = TColor($00FFE500); // #00E5FF

{ TFrmPrincipal }

constructor TFrmPrincipal.Create(AOwner: TComponent);
begin
  inherited CreateNew(AOwner);
  MontarTela;
  CarregarTela;
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

function TFrmPrincipal.NovoCampo(const ARotulo: string; ALargura: Integer;
  ASenha: Boolean): TEdit;
begin
  NovoLabel(Self, ARotulo, 24, FTopo + 4, COR_SUAVE);
  Result := TEdit.Create(Self);
  Result.Parent := Self;
  Result.Left := 190;
  Result.Top := FTopo;
  Result.Width := ALargura;
  Result.ParentFont := False;
  Result.Font.Name := 'Segoe UI';
  Result.Font.Size := 10;
  Result.Font.Color := COR_TEXTO;
  Result.Color := COR_CAMPO;
  Result.BorderStyle := bsSingle;
  if ASenha then
    Result.PasswordChar := #$25CF;
  Inc(FTopo, 32);
end;

function TFrmPrincipal.NovaOpcao(const ARotulo: string; AX, AY: Integer): TCheckBox;
begin
  // Caption vazio + TLabel ao lado: o checkbox nativo ignora a cor da fonte.
  Result := TCheckBox.Create(Self);
  Result.Parent := Self;
  Result.Left := AX;
  Result.Top := AY + 2;
  Result.Width := 17;
  Result.Caption := '';
  NovoLabel(Self, ARotulo, AX + 22, AY, COR_TEXTO);
end;

function TFrmPrincipal.NovoBotao(const ATexto: string; AX: Integer;
  AClick: TNotifyEvent): TButton;
begin
  Result := TButton.Create(Self);
  Result.Parent := Self;
  Result.Left := AX;
  Result.Top := FTopo;
  Result.Width := 170;
  Result.Height := 32;
  Result.Caption := ATexto;
  Result.OnClick := AClick;
end;

procedure TFrmPrincipal.MontarTela;
var
  Topo: TPanel;
  Faixa: TShape;
begin
  Caption := 'HUGINN Força de Vendas — Diagnóstico v' + VERSAO_DIAG + ' (somente leitura)';
  Width := 860;
  Height := 700;
  Position := poScreenCenter;
  Color := COR_FUNDO;
  Font.Name := 'Segoe UI';
  Font.Size := 9;
  Font.Color := COR_TEXTO;
  Constraints.MinWidth := 760;
  Constraints.MinHeight := 560;

  Topo := TPanel.Create(Self);
  Topo.Parent := Self;
  Topo.Align := alTop;
  Topo.Height := 74;
  Topo.BevelOuter := bvNone;
  Topo.ParentBackground := False;
  Topo.Color := COR_PAINEL;
  NovoLabel(Topo, 'HUGINN', 24, 10, COR_CIANO, 20, True);
  NovoLabel(Topo, 'Força de Vendas · Diagnóstico da integradora WinThor  v' +
    VERSAO_DIAG, 150, 18, COR_TEXTO, 11);
  NovoLabel(Topo, 'Inteligência antes da decisão.   Somente leitura — nada é gravado no banco.',
    150, 42, COR_SUAVE, 9);

  Faixa := TShape.Create(Self);
  Faixa.Parent := Self;
  Faixa.Align := alTop;
  Faixa.Height := 3;
  Faixa.Top := 80;
  Faixa.Pen.Style := psClear;
  Faixa.Brush.Color := COR_ELETRICO;

  FTopo := 96;
  edtHost := NovoCampo('Servidor Oracle (IP/host)');
  edtPorta := NovoCampo('Porta', 90);
  edtServico := NovoCampo('Service name / SID');
  chkSID := NovaOpcao('Usar SID em vez de Service name', 470, edtServico.Top + 2);
  edtUsuario := NovoCampo('Usuário Oracle');
  edtSenha := NovoCampo('Senha', 260, True);
  chkSalvarSenha := NovaOpcao('Lembrar senha (protegida pelo Windows)', 470, edtSenha.Top + 2);
  edtOwner := NovoCampo('Schema WinThor (owner)');
  NovoLabel(Self, 'vazio = mesmo do usuário', 470, edtOwner.Top + 4, COR_SUAVE);
  edtPasta := NovoCampo('Pasta de saída', 540);

  chkAmostraPed := NovaOpcao('Incluir amostra dos últimos 50 pedidos da integradora (PCPEDCFV / PCPEDIFV)',
    190, FTopo);
  Inc(FTopo, 26);
  chkAmostraCli := NovaOpcao('Incluir amostra de PCCLIENTFV (contém dados pessoais — LGPD)',
    190, FTopo);
  Inc(FTopo, 36);

  btnTestar := NovoBotao('Testar conexão', 190, BtnTestarClick);
  btnGerar := NovoBotao('Gerar diagnóstico (ZIP)', 372, BtnGerarClick);
  btnPasta := NovoBotao('Abrir pasta do ZIP', 554, BtnPastaClick);
  btnPasta.Enabled := False;
  Inc(FTopo, 44);

  mmoLog := TMemo.Create(Self);
  mmoLog.Parent := Self;
  mmoLog.Left := 24;
  mmoLog.Top := FTopo;
  mmoLog.Width := ClientWidth - 48;
  mmoLog.Height := ClientHeight - FTopo - 16;
  mmoLog.Anchors := [akLeft, akTop, akRight, akBottom];
  mmoLog.ReadOnly := True;
  mmoLog.ScrollBars := ssBoth;
  mmoLog.WordWrap := False;
  mmoLog.ParentFont := False;
  mmoLog.Font.Name := 'Consolas';
  mmoLog.Font.Size := 9;
  mmoLog.Font.Color := COR_CIANO;
  mmoLog.Color := COR_PAINEL;
end;

procedure TFrmPrincipal.Log(const S: string);
begin
  mmoLog.Lines.Add(FormatDateTime('hh:nn:ss', Now) + '  ' + S);
end;

procedure TFrmPrincipal.Habilitar(A: Boolean);
begin
  btnTestar.Enabled := A;
  btnGerar.Enabled := A;
  btnPasta.Enabled := A and (FUltimoZip <> '');
  if A then
    Screen.Cursor := crDefault
  else
    Screen.Cursor := crAppStarting;
end;

procedure TFrmPrincipal.CarregarTela;
var
  C: TFVConfig;
begin
  C := CarregarConfig;
  edtHost.Text := C.Host;
  edtPorta.Text := IntToStr(C.Porta);
  edtServico.Text := C.Servico;
  chkSID.Checked := C.UsarSID;
  edtUsuario.Text := C.Usuario;
  edtSenha.Text := C.Senha;
  chkSalvarSenha.Checked := C.SalvarSenha;
  edtOwner.Text := C.Owner;
  edtPasta.Text := C.PastaSaida;
  chkAmostraPed.Checked := C.AmostraPedidos;
  chkAmostraCli.Checked := C.AmostraClientes;
  Log('Configuração: ' + ArquivoIni);
  if not C.ModoDireto then
    Log('Modo direto DESLIGADO no .ini: usando Oracle Client (Service name = alias TNS).');
end;

function TFrmPrincipal.LerTela(out C: TFVConfig): Boolean;
var
  Base: TFVConfig;
begin
  Result := False;
  Base := CarregarConfig;   // preserva opcoes so do .ini (ModoDireto)
  C := Base;
  C.Host := Trim(edtHost.Text);
  C.Porta := StrToIntDef(Trim(edtPorta.Text), 0);
  C.Servico := Trim(edtServico.Text);
  C.UsarSID := chkSID.Checked;
  C.Usuario := Trim(edtUsuario.Text);
  C.Senha := edtSenha.Text;
  C.SalvarSenha := chkSalvarSenha.Checked;
  C.Owner := UpperCase(Trim(edtOwner.Text));
  C.PastaSaida := Trim(edtPasta.Text);
  C.AmostraPedidos := chkAmostraPed.Checked;
  C.AmostraClientes := chkAmostraCli.Checked;

  if C.ModoDireto and ((C.Host = '') or (C.Porta <= 0)) then
  begin
    ShowMessage('Informe o servidor e a porta do Oracle.');
    Exit;
  end;
  if (C.Servico = '') or (C.Usuario = '') or (C.Senha = '') then
  begin
    ShowMessage('Informe service name/SID, usuário e senha.');
    Exit;
  end;
  if not IdentificadorValido(C.OwnerEfetivo) then
  begin
    ShowMessage('Schema WinThor inválido: ' + C.OwnerEfetivo);
    Exit;
  end;
  if C.PastaSaida = '' then
  begin
    ShowMessage('Informe a pasta de saída.');
    Exit;
  end;
  SalvarConfig(C);
  Result := True;
end;

procedure TFrmPrincipal.BtnTestarClick(Sender: TObject);
var
  C: TFVConfig;
begin
  if not LerTela(C) then
    Exit;
  Habilitar(False);
  Log('Conectando em ' + C.ServidorTexto + ' como ' + C.Usuario + ' ...');
  TThread.CreateAnonymousThread(
    procedure
    var
      Conn: TUniConnection;
      Msg: string;
    begin
      try
        Conn := CriarConexao(C);
        try
          Conn.Connect;
          Msg := 'Conexão OK. Oracle ' + Conn.ServerVersion;
          Conn.Disconnect;
        finally
          Conn.Free;
        end;
      except
        on E: Exception do
          Msg := 'FALHA na conexão: ' + E.ClassName + ' - ' + E.Message;
      end;
      TThread.Queue(nil,
        procedure
        begin
          Log(Msg);
          Habilitar(True);
        end);
    end).Start;
end;

procedure TFrmPrincipal.BtnGerarClick(Sender: TObject);
var
  C: TFVConfig;
begin
  if not LerTela(C) then
    Exit;
  if C.AmostraClientes and (MessageDlg(
    'A amostra de PCCLIENTFV contém dados pessoais de clientes.' + sLineBreak +
    'Envie o ZIP somente por canal seguro. Continuar?',
    mtConfirmation, [mbYes, mbNo], 0) <> mrYes) then
    Exit;
  ForceDirectories(C.PastaSaida);
  Habilitar(False);
  mmoLog.Lines.Clear;
  TThread.CreateAnonymousThread(
    procedure
    var
      Conn: TUniConnection;
      D: TFVDiagnostico;
      Zip, Msg: string;
    begin
      Zip := '';
      try
        Conn := CriarConexao(C);
        try
          Conn.Connect;
          D := TFVDiagnostico.Create(Conn, C.OwnerEfetivo, C.ServidorTexto,
            procedure(const S: string)
            var
              L: string;
            begin
              L := S;
              TThread.Queue(nil,
                procedure
                begin
                  Log(L);
                end);
            end);
          try
            D.AmostraPedidos := C.AmostraPedidos;
            D.AmostraClientes := C.AmostraClientes;
            Zip := D.Executar(C.PastaSaida);
            if D.Erros = 0 then
              Msg := 'Diagnóstico concluído sem erros. Envie o ZIP para a HUGINN.'
            else
              Msg := Format('Diagnóstico concluído com %d erro(s) (registrados no manifesto). ' +
                'Envie o ZIP assim mesmo.', [D.Erros]);
          finally
            D.Free;
          end;
          Conn.Disconnect;
        finally
          Conn.Free;
        end;
      except
        on E: Exception do
          Msg := 'FALHA: ' + E.ClassName + ' - ' + E.Message;
      end;
      TThread.Queue(nil,
        procedure
        begin
          if Zip <> '' then
            FUltimoZip := Zip;
          Log(Msg);
          Habilitar(True);
        end);
    end).Start;
end;

procedure TFrmPrincipal.BtnPastaClick(Sender: TObject);
begin
  if (FUltimoZip <> '') and FileExists(FUltimoZip) then
    ShellExecute(0, 'open', 'explorer.exe',
      PChar('/select,"' + FUltimoZip + '"'), nil, SW_SHOWNORMAL);
end;

end.
