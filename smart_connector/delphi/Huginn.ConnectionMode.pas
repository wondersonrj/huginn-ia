unit Huginn.ConnectionMode;

interface

type
  THuginnConnectionMode = (cmFireDACLocal, cmHuginnCloud);
  // Adapter seam only: original local datamodules/queries/licensing remain with the caller.
  IResumoGerencialSource = interface
    ['{C72D422A-FADF-4C4E-9214-667538B083F2}']
    procedure OpenModule(const Module: string);
  end;

function SelectSource(Mode: THuginnConnectionMode;
  const LocalSource, CloudSource: IResumoGerencialSource): IResumoGerencialSource;

implementation

uses System.SysUtils;

function SelectSource(Mode: THuginnConnectionMode;
  const LocalSource, CloudSource: IResumoGerencialSource): IResumoGerencialSource;
begin
  case Mode of
    cmFireDACLocal: Result := LocalSource;
    cmHuginnCloud: Result := CloudSource;
  else
    raise Exception.Create('Selecione explicitamente o modo de conexao.');
  end;
  if Result = nil then raise Exception.Create('Fonte de dados nao configurada.');
  // No catch, automatic fallback, FireDAC initialization or global mode mutation.
end;

end.
