unit uFrmConexao;

{ HUGINN XML Automatico - tela de configuracao (conexao Oracle e opcoes).
  Montada em codigo (sem .dfm). A senha so e salva se o usuario marcar, via DPAPI. }

interface

uses
  System.SysUtils, System.Classes, Vcl.Forms, Vcl.Controls, Vcl.StdCtrls,
  Vcl.ExtCtrls, Vcl.Graphics, uConfig;

function EditarConfiguracao(var C: TXmlConfig): Boolean;

implementation

uses
  Vcl.Dialogs, System.UITypes, Uni, uConexao;

type
  TFrmConexao = class(TForm)
  private
    FTopo: Integer;
    edtHost, edtPorta, edtServico, edtUsuario, edtSenha, edtOwner,
    edtTolerancia, edtPastaBase, edtLiberados, edtCodFunc, edtJanela: TEdit;
    chkSID, chkDireto, chkSalvarSenha, chkOracle, chkFator253, chkEntrega: TCheckBox;
    function Campo(const Rotulo: string; Largura: Integer = 260; Senha: Boolean = False): TEdit;
    function Opcao(const Rotulo: string; X, Y: Integer): TCheckBox;
    procedure BtnTestarClick(Sender: TObject);
  public
    constructor CriarCom(const C: TXmlConfig);
    function Ler(out C: TXmlConfig; const Base: TXmlConfig): Boolean;
  end;

constructor TFrmConexao.CriarCom(const C: TXmlConfig);
var
  B: TButton;
begin
  inherited CreateNew(nil);
  Caption := 'HUGINN XML Automático — Configuração';
  BorderStyle := bsDialog;
  Position := poMainFormCenter;
  Width := 720;
  Height := 690;
  Font.Name := 'Segoe UI';
  Font.Size := 9;
  FTopo := 16;

  chkOracle := Opcao('Usar o Oracle do WinThor (desmarcado = demonstração, sem banco)', 24, FTopo);
  Inc(FTopo, 32);
  edtHost := Campo('Servidor Oracle (IP/host)');
  edtPorta := Campo('Porta', 90);
  edtServico := Campo('Service name / SID');
  chkSID := Opcao('Usar SID', 470, edtServico.Top + 2);
  edtUsuario := Campo('Usuário Oracle (só leitura)');
  edtSenha := Campo('Senha', 260, True);
  chkSalvarSenha := Opcao('Lembrar senha (protegida pelo Windows)', 470, edtSenha.Top + 2);
  edtOwner := Campo('Schema WinThor (owner)');
  chkDireto := Opcao('Modo direto do UniDAC (sem Oracle Client)', 190, FTopo);
  Inc(FTopo, 36);
  edtTolerancia := Campo('Tolerância de custo (%)', 90);
  chkFator253 := Opcao('Usar fator de conversão da rotina 253 (igual à opção da 1301)', 190, FTopo);
  Inc(FTopo, 32);
  chkEntrega := Opcao('Enviar para a fila da 1321 (GRAVA XML em PCNFENTXML/PCMANIFDESTINATARIO)', 190, FTopo);
  chkEntrega.Font.Style := [fsBold];
  Inc(FTopo, 32);
  edtCodFunc := Campo('Matrícula (CODFUNC)', 90);
  edtJanela := Campo('Janela da 1321 (dias)', 90);
  edtPastaBase := Campo('Pasta do HUGINN (logs/recebidos)', 480);
  edtLiberados := Campo('Pasta onde liberar o XML para a 1301', 480);

  B := TButton.Create(Self);
  B.Parent := Self;
  B.SetBounds(190, FTopo + 8, 150, 30);
  B.Caption := 'Testar conexão';
  B.OnClick := BtnTestarClick;

  B := TButton.Create(Self);
  B.Parent := Self;
  B.SetBounds(ClientWidth - 260, ClientHeight - 50, 110, 30);
  B.Caption := 'Salvar';
  B.ModalResult := mrOk;
  B.Default := True;

  B := TButton.Create(Self);
  B.Parent := Self;
  B.SetBounds(ClientWidth - 140, ClientHeight - 50, 110, 30);
  B.Caption := 'Cancelar';
  B.ModalResult := mrCancel;
  B.Cancel := True;

  chkOracle.Checked := C.UsarOracle;
  edtHost.Text := C.Host;
  edtPorta.Text := IntToStr(C.Porta);
  edtServico.Text := C.Servico;
  chkSID.Checked := C.UsarSID;
  chkDireto.Checked := C.ModoDireto;
  edtUsuario.Text := C.Usuario;
  edtSenha.Text := C.Senha;
  chkSalvarSenha.Checked := C.SalvarSenha;
  edtOwner.Text := C.Owner;
  edtTolerancia.Text := FloatToStr(C.ToleranciaCustoPct);
  chkFator253.Checked := C.UsarFator253;
  edtPastaBase.Text := C.PastaBase;
  edtLiberados.Text := C.PastaLiberados;
  chkEntrega.Checked := C.Entrega1321;
  edtCodFunc.Text := IntToStr(C.CodFunc);
  edtJanela.Text := IntToStr(C.JanelaDias1321);
