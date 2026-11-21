program HuginnFVDiag;

{ HUGINN IA - Forca de Vendas - Diagnostico v0.1 (somente leitura)
  Delphi 12 + UniDAC (provider Oracle). Requer as units do UniDAC no Library Path. }

uses
  Vcl.Forms,
  uDpapi in 'uDpapi.pas',
  uConfig in 'uConfig.pas',
  uConexao in 'uConexao.pas',
  uDiag in 'uDiag.pas',
  uPrincipal in 'uPrincipal.pas';

begin
  ReportMemoryLeaksOnShutdown := DebugHook <> 0;
  Application.Initialize;
  Application.MainFormOnTaskbar := True;
  Application.Title := 'HUGINN FV Diagnóstico';
  Application.CreateForm(TFrmPrincipal, FrmPrincipal);
  Application.Run;
end.
