# Evidências visuais — issue #29

Imagens 1440×1000 (página completa) e mobile 390×844, Chromium/Linux,
versão 0.4.0. Antes: frontend da main pós-#28. Depois: build real do redesign,
API demo, XML sintético e fixture vazia de perfis Windows para mostrar o formulário.
Sem cliente, conexão Oracle real, host, usuário ou segredo real. O token de demo
aparece mascarado apenas no modo legado; Windows instalado usa cookie automático.
Bird é o ícone preexistente, sem outro arquivo de marca oficial disponível.

| Tela | Imagem |
| --- | --- |
| Antes (fluxos na mesma tela) | [antes](antes.png) |
| Dashboard | [Visão geral](visao-geral.png) |
| Produtos demo | [Produtos](produtos.png) |
| Fornecedores demo | [Fornecedores](fornecedores.png) |
| XML sintético | [NF-e](nfe.png) |
| Central única | [Configurações](configuracoes.png) |
| Catálogo e evidências | [Funcionalidades e Validação](validacao.png) |
| Schema demo e manutenção | [Suporte](suporte.png) |
| Responsividade | [Mobile](mobile.png) |

Reprodução: `packaging/windows/ui_snapshots.py`, instruções no
[guia técnico](../../INTERFACE_EMPRESARIAL.md). O workflow Windows portable inclui
snapshots do mesmo fluxo no artifact; não confundir com homologação Oracle real.
