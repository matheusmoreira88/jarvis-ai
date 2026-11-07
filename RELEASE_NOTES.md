# JARVIS AI 0.9.0

## Português (Brasil)

Esta versão deixa o JARVIS mais simples de usar, mais rápido ao abrir e mais coerente com o menu público.

- A detecção por palmas foi removida completamente do código, configurações, diagnóstico e documentação.
- A aba **Mídia** saiu do menu principal. Ao pedir uma música ou abrir o player, o YouTube aparece em uma janela flutuante ajustável.
- Qt Multimedia e o player são inicializados somente no primeiro pedido de mídia, reduzindo o trabalho durante a abertura normal.
- As vozes instaladas no Windows são carregadas em segundo plano. A escolha continua salva e a voz automática em português permanece como fallback.
- Os controles usam estados simples: **Voz**, **Visão** e **Controle do computador** ativados ou desativados.
- O perfil **Restrito** agora bloqueia também comandos de voz em nuvem, além de tela, memória compartilhada e controle do computador.
- A visão contínua cancela sua tarefa assíncrona imediatamente ao desligar ou encerrar o aplicativo.
- A ferramenta de autoalteração do código aparece apenas em uma cópia de desenvolvimento iniciada com `JARVIS_DEVELOPER_MODE=1`.
- Configurações antigas de provedor foram removidas; a versão permanece integrada exclusivamente à Gemini.
- A suíte agora possui 40 testes automatizados, além do smoke test do executável empacotado.

O instalador não possui certificado comercial de assinatura de código. O Windows SmartScreen pode mostrar fornecedor desconhecido; baixe somente desta release oficial e confira o arquivo SHA-256 publicado.

Copyright (c) 2026 Matheus Moreira. Código sob licença MIT. Modelos, APIs e serviços de terceiros mantêm suas próprias licenças e termos.

## English

This release makes JARVIS simpler to use, faster to open, and consistent with its public menu.

- Clap detection has been completely removed from code, settings, diagnostics, and documentation.
- The **Media** tab has been removed from the main menu. Music and YouTube open in a resizable floating player when requested.
- Qt Multimedia and the player initialize only on the first media request, reducing normal startup work.
- Installed Windows voices load in the background. The selected voice remains saved, with automatic Portuguese selection as fallback.
- Controls use simple enabled/disabled states for **Voice**, **Vision**, and **Computer control**.
- **Restricted** mode now blocks cloud voice commands as well as screen frames, shared memories, and computer control.
- Continuous vision immediately cancels its asynchronous task when disabled or during shutdown.
- Source self-modification appears only in a development checkout started with `JARVIS_DEVELOPER_MODE=1`.
- Legacy provider settings are removed; this version remains Gemini-only.
- The suite now contains 40 automated tests plus the packaged executable smoke test.

The installer does not have a commercial code-signing certificate. Windows SmartScreen may show an unknown publisher; download only from this official release and verify the published SHA-256 file.

Copyright (c) 2026 Matheus Moreira. Licensed under MIT. Third-party models, APIs, and services retain their own licenses and terms.
