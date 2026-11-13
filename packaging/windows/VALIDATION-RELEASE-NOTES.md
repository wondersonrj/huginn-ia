VALIDAÇÃO ISOLADA — NÃO DISTRIBUIR PARA CLIENTES

Pacote Windows x64 para validar uma atualização real do GitHub Releases.
Canal teste, chave efêmera exclusiva deste workflow, bootstrap DESATIVADO.
A chave privada é destruída no runner e não está em artefatos/repositório.
A versão 0.0.x é inferior aos pacotes de clientes 0.2.0 e não é candidata a
atualização para esses clientes. Nenhuma instalação existente é modificada.

A assinatura Ed25519 do manifesto cobre a versão/canal/URL/hash SHA256.
Não é assinatura Authenticode de executáveis. Não há conexão Oracle nos testes.
O resultado Windows está no workflow Real GitHub release validation; antes
que o relatório real-release-proof.json esteja anexado, a validação está pendente.
