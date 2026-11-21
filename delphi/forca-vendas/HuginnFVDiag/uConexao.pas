unit uConexao;

{ HUGINN IA - Conexao UniDAC com o Oracle do WinThor. }

interface

uses
  Uni, uConfig;

function CriarConexao(const C: TFVConfig): TUniConnection;

implementation

uses
  System.SysUtils, OracleUniProvider;

function CriarConexao(const C: TFVConfig): TUniConnection;
begin
  Result := TUniConnection.Create(nil);
  try
    Result.ProviderName := 'Oracle';
    Result.LoginPrompt := False;
    // Modo direto (sem Oracle Client instalado). Desligue no .ini (ModoDireto=0)
    // para usar o Oracle Client/TNS da maquina; nesse caso "Servico" = alias TNS.
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