end;

function TFrmConexao.Campo(const Rotulo: string; Largura: Integer; Senha: Boolean): TEdit;
var
  L: TLabel;
begin
  L := TLabel.Create(Self);
  L.Parent := Self;
  L.SetBounds(24, FTopo + 4, 160, 20);
  L.Caption := Rotulo;
  Result := TEdit.Create(Self);
  Result.Parent := Self;
  Result.SetBounds(190, FTopo, Largura, 24);
  if Senha then
    Result.PasswordChar := #$25CF;
  Inc(FTopo, 32);
end;

function TFrmConexao.Opcao(const Rotulo: string; X, Y: Integer): TCheckBox;
begin
  Result := TCheckBox.Create(Self);
  Result.Parent := Self;
  Result.SetBounds(X, Y, 480, 20);
  Result.Caption := Rotulo;
end;

function TFrmConexao.Ler(out C: TXmlConfig; const Base: TXmlConfig): Boolean;
var
  Tol: Double;
begin
  C := Base;
  C.UsarOracle := chkOracle.Checked;
  C.Host := Trim(edtHost.Text);
  C.Porta := StrToIntDef(Trim(edtPorta.Text), 1521);
  C.Servico := Trim(edtServico.Text);
  C.UsarSID := chkSID.Checked;
  C.ModoDireto := chkDireto.Checked;
  C.Usuario := Trim(edtUsuario.Text);
  C.Senha := edtSenha.Text;
  C.SalvarSenha := chkSalvarSenha.Checked;
  C.Owner := UpperCase(Trim(edtOwner.Text));
  if not TryStrToFloat(Trim(edtTolerancia.Text), Tol) or (Tol < 0) then
    Tol := 5;
  C.ToleranciaCustoPct := Tol;
  C.UsarFator253 := chkFator253.Checked;
  C.PastaBase := Trim(edtPastaBase.Text);
  C.PastaLiberados := Trim(edtLiberados.Text);
  C.Entrega1321 := chkEntrega.Checked;
  C.CodFunc := StrToIntDef(Trim(edtCodFunc.Text), 0);
  C.JanelaDias1321 := StrToIntDef(Trim(edtJanela.Text), 90);
  Result := True;
  if C.Entrega1321 and ((not C.UsarOracle) or (C.CodFunc <= 0)) then
  begin
    MessageDlg('O envio para a 1321 exige o Oracle ligado e a matrícula (CODFUNC) preenchida.', mtWarning, [mbOK], 0);
    Result := False;
  end;
  if (C.Owner <> '') and not IdentificadorValido(C.Owner) then
  begin
    MessageDlg('Schema (owner) inválido.', mtWarning, [mbOK], 0);
    Result := False;
  end;
end;

procedure TFrmConexao.BtnTestarClick(Sender: TObject);
var
  C: TXmlConfig;
  Con: TUniConnection;
begin
  if not Ler(C, Default(TXmlConfig)) then
    Exit;
  Screen.Cursor := crHourGlass;
  try
    Con := CriarConexao(C);
    try
      Con.Connect;
      MessageDlg('Conexão OK (somente leitura). Servidor: ' + C.ServidorTexto, mtInformation, [mbOK], 0);
    finally
      Con.Free;
    end;
  except
    on E: Exception do
    begin
      Screen.Cursor := crDefault;
      MessageDlg('Falha na conexão: ' + E.Message, mtError, [mbOK], 0);
    end;
  end;
  Screen.Cursor := crDefault;
end;

function EditarConfiguracao(var C: TXmlConfig): Boolean;
var
  F: TFrmConexao;
  Novo: TXmlConfig;
begin
  Result := False;
  F := TFrmConexao.CriarCom(C);
  try
    while F.ShowModal = mrOk do
      if F.Ler(Novo, C) then
      begin
        C := Novo;
        SalvarConfig(C);
        Exit(True);
      end;
  finally
    F.Free;
  end;
end;

end.
