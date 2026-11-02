# JARVIS AI 0.7.1

## Português (Brasil)

Esta atualização corrige o JARVIS que permanecia em **Processando** sem responder.

- Conversa, transcrição e análise da tela agora usam o Gemini 3.5 Flash-Lite, otimizado para baixa latência.
- Teste real neste computador: resposta completa iniciada e concluída em aproximadamente 1,5 segundo.
- Somente propostas de código continuam usando Gemini 3.8 Flash; a visão ao vivo mantém o modelo Gemini Live.
- “Oi”, “olá” e “alô, Jarvis” recebem resposta local instantânea, mesmo sem internet.
- O Gemini usa raciocínio baixo para começar a transmitir texto mais cedo.
- O histórico enviado caiu para 13 mensagens no texto e 7 na voz; o histórico completo continua salvo no SQLite.
- Uma chamada que não responder em 15 segundos libera o HUD e mostra uma mensagem clara em português.
- A instrução de identidade foi separada do adaptador de rede, corrigindo `SYSTEM_INSTRUCTION is not defined`.
- O fluxo foi validado com 26 testes automatizados e uma chamada real à Gemini.

O instalador não possui certificado comercial de assinatura de código. O Windows SmartScreen pode mostrar fornecedor desconhecido; baixe somente desta release oficial e confira o arquivo SHA-256 publicado.

Copyright (c) 2026 Matheus Moreira. Código sob licença MIT. Modelos, APIs e serviços de terceiros mantêm suas próprias licenças e termos.

## English

This update fixes JARVIS remaining stuck in **Processing** without answering.

- Chat, transcription, and screen analysis now use Gemini 3.5 Flash-Lite, optimized for low latency.
- Live test on this computer: the complete reply started and finished in approximately 1.5 seconds.
- Only code proposals remain on Gemini 3.8 Flash; live vision keeps the Gemini Live model.
- “Oi”, “olá”, and “alô, Jarvis” receive an instant local reply, even without internet.
- Gemini uses low reasoning so streamed text begins sooner.
- Sent history is reduced to 13 text messages and 7 voice messages; the full history remains stored in SQLite.
- A request that does not answer within 15 seconds releases the HUD and shows a clear Portuguese error.
- The identity instruction is separated from the network adapter, fixing `SYSTEM_INSTRUCTION is not defined`.
- The flow was validated with 26 automated tests and a live Gemini request.

The installer does not have a commercial code-signing certificate. Windows SmartScreen may show an unknown publisher; download only from this official release and verify the published SHA-256 file.

Copyright (c) 2026 Matheus Moreira. Licensed under MIT. Third-party models, APIs, and services retain their own licenses and terms.
