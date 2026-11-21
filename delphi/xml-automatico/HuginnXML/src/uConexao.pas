unit uConexao;

{ HUGINN XML Automatico - conexao UniDAC com o Oracle do WinThor.
  Mesmo padrao homologado no HuginnFVDiag (modo direto, sem Oracle Client). }

interface

uses
  Uni, uConfig;

function CriarConexao(const C: TXmlConfig): TUniConnection;

implementation

uses
  System.SysUtils, OracleUniProvider;

function CriarConexao(const C: TXmlConfig): TUniConnection;
begin
  Result := TUniConnection.Create(nil);
  try
    Result.ProviderName := 'Oracle';
    Result.LoginPrompt := False;
    // Modo direto (sem Oracle Client). ModoDireto=0 no .ini usa o Client/TNS da maquina.
    if C.ModoDireto then
    begin
      Result.SpecificOptions.Values['Direct'] := 'True';
      Result.Server := C.ServidorTexto;
    end
    else
    begin
      Result.SpecificOptions.Values['Direct'] := 'False';
      Result.Server := C.Servico;
    end;
    Result.Username := C.Usuario;
    Result.Password := C.Senha;
  except
    Result.Free;
    raise;
  end;
end;

end.
