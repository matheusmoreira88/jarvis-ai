# JARVIS AI

[Português (Brasil)](#português-brasil) | [English](#english)

**Antes de baixar / Before download:** leia [Informações de privacidade / Privacy information](PRIVACY.txt). O instalador também mostra esse texto antes de instalar. / The installer also displays it before installation.

## Português (Brasil)

Assistente pessoal para desktop em português, criado por **Matheus Moreira**. Este projeto é uma implementação independente, com interface própria em PySide6, memória local e integrações opcionais. O JARVIS pede confirmação antes de executar ações no computador, enviar e-mail ou preparar mensagens.

Instagram do criador: [@mthz.mm](https://www.instagram.com/mthz.mm/)<br>
Contato: [matheusmoreiradossantos88@gmail.com](mailto:matheusmoreiradossantos88@gmail.com)

Se o projeto for útil, [deixe uma estrela no GitHub](https://github.com/matheusmoreira88/jarvis-ai).

Licença: [MIT](license).
Direitos autorais: **Copyright (c) 2026 Matheus Moreira**. Modelos e serviços de terceiros mantêm suas próprias licenças e termos.

### Recursos

- Conversa por texto com Gemini ou Groq, selecionável nas configurações, e pesquisa na web com Gemini com fontes retornadas pela busca.
- Os dois provedores recebem instruções para reconhecer Matheus Moreira como criador, responder em português e não alegar ações que o aplicativo não executou.
- Uma conversa única, sem sessões separadas. Histórico, lembranças permanentes e lembretes ficam no SQLite local. A busca indexada recupera lembranças antigas; a biblioteca fica em Configurações. Em Configurações também é possível impedir que lembranças entrem no contexto enviado ao provedor.
- Comandos de voz mãos livres com um único modo: diga **Jarvis**. O filtro local evita enviar ruídos comuns à Groq; na primeira ativação baixa um modelo de português de cerca de 31 MB. A gravação termina após uma pausa, sem botão. Respostas aparecem no centro da interface e na conversa, com fala local por frases.
- Comandos por voz ou texto para abrir aplicativos instalados sem uma confirmação extra depois do pedido explícito. Digitar texto, pressionar teclas, clicar e rolar continuam exigindo confirmação. O comando `agir: pedido` envia uma captura ao Gemini, que pode propor uma única ação; a pessoa revisa e confirma antes da execução.
- Análise por captura explícita ou visão contínua ativada nas configurações: o HUD mostra uma prévia local fluida da tela (cerca de 10 atualizações/s) enquanto a Gemini Live recebe até 1 imagem/s, limite documentado da API. As observações aparecem no histórico. O envio à nuvem pode consumir cota; a visão pode ser desligada a qualquer momento.
- Busca por nome entre os aplicativos disponíveis no menu Iniciar e os programas clássicos registrados no Windows; um pedido explícito abre o app sem uma confirmação extra. Também permite escolher manualmente um arquivo `.exe`.
- Player no HUD para arquivos locais e URLs, além do YouTube incorporado: cole uma URL ou pesquise o nome de uma música, escolha um resultado e reproduza na página oficial sem baixar a faixa. Favoritos e fila ficam salvos localmente; a próxima entrada da fila pode ser aberta por botão ou comando de voz. O painel pode ser recolhido enquanto o áudio toca. Baixar áudio por URL é uma opção separada que pede confirmação.
- Rotinas configuráveis de até oito comandos locais de aplicativos, navegação e música. Lembretes podem repetir diariamente, semanalmente, mensalmente ou anualmente; diga, por exemplo, `me lembra de revisar todo dia às 9`. Um arquivo de calendário `.ics` pode ser importado para criar avisos um dia antes de eventos futuros. A visão pode observar uma tela escolhida nas Configurações; ações visuais usam a tela principal.
- Gmail por OAuth de desktop, com permissão limitada a enviar mensagens e confirmação antes de cada envio.
- WhatsApp Web dentro do HUD, contatos permitidos guardados localmente e mensagens preparadas para revisão. A interface de chamadas do WhatsApp Web pode ser usada no HUD se o serviço e o Qt WebEngine forem compatíveis; o usuário atende e encerra pela própria interface, após permitir o microfone ou a câmera quando solicitado.
- Opção para iniciar minimizado com o login do Windows ou Linux e permanecer na bandeja do sistema. Um bloqueio por usuário evita abrir duas instâncias e disputar microfone ou memória.
- Atalho opcional de duas palmas para alternar a tela cheia. A detecção é local, requer ativação expressa e mantém o microfone aberto enquanto estiver ligada.
- Ferramenta para propor mudanças no próprio código: escolhe um módulo, pede uma proposta ao Gemini, exibe o arquivo para revisão e só grava após duas confirmações. Valida sintaxe, cria backup antes de substituir e permite restaurar uma versão salva pela interface.

### Requisitos

- Windows 10/11. O início automático também oferece suporte a Linux; macOS ainda não foi implementado.
- Para instalar pelo código: Python 3.11 ou superior: [baixar Python](https://www.python.org/downloads/). No Windows, marque **Add Python to PATH** durante a instalação.
- Microfone e saída de áudio para os recursos de voz.
- Chave Gemini: [Google AI Studio](https://aistudio.google.com/app/api-keys).
- Chave Groq: [Groq Console](https://console.groq.com/keys). Groq pode ser usado para conversa e é necessário para transcrição de voz.

O uso das APIs depende dos limites, disponibilidade, termos e eventual cobrança de cada provedor. O Gemini 3.8 Flash oferece uso gratuito dentro da cota indicada pelo Google, mas a pesquisa Google (Search Grounding) não está incluída no nível gratuito. Confira a [página oficial de preços](https://ai.google.dev/gemini-api/docs/pricing) e os painéis antes de usar recursos pagos.

- O Command Center mostra estados atuais de provedor, microfone, visão, mídia e memória; a troca de páginas e o núcleo visual usam animações suaves.
- Peça músicas como toca música [artista ou faixa] ou pesquise no YouTube [termo]; os resultados oficiais abrem dentro do HUD. O vídeo pode ficar numa janela flutuante, em modo compacto ou em tela cheia.

### Instalação fácil no Windows

Baixe `JARVIS-AI-Setup` nos artefatos da execução mais recente de **Build Windows installer** em GitHub → Actions e abra o instalador. Ele instala o JARVIS sem exigir Python no computador. Na primeira execução, cadastre as chaves Gemini/Groq em Configurações.

Para criar o instalador a partir do código, instale Python 3.11+, Inno Setup e execute `build_windows.bat`. O pacote portátil também aparece em `dist/JarvisAI`.

### Instalação pelo código

Instale o Python, abra o PowerShell e execute:

```powershell
git clone https://github.com/matheusmoreira88/jarvis-ai.git
cd jarvis-ai
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m jarvis
```

Se o PowerShell bloquear a ativação do ambiente virtual, rode o aplicativo sem ativá-lo:

```powershell
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m jarvis
```

Na primeira abertura, informe as chaves Gemini e Groq. Elas são guardadas no cofre de credenciais do sistema operacional, não nos arquivos do repositório; nas próximas aberturas não será necessário digitá-las novamente. Para trocá-las, abra **Configurações**.

Os campos opcionais de e-mail e telefone nas configurações são referências privadas deste computador, guardadas no cofre do sistema. O aplicativo não os envia aos provedores. A conta que envia e-mails é a conta autorizada pela janela OAuth do Gmail.

### Controlar aplicativos

Use comandos por texto ou voz como `abrir calculadora`, `abrir aplicativo: nome do app`, `abrir exe: C:\caminho\aplicativo.exe`, `digitar: texto que desejo colar`, `pressionar: enter`, `clicar` ou `rolar: baixo`. Quando você pedir para abrir um app, ele abre sem uma confirmação extra. A lista completa fica em **Configurações**. Digitar, pressionar uma tecla, clicar ou rolar ainda pede confirmação. Posicione o cursor no destino antes de confirmar o clique. O texto digitado e o caminho local do `.exe` ficam no histórico SQLite, mas são omitidos do contexto enviado ao Gemini/Groq.

Para pedir que o Gemini identifique um controle na tela, use `agir: clique no botão Salvar`. O JARVIS pede autorização para enviar uma captura atual ao Gemini, mostra a ação sugerida e solicita uma segunda confirmação antes de clicar. O modelo só pode propor clique, rolagem curta, uma tecla comum ou nenhuma ação; ele não digita nem executa comandos de sistema.

Para apagar a conversa persistida, clique em **Apagar memória local…** e confirme.

### Início automático e bandeja

Clique em **Ativar início automático** e confirme. O aplicativo abre minimizado no próximo login. Fechar a janela mantém o JARVIS na bandeja; escolha **Encerrar** no menu do ícone para sair. Para remover o início automático, clique em **Desativar início automático**.

### Configurar os serviços em Configurações

#### Gemini e Groq

1. Crie uma chave Gemini no [Google AI Studio](https://aistudio.google.com/app/api-keys) e/ou uma chave Groq em [Groq Console](https://console.groq.com/keys).
2. Insira as chaves na janela inicial ou em **Configurações**.
3. Escolha Gemini ou Groq como provedor de conversa. Marque **Pesquisar na web com Gemini nesta solicitação** para ativar a pesquisa Google. O Search Grounding não está disponível no nível gratuito da Gemini API e pode gerar cobrança no nível pago; confira a página de preços antes de usar. A análise de imagem usa Gemini e a transcrição de voz usa Groq/Whisper.

#### Gmail

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e habilite a Gmail API.
2. Configure a tela de consentimento OAuth e crie um OAuth Client ID do tipo **Aplicativo para computador**.
3. Baixe o JSON desse cliente e clique em **Configurar Gmail OAuth…** no JARVIS para importá-lo.
4. Ao enviar o primeiro e-mail, o navegador abrirá a autorização Google. Confira o destinatário e leia o conteúdo completo na janela rolável de revisão antes de cada envio.

A integração solicita somente a permissão de envio (`gmail.send`). Ela não lê a caixa de entrada nem atende chamadas telefônicas.

#### WhatsApp

1. Abra **Contatos permitidos…** e cadastre nome e telefone no formato internacional, incluindo DDI (por exemplo, `5521999999999`).
2. Clique em **Preparar mensagem WhatsApp…**, selecione um contato autorizado e escreva a mensagem.
3. Leia a mensagem completa na janela rolável e confirme. O WhatsApp Web abre no HUD; entre na sua conta, confira a conversa e pressione **Enviar** manualmente.

O aplicativo não lê mensagens nem envia sem a ação final do usuário. Em uma chamada, use os controles oficiais exibidos no WhatsApp Web. O JARVIS não atende automaticamente. O microfone e a câmera só são liberados depois de uma confirmação para `web.whatsapp.com`, e também dependem das permissões do Windows. Chamadas dentro do HUD dependem da compatibilidade do WhatsApp Web com o Qt WebEngine instalado.

### Privacidade e segurança

- Para conversas por texto ou voz, o provedor escolhido recebe a mensagem atual e até 20 mensagens anteriores da conversa. O áudio gravado é enviado à Groq para transcrição; depois, a transcrição e o contexto recente seguem ao provedor escolhido.
- Capturas pontuais e propostas de ação enviam a imagem e o pedido atual à Gemini após a solicitação; não enviam o histórico da conversa. A visão contínua envia quadros e pedidos de análise à Gemini Live somente enquanto estiver ativa. Capturas não são guardadas no SQLite.
- A detecção de palmas analisa áudio localmente e não grava nem transmite os blocos de microfone.
- Por padrão, até 12 lembranças relevantes ou recentes e até 12 lembretes futuros entram no contexto de conversas por texto ou voz. Desmarque “Incluir lembranças salvas no contexto enviado à IA” nas configurações para mantê-los locais. O SQLite não é criptografado.
- Chaves de API e contatos ficam no cofre de credenciais do usuário. Tokens OAuth e configurações ficam nas pastas privadas de dados do aplicativo, fora do repositório.
- O histórico SQLite permanece no computador e não é criptografado; no Linux/macOS, o JARVIS restringe as permissões dos arquivos e pastas à conta atual. No Windows, usa a pasta de dados do perfil do usuário.
- E-mails exigem confirmação. Mensagens do WhatsApp são preparadas para revisão; o envio final é manual.
- As ações no computador usam uma lista limitada e pedem confirmação. O JARVIS não executa comandos arbitrários gerados pelo modelo.
- Não publique arquivos OAuth, tokens nem chaves. Se uma chave for exposta, revogue-a no painel do provedor.

### Limitações conhecidas

O controle do computador está limitado aos aplicativos que o Windows consegue enumerar e às ações implementadas. Abrir um aplicativo após pedido explícito não pede confirmação extra; ações de clique, rolagem, tecla e digitação ainda pedem. A visão Live transmite quadros individuais (até um por segundo; não vídeo de alta taxa de quadros) e depende da disponibilidade da Gemini Live API; as sessões são renovadas periodicamente. Chamadas não são atendidas automaticamente. A reprodução de arquivos e URLs depende dos formatos suportados pelo Qt Multimedia. Downloads devem respeitar direitos autorais e termos do site. Alterações no próprio código exigem revisão explícita e reinício do aplicativo.

### Desenvolvimento

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m jarvis
```



---

## English

A Portuguese-language desktop assistant created by **Matheus Moreira**. This is an independent implementation with its own PySide6 interface, local memory, and optional integrations. JARVIS asks for confirmation before taking computer actions, sending email, or preparing messages.

Creator's Instagram: [@mthz.mm](https://www.instagram.com/mthz.mm/)<br>
Contact: [matheusmoreiradossantos88@gmail.com](mailto:matheusmoreiradossantos88@gmail.com)

If you find the project useful, [leave a star on GitHub](https://github.com/matheusmoreira88/jarvis-ai).

License: [MIT](license).
Copyright **(c) 2026 Matheus Moreira**. Third-party models and services keep their own licenses and terms.

### Features

- Text chat with Gemini or Groq, selectable in Settings, plus Gemini web search with returned source links.
- Both providers are instructed to recognize Matheus Moreira as the creator, answer in Portuguese, and never claim actions the app did not perform.
- One ongoing conversation, with no separate sessions. Chat history, permanent memories, and reminders stay in local SQLite. Indexed search retrieves older memories; the library is in Settings. Settings can keep saved memories out of provider context.
- Hands-free voice commands use one wake phrase: **Jarvis**. A local filter keeps common noises from reaching Groq; it downloads an approximately 31 MB Portuguese model on first use. Recording ends after a pause, without a button. Replies appear in the central interface and chat, with local speech by sentence.
- Voice or text commands to open installed apps without an extra confirmation after an explicit request. Typing text, pressing keys, clicking, and scrolling still require confirmation. The `agir: request` command sends a screenshot to Gemini, which may suggest one action; the user reviews and confirms before execution.
- On-demand screen analysis or continuous viewing enabled in Settings: the HUD shows a smooth local screen preview (about 10 updates/s locally) while Gemini Live receives up to 1 image/s, the API documented limit. Observations appear in chat history. Cloud transmission may use API quota, and viewing can be stopped at any time.
- Search by name through apps available in Start and classic programs registered in Windows; an explicit request opens the app without an extra confirmation. Manual `.exe` selection is also available.
- HUD player for local files and URLs, plus YouTube embedded in the interface: paste a URL or search for a song, choose a result, and play it on the official page without downloading the track. Favorites and a queue are saved locally; the next entry can be opened by button or voice command. The panel can be collapsed while audio plays. Downloading audio from a URL is a separate option that asks for confirmation.
- Configurable routines of up to eight local app, navigation, and music commands. Reminders can repeat daily, weekly, monthly, or yearly; for example, say `me lembra de revisar todo dia às 9`. An `.ics` calendar file can create reminders one day before future events. Vision can observe a display selected in Settings; visual actions use the primary display.
- Gmail desktop OAuth integration, limited to sending messages, with confirmation before each send.
- WhatsApp Web inside the HUD, with an allowlist stored locally and messages prepared for review. WhatsApp Web's call interface can also be used in the HUD if the service and Qt WebEngine are compatible; the user answers and ends calls in that interface, after granting microphone or camera access when requested.
- Option to start minimized at Windows or Linux login and remain in the system tray. A per-user lock prevents duplicate instances from competing for the microphone or memory.
- Optional double-clap shortcut to toggle full screen. Detection runs locally, requires explicit activation, and keeps the microphone open while enabled.
- Tool for proposing changes to its own source: select a module, ask Gemini for a proposal, review the complete file, and confirm twice before writing. Syntax is checked, a backup is created before replacement, and a saved version can be restored from the interface.

### Requirements

- Windows 10/11. Automatic startup also supports Linux; macOS support has not been implemented.
- For a source install: Python 3.11 or newer: [download Python](https://www.python.org/downloads/). On Windows, select **Add Python to PATH** during installation.
- A microphone and audio output for voice features.
- Gemini API key: [Google AI Studio](https://aistudio.google.com/app/api-keys).
- Groq API key: [Groq Console](https://console.groq.com/keys). Groq can be used for chat and is required for voice transcription.

API use is subject to each provider's limits, availability, terms, and any charges. Gemini 3.8 Flash offers free use within Google's published free quota, but Google Search grounding is not included in the free tier. Check the [official pricing page](https://ai.google.dev/gemini-api/docs/pricing) and provider dashboards before using paid features.

- The Command Center shows current provider, microphone, screen, media, and memory states, with gentle page transitions and a pulsing core.
- Say or type play [artist or track] or search YouTube [query] to open official YouTube results in the HUD. The player supports a floating window, compact mode, and full screen.

### Easy Windows installation

Download `JARVIS-AI-Setup` from the latest **Build Windows installer** run under GitHub → Actions and run the installer. It installs JARVIS without requiring Python on the target computer. Enter Gemini/Groq keys in Settings on first launch.

To build the installer from source, install Python 3.11+ and Inno Setup, then run `build_windows.bat`. The portable app is also written to `dist/JarvisAI`.

### Install from source

Install Python, open PowerShell, and run:

```powershell
git clone https://github.com/matheusmoreira88/jarvis-ai.git
cd jarvis-ai
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m jarvis
```

If PowerShell blocks virtual-environment activation, run the app without activating it:

```powershell
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m jarvis
```

On first launch, enter both Gemini and Groq API keys. They are stored in the operating system's credential vault, not in repository files, so you will not need to enter them again on later launches. To change them, open **Settings**.

The optional email and phone fields in Settings are private references stored in this computer's credential vault. The app does not send them to providers. Gmail sends from the account authorized in the OAuth window.

### Controlling apps

Use text or voice commands such as `abrir calculadora` (open calculator), `abrir aplicativo: app name`, `abrir exe: C:\path\app.exe`, `digitar: text to paste`, `pressionar: enter` (press enter), `clicar` (click), or `rolar: baixo` (scroll down). An explicit request to open an app launches it without an extra confirmation. The full list is in **Settings**. Typing, key presses, clicks, and scrolling still ask first. Place the pointer at the target before confirming a click. Typed text and local `.exe` paths are stored in SQLite history but excluded from context sent to Gemini/Groq.

To ask Gemini to identify a control on screen, use `agir: click the Save button`. JARVIS asks permission to send a current screenshot to Gemini, shows the suggested action, and requests a second confirmation before clicking. The model can only propose one click, short scroll, common key press, or no action; it cannot type text or run system commands.

To erase the saved conversation, choose **Apagar memória local…** and confirm.

### Automatic startup and system tray

Click **Ativar início automático** (Enable automatic startup) and confirm. The app will open minimized at the next login. Closing the window keeps JARVIS in the system tray; select **Encerrar** (Exit) from the tray menu to quit. To remove automatic startup, click **Desativar início automático** (Disable automatic startup).

### Configure services in Settings

#### Gemini and Groq

1. Create a Gemini key in [Google AI Studio](https://aistudio.google.com/app/api-keys) and/or a Groq key in [Groq Console](https://console.groq.com/keys).
2. Enter the keys in the first-run window or in **Settings**.
3. Choose Gemini or Groq for chat. Select **Pesquisar na web com Gemini nesta solicitação** (Search the web with Gemini for this request) to enable Google Search. Search Grounding is not available on the free Gemini API tier and may incur charges on a paid tier; check the pricing page before using it. Image analysis uses Gemini, and voice transcription uses Groq/Whisper.

#### Gmail

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/) and enable the Gmail API.
2. Configure the OAuth consent screen and create an OAuth Client ID of type **Desktop app**.
3. Download the client JSON and import it in JARVIS using **Configurar Gmail OAuth…** (Configure Gmail OAuth).
4. The browser opens Google authorization when you send the first email. Review the recipient and read the full message in the scrollable review window before each send.

The integration requests only the send permission (`gmail.send`). It does not read the inbox or answer phone calls.

#### WhatsApp

1. Open **Contatos permitidos…** (Allowed contacts) and add a name and an international phone number, including the country calling code (for example, `5521999999999`).
2. Click **Preparar mensagem WhatsApp…** (Prepare WhatsApp message), select an allowed contact, and write the message.
3. Read the full message in the scrollable review window and confirm. WhatsApp Web opens in the HUD; sign in, check the conversation, and press **Send** manually.

The app does not read messages or send without the user's final action. For calls, use the official controls shown in WhatsApp Web. JARVIS does not auto-answer. Microphone and camera access are granted only after confirmation for `web.whatsapp.com`, and also depend on Windows permissions. Calls in the HUD depend on WhatsApp Web compatibility with the installed Qt WebEngine version.

### Privacy and security

- For text or voice conversations, the selected provider receives the current message and up to 20 previous conversation messages. Recorded audio is sent to Groq for transcription; then the transcript and recent context go to the selected chat provider.
- On-demand captures and action proposals send the image and current request to Gemini when requested; they do not include conversation history. Continuous vision sends frames and analysis prompts to Gemini Live only while it is enabled. Captures are not saved to SQLite.
- Clap detection analyzes audio locally and does not record or transmit microphone blocks.
- By default, up to 12 relevant or recent memories and up to 12 future reminders are included in text or spoken chat context. Turn off “Incluir lembranças salvas no contexto enviado à IA” in Settings to keep them local. SQLite history and memories are not encrypted.
- API keys and contacts are stored in the user's credential vault. OAuth tokens and settings are stored in private application-data folders outside the repository.
- SQLite history stays on the computer and is not encrypted; on Linux/macOS, JARVIS restricts file and directory permissions to the current account. On Windows, it uses the current user's application-data folder.
- Emails require confirmation. WhatsApp messages are prepared for review; the final send is manual.
- Computer actions use a limited list and require confirmation. JARVIS does not execute arbitrary commands generated by the model.
- Do not publish OAuth files, tokens, or keys. If a key is exposed, revoke it in the provider dashboard.

### Known limitations

Computer control is limited to apps Windows can enumerate and implemented actions. Opening an app after an explicit request does not ask for extra confirmation; clicks, scrolling, key presses, and typing still do. Live vision streams individual frames (up to one per second, not high-frame-rate video) and depends on Gemini Live API availability; sessions are renewed periodically. Calls are not answered automatically. Playback of files and URLs depends on formats supported by Qt Multimedia. Downloads must comply with copyright and site terms. Source changes require explicit review and an app restart.

### Development

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m jarvis
```


## Ativação por palavra-chave, privacidade e atualizações

Com as chaves configuradas, a escuta e a visão iniciam automaticamente. Diga apenas “Jarvis” e seu pedido. No primeiro uso, o JARVIS baixa o [modelo pequeno de português do Vosk](https://alphacephei.com/vosk/models), sob licença Apache 2.0. Ele filtra o nome localmente e envia apenas comandos detectados à Groq. Se não reconhecer o nome, o comando não será enviado; teste com seu microfone. Para desligar, peça “Jarvis, desligar microfone” ou “Jarvis, desligar visão”; a escolha é lembrada nas próximas aberturas.

O microfone e a visão podem ser desligados por comando de voz ou nas Configurações. Essa preferência permanece após reiniciar o aplicativo. As chaves e o provedor são gerenciados somente nas Configurações.

Crie ações rápidas em Configurações. Cada frase configurada chama o mesmo despachante de comandos locais do aplicativo, preservando suas confirmações e validações.

Para atualizar, use **Verificar atualizações** nas configurações. A página de releases publica o instalador de Windows associado a tags `v*`; instale a versão mais recente por cima da atual para manter suas preferências locais. Quem mantém o projeto pode publicar uma versão criando e enviando uma tag, por exemplo `v0.4.0`.

O único modo de chamada é “Jarvis”, reconhecido localmente pelo Vosk.


### English: wake-word activation, privacy and updates

With API keys configured, listening and vision start automatically. Say “Jarvis” and your request. On first use, JARVIS downloads the [small Portuguese Vosk model](https://alphacephei.com/vosk/models), licensed under Apache 2.0. It filters the name locally and sends detected commands to Groq. If it misses the name, the command is not sent; test it with your microphone. To stop, say “Jarvis, desligar microfone” or “Jarvis, desligar visão”; the choice persists across launches.

Turn the microphone or vision off by voice command or in Settings. This preference survives app restarts. API keys and the chat provider are managed in Settings.

Create, use and remove configurable quick actions in Settings. Each phrase calls the app’s existing local command dispatcher, preserving its checks and confirmations.

To update, select **Check for updates** in Settings. The GitHub releases page provides the Windows installer published for v* tags. Install the newest version over the existing one to retain local preferences. Maintainers can publish a release by creating and pushing a tag, for example v0.3.0.

The only wake phrase is “Jarvis”, recognized locally with Vosk.


## Versão 0.4.0 · painel e memória permanente

A versão 0.4.0 traz o painel simplificado inspirado no conceito visual enviado: versão atual no núcleo, monitor real de CPU/RAM/disco, mapa visual de memória e prévia local ao vivo da tela. A área “Active Agents” e cartões demonstrativos foram removidos. Voz mãos livres usa “Hey Jarvis” por padrão quando ativada nas preferências. Para salvar uma informação, diga ou escreva “Jarvis, lembra que meu planejamento escolar está no caderno azul”. Para criar um prazo, use uma data: “Jarvis, me lembra 1 dia antes de entregar o trabalho dia 18/11/2027”. No próximo início do JARVIS em que o horário do alerta já tiver chegado, ele mostra o lembrete. As lembranças ficam no SQLite local e podem ser revisadas ou excluídas em **Painel → Ver lembranças e lembretes**.

## Version 0.4.0 · dashboard and long-term memory

Version 0.4.0 adds the streamlined dashboard inspired by the supplied visual: current app version, real CPU/RAM/disk monitor, memory map, and a live local screen preview. The “Active Agents” area and sample cards were removed. Hands-free voice uses “Hey Jarvis” by default when enabled in Settings. To save a fact, say or type “Jarvis, remember that my school plan is in the blue notebook.” To set a due date, include a date: “Jarvis, me lembra 1 dia antes de entregar o trabalho dia 18/11/2027.” JARVIS displays the reminder the next time it starts after the alert time. Memories stay in local SQLite and can be reviewed or deleted from **Dashboard → View memories and reminders**.


## Versão 0.5.0 · ativação Jarvis e menor latência

Fale “Jarvis, [comando]” ou “Jarvis” e o comando na frase seguinte. O modo Jarvis usa detecção local de fala e envia os trechos detectados à Groq para transcrever; frases sem Jarvis não viram comandos. A pausa que encerra a fala foi reduzida para 0,7 s. O modo opcional Hey Jarvis continua disponível com detecção da palavra-chave local. A visão começa ao ser ligada, sem aviso adicional dentro do aplicativo; leia as [informações de privacidade](PRIVACY.txt) antes de baixar. Confirmações para clicar, digitar, enviar mensagens ou modificar arquivos continuam. Voz e visão estão em módulos separados da interface. Os testes automatizados cobrem ativação, lembretes, permissões e confirmações.

## Version 0.5.0 · Jarvis activation and lower latency

Say “Jarvis, [command]” or “Jarvis” and your command in the next phrase. Jarvis mode uses local speech detection and sends detected speech segments to Groq for transcription; phrases without Jarvis do not become commands. The end-of-speech pause is now 0.7 s. Optional Hey Jarvis mode still uses local wake-word detection. Vision begins when switched on, without another in-app notice; read the [privacy information](PRIVACY.txt) before downloading. Confirmations for clicking, typing, sending messages, and modifying files remain. Voice and vision workers are separate from the interface. Automated tests cover activation, reminders, permissions, and confirmations.

## Versão 0.6.0 · voz, memória e HUD

- Ativação opcional “Jarvis local” com filtro Vosk baixado no primeiro uso; o modo anterior com transcrição na nuvem permanece disponível. O microfone reutiliza o mesmo fluxo entre frases e ajusta o limiar de fala ao ruído do ambiente.
- Respostas aparecem em fluxo, com leitura local por frases. A busca FTS5 recupera lembranças antigas; a biblioteca de memória tem busca e paginação.
- A prévia da tela e a visão Gemini compartilham a captura. É possível escolher a tela observada; propostas de ação usam a tela principal.
- Novo núcleo visual, indicadores reais no painel, redução de animações, favoritos e fila de mídia, rotinas configuráveis, lembretes recorrentes e importação de eventos `.ics` com aviso um dia antes.
- O código da resposta, tema, rotinas, calendário, mídia e detecção local foi separado em módulos. Testes de regressão cobrem as novidades.

Para usar as novidades, abra **Configurações**. Escolha a tela observada; crie uma rotina com uma frase e de 1 a 8 comandos locais; importe seu calendário escolar `.ics`; ou abra **Ver lembranças e lembretes** para pesquisar conteúdos antigos. Em **Mídia**, use **☆ Salvar**, **+ Fila** e **Próxima**. Arquivos `.ics` com regras de repetição complexas são importados apenas pela ocorrência explícita no arquivo; exporte as ocorrências futuras separadamente se precisar de todas.

## Version 0.6.0 · voice, memory and HUD

- Optional “Jarvis local” activation with a first-use Vosk download; the previous cloud transcription mode remains available. The microphone reuses its stream between utterances and adapts its speech threshold to background noise.
- Replies stream into chat with sentence-sized local speech. FTS5 search retrieves older memories, and the memory manager adds search and paging.
- The local screen preview and Gemini vision share capture. You can select the observed display; visual action proposals use the primary display.
- New painted core, real dashboard indicators, reduced-motion option, media favorites and queue, configurable routines, recurring reminders, and `.ics` event import with a one-day reminder.
- Reply, theme, routine, calendar, media, and local wake code are separate modules. Regression checks cover the new behavior.

Open **Settings** to select the observed display, configure a routine with a phrase and 1–8 local commands, import a school `.ics` calendar, or select **Ver lembranças e lembretes** to search old memories. In **Media**, use **☆ Salvar** (Save), **+ Fila** (Queue), and **Próxima** (Next). Complex recurring rules in `.ics` files are imported only as the explicit occurrence in the file; export future occurrences separately if you need them all.

## Versão 0.6.1 · interface central e ativação única

O painel agora concentra o JARVIS em uma esfera neural animada e mostra respostas no centro. Foram removidos o monitor do sistema, o mapa de memória, os indicadores intermediários e os nomes de provedores no menu. Configurações ganhou fundo consistente e deixou de animar a área de rolagem, evitando a sobreposição visual. O único modo de ativação exposto é “Jarvis”; ruídos curtos são filtrados antes da transcrição. Voz e visão iniciam com chaves configuradas e respeitam a escolha de desligá-las. Comandos de voz podem minimizar o JARVIS ou colocá-lo em tela cheia. O texto de privacidade exibido pelo instalador e os direitos autorais foram atualizados.

## Version 0.6.1 · central interface and one wake phrase

The main view now centers JARVIS in an animated neural sphere and shows answers there. The system monitor, memory map, middle status pills, and provider names in the menu were removed. Settings has a consistent background and no longer animates its scrolling surface, avoiding the visual overlap. The only exposed wake phrase is “Jarvis”; short noises are filtered before transcription. Voice and vision start when keys are configured and respect a later choice to turn them off. Voice commands can minimize JARVIS or switch it to full screen. The installer privacy text and copyright notice were updated.
