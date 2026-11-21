unit uRegistro;

{ HUGINN XML Automatico - guarda local dos XMLs recebidos e liberacao do original.

  - Recebidos\<chave>\<sha256>.xml : copia byte a byte de cada versao recebida.
    Mesma chave + mesmo hash = idempotente. Mesma chave + hash diferente = conflito,
    sinalizado para revisao (nada e substituido).
  - Liberacao: grava o XML ORIGINAL na pasta de liberados e confere o SHA-256
    lendo o arquivo gravado de volta. Nada e reserializado. }

interface

uses
  System.SysUtils;

type
  TStatusRecebido = (rgNovo, rgMesmoArquivo, rgConflito);

  TResultadoRecebido = record
    Status: TStatusRecebido;
    Caminho: string;
    OutrosHashes: TArray<string>;   // versoes diferentes ja recebidas com a mesma chave
  end;

function RegistrarRecebido(const PastaBase, Chave, Sha256: string;
  const Bytes: TBytes): TResultadoRecebido;
function LiberarOriginal(const PastaDestino, Chave, Sha256: string;
  const Bytes: TBytes): string;
function NomeArquivoLiberado(const Chave: string): string;

implementation

uses
  System.IOUtils, System.Classes, uValidacao, uXmlNFe;

procedure ExigirChave(const Chave: string);
begin
  // A chave vira nome de pasta: so aceita os 44 digitos validados.
  if not ChaveNFeValida(Chave) then
    raise Exception.Create('Chave de acesso inválida para registro.');
end;

procedure GravarExclusivo(const Arquivo: string; const Bytes: TBytes);
var
  F: TFileStream;
begin
  F := TFileStream.Create(Arquivo, fmCreate or fmShareExclusive);
  try
    if Length(Bytes) > 0 then
      F.WriteBuffer(Bytes[0], Length(Bytes));
  finally
    F.Free;
  end;
end;

function RegistrarRecebido(const PastaBase, Chave, Sha256: string;
  const Bytes: TBytes): TResultadoRecebido;
var
  Pasta, Arq, Nome: string;
begin
  ExigirChave(Chave);
  Result := Default(TResultadoRecebido);
  Pasta := TPath.Combine(TPath.Combine(PastaBase, 'Recebidos'), Chave);
  TDirectory.CreateDirectory(Pasta);
  Arq := TPath.Combine(Pasta, Sha256 + '.xml');
  for Nome in TDirectory.GetFiles(Pasta, '*.xml') do
    if not SameText(TPath.GetFileNameWithoutExtension(Nome), Sha256) then
    begin
      SetLength(Result.OutrosHashes, Length(Result.OutrosHashes) + 1);
      Result.OutrosHashes[High(Result.OutrosHashes)] := TPath.GetFileNameWithoutExtension(Nome);
    end;
  Result.Caminho := Arq;
  if TFile.Exists(Arq) then
    Result.Status := rgMesmoArquivo
  else
  begin
    GravarExclusivo(Arq, Bytes);
    Result.Status := rgNovo;
  end;
  if Length(Result.OutrosHashes) > 0 then
    Result.Status := rgConflito;
end;

function NomeArquivoLiberado(const Chave: string): string;
begin
  Result := Chave + '-procNFe.xml';
end;

function LiberarOriginal(const PastaDestino, Chave, Sha256: string;
  const Bytes: TBytes): string;
var
  Lido: TBytes;
begin
  ExigirChave(Chave);
  if Sha256Hex(Bytes) <> Sha256 then
    raise Exception.Create('O conteúdo em memória não confere com o hash recebido. Abra o XML novamente.');
  TDirectory.CreateDirectory(PastaDestino);
  Result := TPath.Combine(PastaDestino, NomeArquivoLiberado(Chave));
  if TFile.Exists(Result) then
  begin
    if Sha256Hex(TFile.ReadAllBytes(Result)) = Sha256 then
      Exit;  // ja liberado, identico: idempotente
    raise Exception.Create('Já existe um XML liberado com esta chave e conteúdo DIFERENTE: ' + Result +
      '. Revise antes de substituir (nada foi alterado).');
  end;
  GravarExclusivo(Result, Bytes);
  Lido := TFile.ReadAllBytes(Result);
  if Sha256Hex(Lido) <> Sha256 then
    raise Exception.Create('Falha de integridade: o arquivo gravado não tem o mesmo SHA-256 do recebido.');
end;

end.
