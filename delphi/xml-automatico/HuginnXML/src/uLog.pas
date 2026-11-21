unit uLog;

{ HUGINN XML Automatico - log de operacoes.

  Um arquivo por dia: <PastaBase>\logs\AAAA-MM-DD.jsonl, uma linha JSON por acao
  (abrir, analisar, reanalisar, liberar, erro). Registra data/hora, usuario e
  maquina do Windows, versao, regra, chave, SHA-256, filial, resultado e decisao.
  NAO registra o XML, senhas nem valores fiscais. }

interface

uses
  System.SysUtils;

type
  TRegistroLog = record
    DataHora, Usuario, Maquina, Acao, Chave, Sha256, Filial, Resultado, Detalhe: string;
  end;

procedure RegistrarOperacao(const PastaBase, Acao, Chave, Sha256, Filial,
  Resultado, Detalhe: string);
function LerHistorico(const PastaBase: string; MaxRegistros: Integer = 500): TArray<TRegistroLog>;

implementation

uses
  System.Classes, System.IOUtils, System.JSON, System.DateUtils, System.Types,
  System.Generics.Collections, uTipos;

function PastaLogs(const PastaBase: string): string;
begin
  Result := TPath.Combine(PastaBase, 'logs');
end;

procedure RegistrarOperacao(const PastaBase, Acao, Chave, Sha256, Filial,
  Resultado, Detalhe: string);
var
  J: TJSONObject;
  Linha: TBytes;
  F: TFileStream;
  Arq: string;
begin
  try
    TDirectory.CreateDirectory(PastaLogs(PastaBase));
    Arq := TPath.Combine(PastaLogs(PastaBase), FormatDateTime('yyyy-mm-dd', Now) + '.jsonl');
    J := TJSONObject.Create;
    try
      J.AddPair('dataHora', DateToISO8601(Now, False));
      J.AddPair('usuario', GetEnvironmentVariable('USERNAME'));
      J.AddPair('maquina', GetEnvironmentVariable('COMPUTERNAME'));
      J.AddPair('versao', VERSAO_APP);
      J.AddPair('regra', VERSAO_REGRA);
      J.AddPair('acao', Acao);
      J.AddPair('chave', Chave);
      J.AddPair('sha256', Sha256);
      J.AddPair('filial', Filial);
      J.AddPair('resultado', Resultado);
      J.AddPair('detalhe', Detalhe);
      Linha := TEncoding.UTF8.GetBytes(J.ToJSON + #10);
    finally
      J.Free;
    end;
    if TFile.Exists(Arq) then
      F := TFileStream.Create(Arq, fmOpenReadWrite or fmShareDenyWrite)
    else
      F := TFileStream.Create(Arq, fmCreate or fmShareDenyWrite);
    try
      F.Seek(0, soEnd);
      F.WriteBuffer(Linha[0], Length(Linha));
    finally
      F.Free;
    end;
  except
    // A tela captura e mostra no rodape; a operacao em si nao e desfeita.
    on E: Exception do
      raise Exception.Create('Não foi possível gravar o log de operações: ' + E.Message);
  end;
end;

function Campo(J: TJSONObject; const Nome: string): string;
var
  V: TJSONValue;
begin
  V := J.GetValue(Nome);
  if V = nil then
    Result := ''
  else
    Result := V.Value;
end;

function LerHistorico(const PastaBase: string; MaxRegistros: Integer): TArray<TRegistroLog>;
var
  Arquivos: TStringDynArray;
  I, K: Integer;
  Linhas: TArray<string>;
  V: TJSONValue;
  R: TRegistroLog;
begin
  Result := nil;
  if not TDirectory.Exists(PastaLogs(PastaBase)) then
    Exit;
  Arquivos := TDirectory.GetFiles(PastaLogs(PastaBase), '*.jsonl');
  TArray.Sort<string>(Arquivos);
  // Do mais recente para o mais antigo.
  for I := High(Arquivos) downto 0 do
  begin
    Linhas := TFile.ReadAllLines(Arquivos[I], TEncoding.UTF8);
    for K := High(Linhas) downto 0 do
    begin
      if Trim(Linhas[K]) = '' then
        Continue;
      V := TJSONObject.ParseJSONValue(Linhas[K]);
      try
        if V is TJSONObject then
        begin
          R.DataHora := Campo(TJSONObject(V), 'dataHora');
          R.Usuario := Campo(TJSONObject(V), 'usuario');
          R.Maquina := Campo(TJSONObject(V), 'maquina');
          R.Acao := Campo(TJSONObject(V), 'acao');
          R.Chave := Campo(TJSONObject(V), 'chave');
          R.Sha256 := Campo(TJSONObject(V), 'sha256');
          R.Filial := Campo(TJSONObject(V), 'filial');
          R.Resultado := Campo(TJSONObject(V), 'resultado');
          R.Detalhe := Campo(TJSONObject(V), 'detalhe');
          SetLength(Result, Length(Result) + 1);
          Result[High(Result)] := R;
          if Length(Result) >= MaxRegistros then
            Exit;
        end;
      finally
        V.Free;
      end;
    end;
  end;
end;

end.
