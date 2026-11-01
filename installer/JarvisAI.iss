#define AppName "JARVIS AI"
#define AppVersion "0.7.0"
#define AppPublisher "Matheus Moreira"
#define AppExeName "JarvisAI.exe"

[Setup]
AppId={{0F3E7067-9D10-4AF2-8B16-69E3A8FA8C01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\JarvisAI
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=JARVIS-AI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile=..\PRIVACY.txt
UninstallDisplayName={#AppName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\JarvisAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JARVIS AI"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\JARVIS AI"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir JARVIS AI"; Flags: postinstall nowait skipifsilent
