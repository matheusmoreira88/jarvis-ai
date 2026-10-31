# JARVIS AI

Assistente pessoal para desktop em português, criado por **Matheus Moreira**. Este projeto é uma implementação independente, com interface própria em PySide6, memória local e integrações opcionais. O JARVIS pede confirmação antes de abrir aplicativos, enviar e-mail ou preparar mensagens.

Instagram do criador: [@mthz.mm](https://www.instagram.com/mthz.mm/)<br>
Contato: [matheusmoreiradossantos88@gmail.com](mailto:matheusmoreiradossantos88@gmail.com)

Se o projeto for útil, [deixe uma estrela no GitHub](https://github.com/matheusmoreira88/jarvis-ai) e compartilhe sugestões ou problemas pela área de Issues.

## Recursos disponíveis

- Conversa por texto com Gemini ou Groq, selecionável nas configurações, além da opção de pesquisa na web com Gemini e fontes retornadas pela busca.
- Histórico local em SQLite para contexto entre sessões.
- Comando por voz sob demanda: grava até 15 segundos, transcreve com Groq/Whisper e responde com voz sintetizada localmente.
- Análise da tela por captura explícita ou observação contínua opcional a cada 10 segundos. A observação contínua pede consentimento, envia as capturas ao Gemini e pode consumir cota da API.
- Abertura confirmada de aplicativos incluídos numa lista fixa (Bloco de Notas, Calculadora e Explorador de Arquivos).
- Player de áudio e vídeo para arquivos locais e URLs, com controles recolhíveis; download de áudio por URL para uma pasta escolhida.
- Integração Gmail por OAuth de desktop, com permissão limitada a enviar mensagens e confirmação antes de cada envio.
- WhatsApp Web em uma janela incorporada, contatos permitidos armazenados localmente e mensagens preparadas para revisão. O usuário precisa conferir e clicar em **Enviar** no próprio WhatsApp.
- Opção para iniciar minimizado com o login do Windows ou Linux e permanecer na bandeja até ser encerrado no menu.
- Atalho opcional de duas palmas para alternar tela cheia. A detecção é local, requer ativação expressa e mantém o microfone aberto enquanto estiver ligada.

## Requisitos

- Windows 10/11 (o código de início automático também oferece Linux; macOS ainda não foi implementado).
- Python 3.11 ou superior: [baixar Python](https://www.python.org/downloads/). No Windows, marque **Add Python to PATH** durante a instalação.
- Microfone e saída de áudio para os recursos de voz.
- Chave de API Gemini: [Google AI Studio](https://aistudio.google.com/app/api-keys).
- Chave Groq: [Groq Console](https://console.groq.com/keys). Groq pode ser usado para conversa e é necessário para transcrever voz.

O uso das APIs depende dos limites, disponibilidade, termos e eventual cobrança definidos por cada provedor. Consulte os respectivos painéis antes de habilitar faturamento.

## Instalação no Windows

Abra PowerShell na pasta do projeto e execute:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m jarvis
```

Se o PowerShell bloquear a ativação do ambiente virtual, rode o JARVIS sem ativá-lo:

```powershell
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m jarvis
```

Na primeira abertura, informe ao menos a chave do provedor escolhido. Chaves e credenciais são guardadas no cofre do sistema operacional, não em arquivos do repositório. Para trocar as chaves depois, abra **Configurações**.

### Início automático

Na interface, clique **Ativar início automático** e confirme. O aplicativo registra uma inicialização por usuário e abre minimizado no próximo login. Fechar a janela mantém o JARVIS na bandeja do sistema; use **Encerrar** no menu do ícone para sair. Para remover o início automático, clique **Desativar início automático**.

## Configurar as integrações

### Gemini e Groq

1. Crie uma chave Gemini no [Google AI Studio](https://aistudio.google.com/app/api-keys) e/ou uma chave Groq em [Groq Console](https://console.groq.com/keys).
2. Insira as chaves na janela inicial ou em **Configurações**.
3. Escolha Gemini ou Groq como provedor de conversa. Marque **Pesquisar na web com Gemini nesta solicitação** para obter respostas fundamentadas na pesquisa Google. A pesquisa pode consumir cota adicional conforme as regras do provedor. A análise de imagem usa Gemini; a transcrição de voz usa Groq/Whisper.

### Gmail

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e habilite a Gmail API.
2. Configure a tela de consentimento OAuth e crie um OAuth Client ID do tipo **Aplicativo para computador**.
3. Baixe o JSON desse cliente e, no JARVIS, clique **Configurar Gmail OAuth…** para importá-lo.
4. Ao enviar o primeiro e-mail, o navegador abrirá a autorização Google. Confira o destinatário e o conteúdo na confirmação do aplicativo antes de cada envio.

A integração solicita somente a permissão de envio (`gmail.send`). Ela não lê a caixa de entrada nem atende chamadas.

### WhatsApp

1. Abra **Contatos permitidos…** e cadastre nome e telefone no formato internacional, incluindo DDI (por exemplo, `5521999999999`).
2. Clique **Preparar mensagem WhatsApp…**, selecione um contato autorizado e escreva o texto.
3. Confirme a revisão; o WhatsApp Web abre no HUD. Entre na sua conta, confira a conversa e pressione **Enviar** manualmente.

O aplicativo não lê mensagens, não envia sem a ação final do usuário e não atende chamadas do WhatsApp. Chamadas pessoais não são disponibilizadas por uma integração genérica para este aplicativo; atender chamadas deve ser feito nos controles oficiais do WhatsApp. A janela incorporada depende de o WhatsApp Web aceitar o navegador Qt WebEngine instalado no computador.

## Privacidade e segurança

- Gemini/Groq recebem apenas as solicitações encaminhadas a eles: prompts, capturas de tela sob demanda ou contínuas depois do consentimento, e áudio gravado para transcrição.
- Detecção de palmas não grava nem transmite áudio; ela analisa os blocos de microfone localmente enquanto ativada.
- Chaves de API e lista de contatos ficam no cofre de credenciais do usuário. Tokens OAuth e configurações ficam nas pastas privadas de dados do aplicativo, fora do repositório.
- E-mails exigem confirmação explícita antes do envio. Mensagens WhatsApp são apenas preparadas; o envio final é manual.
- Ações locais são restritas a uma lista fixa e pedem confirmação. O JARVIS não executa comandos arbitrários do modelo.
- Não compartilhe arquivos de credencial OAuth, tokens ou chaves. Se uma chave for publicada por engano, revogue-a no painel do provedor.

## Limitações conhecidas

O controle do computador está limitado à lista de aplicativos acima. A visão contínua usa intervalos de 10 segundos e não equivale a vídeo ao vivo. Chamadas telefônicas ou do WhatsApp não são atendidas pelo JARVIS. A qualidade de mídia por URL depende do formato e do suporte do Qt Multimedia; downloads devem respeitar direitos autorais e termos do site. O projeto ainda não é um assistente autônomo que altera seu próprio código.

## Desenvolvimento

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m jarvis
```

Contribuições são bem-vindas por Issues e Pull Requests. Antes de publicar mudanças, confira que nenhum segredo, token ou dado pessoal foi incluído.
