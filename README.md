# JARVIS AI

Assistente pessoal para desktop, desenvolvido para o projeto JARVIS AI de Matheus Moreira. Os recursos entram gradualmente e só serão anunciados como disponíveis quando estiverem implementados.

## Requisitos

- Python 3.11 ou superior
- Windows 10/11 (suporte a macOS e Linux planejado)
- Chave Gemini para conversa e raciocínio
- Chave Groq opcional para transcrição Whisper

## Desenvolvimento

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m jarvis
```

O e-mail e telefone são opcionais e permanecem no armazenamento local. As chaves de API são salvas pelo gerenciador de credenciais do sistema operacional; não coloque credenciais em arquivos versionados.

## Estado

Este branch inicia uma reconstrução limpa. A primeira etapa cobre a estrutura independente, interface inicial, configuração local e memória. Controle do computador, visão de tela, integrações de mensagens, e-mail, chamadas, música e gesto por palmas exigem implementações separadas e não estão ativos nesta etapa.

## Contato

Instagram: [@mthz.mm](https://www.instagram.com/mthz.mm/)
