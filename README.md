# JARVIS AI

[Português (Brasil)](#português-brasil) | [English](#english)

## Português (Brasil)

Assistente pessoal para desktop em português, criado por **Matheus Moreira**. Este projeto é uma implementação independente, com interface própria em PySide6, memória local e integrações opcionais. O JARVIS pede confirmação antes de executar ações no computador, enviar e-mail ou preparar mensagens.

Instagram do criador: [@mthz.mm](https://www.instagram.com/mthz.mm/)<br>
Contato: [matheusmoreiradossantos88@gmail.com](mailto:matheusmoreiradossantos88@gmail.com)

Se o projeto for útil, [deixe uma estrela no GitHub](https://github.com/matheusmoreira88/jarvis-ai) e compartilhe sugestões ou problemas pela área de Issues.

Licença: [MIT](LICENSE).

### Recursos

- Conversa por texto com Gemini ou Groq, selecionável nas configurações, e pesquisa na web com Gemini com fontes retornadas pela busca.
- Os dois provedores recebem instruções para reconhecer Matheus Moreira como criador, responder em português e não alegar ações que o aplicativo não executou.
- Uma conversa única, sem sessões separadas. Todo o histórico é persistido em SQLite entre inicializações e pode ser percorrido por páginas no HUD, com botão para apagar a memória local.
- Comando por voz: o microfone abre somente após pressionar **Falar**, acompanha a fala e encerra após cerca de 1,15 segundo de silêncio ou pelo botão de parada. Groq/Whisper transcreve e uma voz sintetizada localmente lê a resposta. Há um limite de segurança de três minutos por gravação.
- Comandos por voz ou texto para abrir aplicativos autorizados, digitar texto e pressionar teclas comuns, sempre com confirmação e escopo limitado. O comando `agir: pedido` envia uma captura ao Gemini, que pode propor uma única ação; a pessoa revisa e confirma antes da execução.
- Análise da tela por captura explícita ou observação contínua opcional com Gemini 3.8 Live, até um quadro por segundo. Depois de cada cinco quadros, envia um pedido de análise; as observações são exibidas no histórico e o áudio de resposta é reproduzido localmente. A observação pede consentimento, transmite imagens e pode consumir cota da API; a conexão é renovada periodicamente.
- Abertura confirmada de aplicativos conhecidos (Bloco de Notas, Calculadora e Explorador de Arquivos) e escolha manual de outros executáveis `.exe` no Windows.
- Player no HUD para arquivos locais e URLs, além do YouTube incorporado: cole uma URL ou pesquise o nome de uma música, escolha um resultado e reproduza na página oficial sem baixar a faixa. O painel pode ser recolhido enquanto o áudio toca. Baixar áudio por URL é uma opção separada que pede confirmação.
- Gmail por OAuth de desktop, com permissão limitada a enviar mensagens e confirmação antes de cada envio.
- WhatsApp Web dentro do HUD, contatos permitidos guardados localmente e mensagens preparadas para revisão. A interface de chamadas do WhatsApp Web pode ser usada no HUD se o serviço e o Qt WebEngine forem compatíveis; o usuário atende e encerra pela própria interface, após permitir o microfone ou a câmera quando solicitado.
- Opção para iniciar minimizado com o login do Windows ou Linux e permanecer na bandeja do sistema.
- Atalho opcional de duas palmas para alternar a tela cheia. A detecção é local, requer ativação expressa e mantém o microfone aberto enquanto estiver ligada.
- Ferramenta para propor mudanças no próprio código: escolhe um módulo, pede uma proposta ao Gemini, exibe o arquivo para revisão e só grava após duas confirmações. Valida sintaxe, cria backup antes de substituir e permite restaurar uma versão salva pela interface.

### Requisitos

- Windows 10/11. O início automático também oferece suporte a Linux; macOS ainda não foi implementado.
- Python 3.11 ou superior: [baixar Python](https://www.python.org/downloads/). No Windows, marque **Add Python to PATH** durante a instalação.
- Microfone e saída de áudio para os recursos de voz.
- Chave Gemini: [Google AI Studio](https://aistudio.google.com/app/api-keys).
- Chave Groq: [Groq Console](https://console.groq.com/keys). Groq pode ser usado para conversa e é necessário para transcrição de voz.

O uso das APIs depende dos limites, disponibilidade, termos e eventual cobrança de cada provedor. O Gemini 3.8 Flash oferece uso gratuito dentro da cota indicada pelo Google, mas a pesquisa Google (Search Grounding) não está incluída no nível gratuito. Confira a [página oficial de preços](https://ai.google.dev/gemini-api/docs/pricing) e os painéis antes de usar recursos pagos.

### Instalação no Windows

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

Use comandos por texto ou voz como `abrir calculadora`, `abrir exe: C:\caminho\aplicativo.exe`, `digitar: texto que desejo colar`, `pressionar: enter`, `clicar` ou `rolar: baixo`. Para abrir um executável, escolher um app, digitar, pressionar uma tecla, clicar ou rolar, o JARVIS pede confirmação. A abertura de um `.exe` também está disponível em **Integrações**. Posicione o cursor no destino antes de confirmar o clique. O texto digitado e o caminho local do `.exe` ficam no histórico SQLite, mas são omitidos do contexto enviado ao Gemini/Groq.

Para pedir que o Gemini identifique um controle na tela, use `agir: clique no botão Salvar`. O JARVIS pede autorização para enviar uma captura atual ao Gemini, mostra a ação sugerida e solicita uma segunda confirmação antes de clicar. O modelo só pode propor clique, rolagem curta, uma tecla comum ou nenhuma ação; ele não digita nem executa comandos de sistema.

Para apagar a conversa persistida, clique em **Apagar memória local…** e confirme.

### Início automático e bandeja

Clique em **Ativar início automático** e confirme. O aplicativo abre minimizado no próximo login. Fechar a janela mantém o JARVIS na bandeja; escolha **Encerrar** no menu do ícone para sair. Para remover o início automático, clique em **Desativar início automático**.

### Configurar as integrações

#### Gemini e Groq

1. Crie uma chave Gemini no [Google AI Studio](https://aistudio.google.com/app/api-keys) e/ou uma chave Groq em [Groq Console](https://console.groq.com/keys).
2. Insira as chaves na janela inicial ou em **Configurações**.
3. Escolha Gemini ou Groq como provedor de conversa. Marque **Pesquisar na web com Gemini nesta solicitação** para ativar a pesquisa Google. O Search Grounding não está disponível no nível gratuito da Gemini API e pode gerar cobrança no nível pago; confira a página de preços antes de usar. A análise de imagem usa Gemini e a transcrição de voz usa Groq/Whisper.

#### Gmail

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e habilite a Gmail API.
2. Configure a tela de consentimento OAuth e crie um OAuth Client ID do tipo **Aplicativo para computador**.
3. Baixe o JSON desse cliente e clique em **Configurar Gmail OAuth…** no JARVIS para importá-lo.
4. Ao enviar o primeiro e-mail, o navegador abrirá a autorização Google. Confira o destinatário e o conteúdo na confirmação antes de cada envio.

A integração solicita somente a permissão de envio (`gmail.send`). Ela não lê a caixa de entrada nem atende chamadas telefônicas.

#### WhatsApp

1. Abra **Contatos permitidos…** e cadastre nome e telefone no formato internacional, incluindo DDI (por exemplo, `5521999999999`).
2. Clique em **Preparar mensagem WhatsApp…**, selecione um contato autorizado e escreva a mensagem.
3. Revise e confirme. O WhatsApp Web abre no HUD; entre na sua conta, confira a conversa e pressione **Enviar** manualmente.

O aplicativo não lê mensagens nem envia sem a ação final do usuário. Em uma chamada, use os controles oficiais exibidos no WhatsApp Web. O JARVIS não atende automaticamente. O microfone e a câmera só são liberados depois de uma confirmação para `web.whatsapp.com`, e também dependem das permissões do Windows. Chamadas dentro do HUD dependem da compatibilidade do WhatsApp Web com o Qt WebEngine instalado.

### Privacidade e segurança

- Gemini e Groq recebem somente o conteúdo encaminhado para cada solicitação: prompts, capturas de tela após ação ou consentimento, e áudio gravado para transcrição.
- A detecção de palmas analisa áudio localmente e não grava nem transmite os blocos de microfone.
- Chaves de API e contatos ficam no cofre de credenciais do usuário. Tokens OAuth e configurações ficam nas pastas privadas de dados do aplicativo, fora do repositório.
- O histórico SQLite permanece no computador e não é criptografado; no Linux/macOS, o JARVIS restringe as permissões dos arquivos e pastas à conta atual. No Windows, usa a pasta de dados do perfil do usuário.
- E-mails exigem confirmação. Mensagens do WhatsApp são preparadas para revisão; o envio final é manual.
- As ações no computador usam uma lista limitada e pedem confirmação. O JARVIS não executa comandos arbitrários gerados pelo modelo.
- Não publique arquivos OAuth, tokens nem chaves. Se uma chave for exposta, revogue-a no painel do provedor.

### Limitações conhecidas

O controle do computador está limitado aos aplicativos e ações confirmadas. A visão Live transmite quadros individuais (não vídeo de alta taxa de quadros) e depende da disponibilidade da Gemini Live API; as sessões são renovadas periodicamente. Chamadas não são atendidas automaticamente. A reprodução de arquivos e URLs depende dos formatos suportados pelo Qt Multimedia. Downloads devem respeitar direitos autorais e termos do site. Alterações no próprio código exigem revisão explícita e reinício do aplicativo.

### Desenvolvimento

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m jarvis
```

Contribuições são bem-vindas por Issues e Pull Requests. Antes de publicar mudanças, confira que nenhum segredo, token ou dado pessoal foi incluído.

---

## English

A Portuguese-language desktop assistant created by **Matheus Moreira**. This is an independent implementation with its own PySide6 interface, local memory, and optional integrations. JARVIS asks for confirmation before taking computer actions, sending email, or preparing messages.

Creator's Instagram: [@mthz.mm](https://www.instagram.com/mthz.mm/)<br>
Contact: [matheusmoreiradossantos88@gmail.com](mailto:matheusmoreiradossantos88@gmail.com)

If you find the project useful, [leave a star on GitHub](https://github.com/matheusmoreira88/jarvis-ai) and share suggestions or issues in the Issues section.

License: [MIT](LICENSE).

### Features

- Text chat with Gemini or Groq, selectable in Settings, plus Gemini web search with returned source links.
- Both providers are instructed to recognize Matheus Moreira as the creator, answer in Portuguese, and never claim actions the app did not perform.
- One ongoing conversation, with no separate sessions. The full history is stored in SQLite between app launches and can be browsed in pages in the HUD, with a button to clear local memory.
- Voice commands: the microphone opens only after pressing **Speak**, follows the user's speech, and stops after about 1.15 seconds of silence or when the stop button is pressed. Groq/Whisper transcribes the recording and a local speech synthesizer reads the response. Each recording has a three-minute safety limit.
- Voice or text commands to open allowed apps, type text, and press common keys, always with confirmation and limited scope. The `agir: request` command sends a screenshot to Gemini, which may suggest one action; the user reviews and confirms before execution.
- Screen analysis on demand or optional continuous observation with Gemini 3.8 Live, up to one frame per second. It sends an analysis prompt after every five frames; observations appear in the history and response audio is played locally. Observation asks for consent, streams images, and may use API quota; the connection is renewed periodically.
- Confirmed opening of known apps (Notepad, Calculator, and File Explorer) and manual selection of other `.exe` files on Windows.
- HUD player for local files and URLs, plus YouTube embedded in the interface: paste a URL or search for a song, choose a result, and play it on the official page without downloading the track. The panel can be collapsed while audio plays. Downloading audio from a URL is a separate option that asks for confirmation.
- Gmail desktop OAuth integration, limited to sending messages, with confirmation before each send.
- WhatsApp Web inside the HUD, with an allowlist stored locally and messages prepared for review. WhatsApp Web's call interface can also be used in the HUD if the service and Qt WebEngine are compatible; the user answers and ends calls in that interface, after granting microphone or camera access when requested.
- Option to start minimized at Windows or Linux login and remain in the system tray.
- Optional double-clap shortcut to toggle full screen. Detection runs locally, requires explicit activation, and keeps the microphone open while enabled.
- Tool for proposing changes to its own source: select a module, ask Gemini for a proposal, review the complete file, and confirm twice before writing. Syntax is checked, a backup is created before replacement, and a saved version can be restored from the interface.

### Requirements

- Windows 10/11. Automatic startup also supports Linux; macOS support has not been implemented.
- Python 3.11 or newer: [download Python](https://www.python.org/downloads/). On Windows, select **Add Python to PATH** during installation.
- A microphone and audio output for voice features.
- Gemini API key: [Google AI Studio](https://aistudio.google.com/app/api-keys).
- Groq API key: [Groq Console](https://console.groq.com/keys). Groq can be used for chat and is required for voice transcription.

API use is subject to each provider's limits, availability, terms, and any charges. Gemini 3.8 Flash offers free use within Google's published free quota, but Google Search grounding is not included in the free tier. Check the [official pricing page](https://ai.google.dev/gemini-api/docs/pricing) and provider dashboards before using paid features.

### Windows installation

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

Use text or voice commands such as `abrir calculadora` (open calculator), `abrir exe: C:\path\app.exe`, `digitar: text to paste`, `pressionar: enter` (press enter), `clicar` (click), or `rolar: baixo` (scroll down). JARVIS asks for confirmation before opening an executable, typing, pressing a key, clicking, or scrolling. You can also select an `.exe` from **Integrations**. Place the pointer at the target before confirming a click. Typed text and local `.exe` paths are stored in SQLite history but excluded from context sent to Gemini/Groq.

To ask Gemini to identify a control on screen, use `agir: click the Save button`. JARVIS asks permission to send a current screenshot to Gemini, shows the suggested action, and requests a second confirmation before clicking. The model can only propose one click, short scroll, common key press, or no action; it cannot type text or run system commands.

To erase the saved conversation, choose **Apagar memória local…** and confirm.

### Automatic startup and system tray

Click **Ativar início automático** (Enable automatic startup) and confirm. The app will open minimized at the next login. Closing the window keeps JARVIS in the system tray; select **Encerrar** (Exit) from the tray menu to quit. To remove automatic startup, click **Desativar início automático** (Disable automatic startup).

### Configuring integrations

#### Gemini and Groq

1. Create a Gemini key in [Google AI Studio](https://aistudio.google.com/app/api-keys) and/or a Groq key in [Groq Console](https://console.groq.com/keys).
2. Enter the keys in the first-run window or in **Settings**.
3. Choose Gemini or Groq for chat. Select **Pesquisar na web com Gemini nesta solicitação** (Search the web with Gemini for this request) to enable Google Search. Search Grounding is not available on the free Gemini API tier and may incur charges on a paid tier; check the pricing page before using it. Image analysis uses Gemini, and voice transcription uses Groq/Whisper.

#### Gmail

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/) and enable the Gmail API.
2. Configure the OAuth consent screen and create an OAuth Client ID of type **Desktop app**.
3. Download the client JSON and import it in JARVIS using **Configurar Gmail OAuth…** (Configure Gmail OAuth).
4. The browser opens Google authorization when you send the first email. Review the recipient and message in the confirmation dialog before each send.

The integration requests only the send permission (`gmail.send`). It does not read the inbox or answer phone calls.

#### WhatsApp

1. Open **Contatos permitidos…** (Allowed contacts) and add a name and an international phone number, including the country calling code (for example, `5521999999999`).
2. Click **Preparar mensagem WhatsApp…** (Prepare WhatsApp message), select an allowed contact, and write the message.
3. Review and confirm. WhatsApp Web opens in the HUD; sign in, check the conversation, and press **Send** manually.

The app does not read messages or send without the user's final action. For calls, use the official controls shown in WhatsApp Web. JARVIS does not auto-answer. Microphone and camera access are granted only after confirmation for `web.whatsapp.com`, and also depend on Windows permissions. Calls in the HUD depend on WhatsApp Web compatibility with the installed Qt WebEngine version.

### Privacy and security

- Gemini and Groq receive only the content routed to them: prompts, screenshots after an explicit action or consent, and recorded audio for transcription.
- Clap detection analyzes audio locally and does not record or transmit microphone blocks.
- API keys and contacts are stored in the user's credential vault. OAuth tokens and settings are stored in private application-data folders outside the repository.
- SQLite history stays on the computer and is not encrypted; on Linux/macOS, JARVIS restricts file and directory permissions to the current account. On Windows, it uses the current user's application-data folder.
- Emails require confirmation. WhatsApp messages are prepared for review; the final send is manual.
- Computer actions use a limited list and require confirmation. JARVIS does not execute arbitrary commands generated by the model.
- Do not publish OAuth files, tokens, or keys. If a key is exposed, revoke it in the provider dashboard.

### Known limitations

Computer control is limited to the listed apps and confirmed actions. Live vision streams individual frames (not high-frame-rate video) and depends on Gemini Live API availability; sessions are renewed periodically. Calls are not answered automatically. Playback of files and URLs depends on formats supported by Qt Multimedia. Downloads must comply with copyright and site terms. Source changes require explicit review and an app restart.

### Development

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m jarvis
```

Contributions are welcome through Issues and Pull Requests. Before publishing changes, check that no secret, token, or personal data has been included.
