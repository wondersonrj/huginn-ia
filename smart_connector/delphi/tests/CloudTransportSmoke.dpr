program CloudTransportSmoke;

{$APPTYPE CONSOLE}

uses
  System.SysUtils, System.JSON, Winapi.Windows,
  Huginn.CloudTransport in '..\Huginn.CloudTransport.pas',
  Huginn.ConnectionMode in '..\Huginn.ConnectionMode.pas',
  Huginn.Credentials in '..\Huginn.Credentials.pas';

type
  TSource = class(TInterfacedObject, IResumoGerencialSource)
  public
    procedure OpenModule(const Module: string);
  end;

procedure TSource.OpenModule(const Module: string);
begin
  raise Exception.Create('synthetic failure');
end;

procedure Check(Value: Boolean);
begin
  if not Value then raise Exception.Create('Assertion failed');
end;

procedure UnitTests;
var LocalSource, CloudSource, Selected: IResumoGerencialSource;
  Transport: IHuginnTransport; FailedAsExpected: Boolean;
begin
  LocalSource := TSource.Create;
  CloudSource := TSource.Create;
  Check(SelectSource(cmFireDACLocal, LocalSource, CloudSource) = LocalSource);
  Selected := SelectSource(cmHuginnCloud, LocalSource, CloudSource);
  Check(Selected = CloudSource);
  FailedAsExpected := False;
  try Selected.OpenModule('vendas'); except FailedAsExpected := True; end;
  Check(FailedAsExpected and (Selected = CloudSource)); // No automatic local fallback
  FailedAsExpected := False;
  try Transport := THuginnCloudTransport.Create('http://localhost', StringOfChar('x', 32), 5000);
  except on E: EHuginnCloud do FailedAsExpected := True; end;
  Check(FailedAsExpected);
  Transport := THuginnCloudTransport.Create('https://localhost', StringOfChar('x', 32), 5000);
  FailedAsExpected := False;
  try Transport.GetJson('/sql'); except on E: EHuginnCloud do FailedAsExpected := True; end;
  Check(FailedAsExpected);
  Writeln('Synthetic source selection and transport policy: PASS');
end;

procedure Probe(const Origin: string);
var Transport: IHuginnTransport; Payload: TJSONObject; Status: TJSONValue;
begin
  Transport := THuginnCloudTransport.Create(Origin, ReadCloudToken(Origin), 5000);
  Payload := Transport.GetJson('/health');
  try
    Status := Payload.GetValue('status');
    Check((Status <> nil) and (Status.Value = 'ok'));
    Writeln('Authenticated HTTPS health: PASS. Oracle/report modules not validated.');
  finally Payload.Free; end;
end;

begin
  try
    if ParamCount = 0 then UnitTests
    else if (ParamCount = 2) and (ParamStr(1) = '--probe') then Probe(ParamStr(2))
    else raise Exception.Create('Use no arguments for synthetic tests, or --probe https://host:port');
  except
    // Never emit raw exception messages, HTTP bodies, tokens or URL values.
    on E: Exception do begin Writeln('FAIL. Consulte o diagnostico HTTPS e a configuracao local.'); Halt(1); end;
  end;
end.
