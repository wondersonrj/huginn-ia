program TestesHuginnXML;

{ Testes DUnitX do HUGINN XML Automatico (console). Nao acessa banco. }

{$APPTYPE CONSOLE}
{$STRONGLINKTYPES ON}

uses
  System.SysUtils,
  DUnitX.TestFramework,
  DUnitX.Loggers.Console,
  DUnitX.Loggers.Xml.NUnit,
  uTipos in '..\src\uTipos.pas',
  uValidacao in '..\src\uValidacao.pas',
  uXmlNFe in '..\src\uXmlNFe.pas',
  uProvedor in '..\src\uProvedor.pas',
  uProvedorDemo in '..\src\uProvedorDemo.pas',
  uMotor in '..\src\uMotor.pas',
  uRegistro in '..\src\uRegistro.pas',
  uTestesHuginnXML in 'uTestesHuginnXML.pas';

var
  Runner: ITestRunner;
  Resultados: IRunResults;
begin
  try
    TDUnitX.CheckCommandLine;
    Runner := TDUnitX.CreateRunner;
    Runner.UseRTTI := True;
    Runner.FailsOnNoAsserts := False;
    Runner.AddLogger(TDUnitXConsoleLogger.Create(True));
    Runner.AddLogger(TDUnitXXMLNUnitFileLogger.Create(TDUnitX.Options.XMLOutputFile));
    Resultados := Runner.Execute;
    if not Resultados.AllPassed then
      System.ExitCode := EXIT_ERRORS;
  except
    on E: Exception do
    begin
      System.Writeln(E.ClassName, ': ', E.Message);
      System.ExitCode := EXIT_ERRORS;
    end;
  end;
  if TDUnitX.Options.ExitBehavior = TDUnitXExitBehavior.Pause then
  begin
    System.Write('Pressione Enter para sair...');
    System.Readln;
  end;
end.
