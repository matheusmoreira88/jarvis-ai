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

## Recursos nesta versão

- Interface desktop original em PySide6 e conversa por texto com Gemini.
- Memória conversacional local em SQLite.
- Chaves Gemini/Groq e contatos opcionais guardados no cofre de credenciais do sistema.
- Gravação pontual de até 15 segundos, transcrição Groq/Whisper e resposta por voz local. O microfone não fica aberto em segundo plano.
- Captura e análise da tela somente ao clicar no botão correspondente.
- Abertura de três aplicativos permitidos, sempre após confirmação.
- Reprodução de arquivos e URLs de áudio/vídeo em um player que pode ser recolhido.
- Download de áudio por URL para uma pasta escolhida, após confirmação.
- Opção para abrir minimizado junto com o login do Windows ou Linux.
- Envio de e-mail Gmail por OAuth de desktop, usando escopo limitado a envio e confirmação do destinatário/conteúdo antes de cada envio.

WhatsApp dentro do HUD, lista de contatos autorizados, atendimento de chamadas e ativação por duas palmas ainda não estão implementados. O e-mail e o telefone cadastrados são apenas dados locais; eles não concedem acesso aos serviços. O Gmail requer ativar a Gmail API num projeto Google Cloud e importar um OAuth Client ID do tipo desktop; o usuário autoriza a conta no navegador na primeira utilização.

## Privacidade e controle

As capturas de tela são enviadas ao Gemini apenas após ação explícita do usuário. O microfone grava uma amostra limitada a 15 segundos após o clique, transcreve pelo Groq e fecha a gravação. Abrir aplicativos requer confirmação. Para análise da tela ou transcrição, o conteúdo correspondente é enviado ao provedor configurado.

## Contato

Instagram: [@mthz.mm](https://www.instagram.com/mthz.mm/)
