unit Huginn.CloudTransport;

interface

uses System.SysUtils, System.JSON;

type
  EHuginnCloud = class(Exception);

  IHuginnTransport = interface
    ['{5D911EDA-A395-41AA-B79F-0B054489C9AC}']
    function GetJson(const Path: string): TJSONObject; // Caller owns result
  end;

  THuginnCloudTransport = class(TInterfacedObject, IHuginnTransport)
  private
    FOrigin: string;
    FToken: string;
    FTimeoutMs: Integer;
  public
    constructor Create(const Origin, Token: string; TimeoutMs: Integer);
    function GetJson(const Path: string): TJSONObject;
  end;

function CloudFailureMessage(Code: Integer): string;

implementation

uses System.Variants, System.Win.ComObj, System.RegularExpressions,
  Winapi.Windows, Winapi.ActiveX;

function CloudFailureMessage(Code: Integer): string;
begin
  case Code and $FFFF of
    12002: Result := 'Tempo de conexao excedido. Verifique rede/proxy na sessao Cloud.';
    12007: Result := 'DNS indisponivel na sessao Cloud.';
    12029, 12030: Result := 'Conector inacessivel. Verifique rota, porta e proxy autorizados.';
    12037, 12038, 12044, 12045, 12175:
      Result := 'Falha de certificado/TLS. Corrija hostname, validade e cadeia; nao ignore a verificacao.';
    12166, 12167: Result := 'Configuracao de proxy indisponivel. Consulte o administrador.';
  else
    Result := 'Falha no transporte HTTPS. Execute o diagnostico na sessao WinThor Cloud.';
  end;
end;

constructor THuginnCloudTransport.Create(const Origin, Token: string; TimeoutMs: Integer);
var I: Integer;
begin
  inherited Create;
  // Root origin only. No userinfo, path, query, fragment, whitespace or token in URL.
  if not TRegEx.IsMatch(Origin,
    '^https://([A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?|\[[0-9A-Fa-f:]+\])(:[0-9]{1,5})?/?$') then
    raise EHuginnCloud.Create('Informe origem HTTPS sem caminho, credenciais, query ou fragmento.');
  if (TimeoutMs < 1000) or (TimeoutMs > 30000) or (Length(Token) < 32) then
    raise EHuginnCloud.Create('Token ou timeout invalido.');
  for I := 1 to Length(Token) do
    if (Ord(Token[I]) <= 32) or (Ord(Token[I]) = 127) then
      raise EHuginnCloud.Create('Token invalido.');
  FOrigin := Origin;
  if FOrigin[Length(FOrigin)] = '/' then Delete(FOrigin, Length(FOrigin), 1);
  FToken := Token; // Only in process memory; never log an exception/body or token.
  FTimeoutMs := TimeoutMs;
end;

function THuginnCloudTransport.GetJson(const Path: string): TJSONObject;
var Request: OleVariant; Status: Integer; Text: string; Value: TJSONValue;
  InitResult: HRESULT;
begin
  if (Path <> '/health') and (Path <> '/oracle/test') and
     (Path <> '/oracle/server-time') and (Path <> '/api/v1/capabilities') then
    raise EHuginnCloud.Create('Operacao nao autorizada pelo adaptador.');
  InitResult := CoInitializeEx(nil, COINIT_APARTMENTTHREADED);
  if Failed(InitResult) and (InitResult <> RPC_E_CHANGED_MODE) then
    raise EHuginnCloud.Create('Transporte Windows indisponivel.');
  try
    try
      Request := CreateOleObject('WinHttp.WinHttpRequest.5.1');
      Request.SetProxy(0);
      Request.SetTimeouts(FTimeoutMs, FTimeoutMs, FTimeoutMs, FTimeoutMs);
      Request.Option[6] := False; // Redirects disabled; no Bearer forwarding
      Request.Option[9] := 2048;  // TLS 1.2, OS certificate/hostname validation
      Request.SetAutoLogonPolicy(2); // Never silently send Windows credentials
      Request.Open('GET', FOrigin + Path, False);
      Request.SetRequestHeader('Authorization', 'Bearer ' + FToken);
      Request.SetRequestHeader('Accept', 'application/json');
      Request.Send(EmptyParam);
      Status := Request.Status;
      case Status of
        200: ;
        401: raise EHuginnCloud.Create('Token rejeitado. Reconfigure a credencial da API.');
        403: raise EHuginnCloud.Create('Operacao ou filial nao autorizada.');
        404: raise EHuginnCloud.Create('Endpoint indisponivel nesta versao ou rota do proxy.');
        407: raise EHuginnCloud.Create('Proxy exige autenticacao. Consulte o administrador Cloud.');
        503: raise EHuginnCloud.Create('Servico ou Oracle indisponivel no conector.');
      else
        if (Status >= 300) and (Status < 400) then
          raise EHuginnCloud.Create('Redirecionamento rejeitado. Configure a origem HTTPS final.');
        raise EHuginnCloud.Create('Resposta HTTP inesperada. Execute o diagnostico.');
      end;
      Text := Request.ResponseText;
      if Length(Text) > 65536 then raise EHuginnCloud.Create('Resposta excede o limite.');
      Value := TJSONObject.ParseJSONValue(Text);
      if not (Value is TJSONObject) then begin
        Value.Free;
        raise EHuginnCloud.Create('Resposta JSON invalida.');
      end;
      Result := TJSONObject(Value);
    except
      on E: EHuginnCloud do raise;
      on E: EOleException do raise EHuginnCloud.Create(CloudFailureMessage(E.ErrorCode));
      on E: Exception do raise EHuginnCloud.Create('Falha HTTPS. Nenhuma troca automatica para FireDAC foi realizada.');
    end;
  finally
    Request := Unassigned;
    if Succeeded(InitResult) then CoUninitialize;
  end;
end;

end.
