unit uValidacao;

{ HUGINN XML Automatico - validacoes puras (sem banco, sem tela). }

interface

function SoDigitos(const S: string): string;
function CNPJValido(const S: string): Boolean;
function GTINValido(const S: string): Boolean;
function GTINInformado(const S: string): Boolean;   // nao vazio e diferente de "SEM GTIN"
function DVChaveNFe(const Chave43: string): Char;
function ChaveNFeValida(const Chave: string): Boolean;
function MesmaUnidade(const A, B: string): Boolean;

implementation

uses
  System.SysUtils;

function SoDigitos(const S: string): string;
var
  C: Char;
begin
  Result := '';
  for C in S do
    if CharInSet(C, ['0'..'9']) then
      Result := Result + C;
end;

function CNPJValido(const S: string): Boolean;

  function Digito(const Base: string; const Pesos: array of Integer): Integer;
  var
    I, Soma, Resto: Integer;
  begin
    Soma := 0;
    for I := 0 to High(Pesos) do
      Inc(Soma, (Ord(Base[I + 1]) - Ord('0')) * Pesos[I]);
    Resto := Soma mod 11;
    if Resto < 2 then
      Result := 0
    else
      Result := 11 - Resto;
  end;

var
  D: string;
  I: Integer;
  TodosIguais: Boolean;
begin
  D := SoDigitos(S);
  Result := False;
  if Length(D) <> 14 then
    Exit;
  TodosIguais := True;
  for I := 2 to 14 do
    if D[I] <> D[1] then
    begin
      TodosIguais := False;
      Break;
    end;
  if TodosIguais then
    Exit;
  Result :=
    (Digito(D, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) = Ord(D[13]) - Ord('0')) and
    (Digito(D, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]) = Ord(D[14]) - Ord('0'));
end;

function GTINInformado(const S: string): Boolean;
var
  T: string;
begin
  T := UpperCase(Trim(S));
  Result := (T <> '') and (T <> 'SEM GTIN');
end;

function GTINValido(const S: string): Boolean;
var
  T: string;
  I, Soma, Peso, N: Integer;
begin
  Result := False;
  T := Trim(S);
  N := Length(T);
  if not (N in [8, 12, 13, 14]) then
    Exit;
  if SoDigitos(T) <> T then
    Exit;
  // Da direita para a esquerda, sem o digito verificador: pesos 3,1,3,1...
  Soma := 0;
  Peso := 3;
  for I := N - 1 downto 1 do
  begin
    Inc(Soma, (Ord(T[I]) - Ord('0')) * Peso);
    if Peso = 3 then
      Peso := 1
    else
      Peso := 3;
  end;
  Result := ((10 - (Soma mod 10)) mod 10) = (Ord(T[N]) - Ord('0'));
end;

function DVChaveNFe(const Chave43: string): Char;
var
  I, Soma, Peso, Resto: Integer;
begin
  Soma := 0;
  Peso := 2;
  for I := Length(Chave43) downto 1 do
  begin
    Inc(Soma, (Ord(Chave43[I]) - Ord('0')) * Peso);
    Inc(Peso);
    if Peso > 9 then
      Peso := 2;
  end;
  Resto := Soma mod 11;
  if Resto < 2 then
    Result := '0'
  else
    Result := Char(Ord('0') + 11 - Resto);
end;

function ChaveNFeValida(const Chave: string): Boolean;
begin
  Result := (Length(Chave) = 44) and (SoDigitos(Chave) = Chave) and
    (DVChaveNFe(Copy(Chave, 1, 43)) = Chave[44]);
end;

function MesmaUnidade(const A, B: string): Boolean;
begin
  Result := SameText(Trim(A), Trim(B));
end;

end.
