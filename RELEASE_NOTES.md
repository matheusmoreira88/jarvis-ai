# JARVIS AI 0.8.0

## Português (Brasil)

Esta versão concentra estabilidade, privacidade e diagnóstico, mantendo o HUD e as funcionalidades existentes.

- Estados centralizados para escuta, transcrição, processamento, fala, observação e erro.
- Visão contínua silenciosa, sem áudio automático e com redução de quadros repetidos enviados à Gemini Live.
- Perfis de privacidade **Equilibrado**, **Restrito** e **Integrado**. O perfil Restrito bloqueia visão contínua, controle do computador e compartilhamento de lembranças com a IA.
- Cancelamento mais rápido de respostas e TTS, além de encerramento seguro pelo modo pânico ou fechamento do aplicativo.
- Logs locais rotativos com remoção de formatos comuns de credenciais.
- Diagnóstico offline de áudio, captura de tela, filtro local de voz, SDK Gemini e configuração da chave.
- Auditoria local de ações guarda somente categoria, resultado e horário; comandos, caminhos e textos digitados não são registrados.
- Índice de busca da memória permanece sincronizado após atualizações e backups SQLite acima de 512 MB são rejeitados.
- O pipeline do GitHub agora executa um smoke test no aplicativo já empacotado antes de criar o instalador.
- Suíte ampliada para 38 testes automatizados.

O instalador não possui certificado comercial de assinatura de código. O Windows SmartScreen pode mostrar fornecedor desconhecido; baixe somente desta release oficial e confira o arquivo SHA-256 publicado.

Copyright (c) 2026 Matheus Moreira. Código sob licença MIT. Modelos, APIs e serviços de terceiros mantêm suas próprias licenças e termos.

## English

This release focuses on stability, privacy, and diagnostics while preserving the existing HUD and feature set.

- Centralized lifecycle states for listening, transcription, thinking, speaking, observation, and errors.
- Silent continuous vision with no automatic audio and fewer repeated frames sent to Gemini Live.
- **Balanced**, **Restricted**, and **Connected** privacy profiles. Restricted blocks continuous vision, computer control, and sharing saved memories with AI.
- Faster reply and TTS cancellation, plus safer panic-mode and application shutdown behavior.
- Local rotating logs that redact common credential formats.
- Offline diagnostics for audio, screen capture, local voice filtering, the Gemini SDK, and key configuration.
- Local action auditing stores only category, outcome, and time; commands, paths, and typed text are not recorded.
- Memory search stays synchronized after updates, and SQLite backups larger than 512 MB are rejected.
- The GitHub pipeline now smoke-tests the packaged application before creating the installer.
- The automated suite now contains 38 tests.

The installer does not have a commercial code-signing certificate. Windows SmartScreen may show an unknown publisher; download only from this official release and verify the published SHA-256 file.

Copyright (c) 2026 Matheus Moreira. Licensed under MIT. Third-party models, APIs, and services retain their own licenses and terms.
