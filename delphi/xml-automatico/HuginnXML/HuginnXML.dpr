program HuginnXML;

{ HUGINN XML Automatico v0.1 - conferencia de NF-e de entrada antes da 1301.
  Delphi 12 + UniDAC (provider Oracle). Somente leitura no WinThor. }

uses
  Vcl.Forms,
  uTipos in 'src\uTipos.pas',
  uValidacao in 'src\uValidacao.pas',
  uXmlNFe in 'src\uXmlNFe.pas',
  uProvedor in 'src\uProvedor.pas',
  uProvedorDemo in 'src\uProvedorDemo.pas',
  uDpapi in 'src\uDpapi.pas',
  uConfig in 'src\uConfig.pas',
  uConexao in 'src\uConexao.pas',
  uProvedorOracle in 'src\uProvedorOracle.pas',
  uMotor in 'src\uMotor.pas',
  uRegistro in 'src\uRegistro.pas',
  uLog in 'src\uLog.pas',
  uFrmConexao in 'src\uFrmConexao.pas',
  uPrincipal in 'src\uPrincipal.pas';

begin
  {$IFDEF DEBUG}
  ReportMemoryLeaksOnShutdown := True;
  {$ENDIF}
  Application.Initialize;
  Application.MainFormOnTaskbar := True;
  Application.Title := 'HUGINN XML Automático';
  Application.CreateForm(TFrmPrincipal, FrmPrincipal);
  Application.Run;
end.
