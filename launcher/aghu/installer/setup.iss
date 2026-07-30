; Instalador (Inno Setup) do launcher AGHU: Impressora por Computador.
; Empacotamento isolado do launcher servicos_ti (produto próprio).
; Compilar a partir da raiz do build do PyInstaller (launcher\aghu\dist\ImpressoraAGHU).
; Uso: iscc launcher\aghu\installer\setup.iss /DMyAppVersion=1.0.0

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

#define MyAppPublisher "Extrator2"
#define MyDistDir "..\dist\ImpressoraAGHU"

[Setup]
AppId={{7F2A5C31-9B44-4E1A-8C3D-6A0E9B5F2C17}}
AppName=Extrator2 - AGHU Impressora
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Extrator2\ImpressoraAGHU
DefaultGroupName=Extrator2
DisableProgramGroupPage=yes
OutputDir=..\dist\installers
OutputBaseFilename=ImpressoraAGHU-Setup-{#MyAppVersion}
SetupIconFile=..\icons\impressora_aghu.ico
UninstallDisplayIcon={app}\ImpressoraAGHU.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Instalação por usuário: não exige privilégios de administrador.
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar ícone na área de trabalho"; GroupDescription: "Ícones na área de trabalho:"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "leiame.txt"; DestDir: "{app}"; DestName: "LEIAME.txt"; Flags: isreadme

[Icons]
Name: "{group}\AGHU Impressora"; Filename: "{app}\ImpressoraAGHU.exe"; IconFilename: "{app}\ImpressoraAGHU.exe"
Name: "{autodesktop}\AGHU Impressora"; Filename: "{app}\ImpressoraAGHU.exe"; IconFilename: "{app}\ImpressoraAGHU.exe"; Tasks: desktopicon
Name: "{group}\Leia-me"; Filename: "{app}\LEIAME.txt"
Name: "{group}\Desinstalar AGHU Impressora"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\ImpressoraAGHU.exe"; Description: "Executar AGHU Impressora"; Flags: nowait postinstall skipifsilent unchecked
