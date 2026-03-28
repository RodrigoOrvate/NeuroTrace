; ============================================================================
; NeuroTrace — Script do Instalador (Inno Setup 6)
; ============================================================================
; Para compilar:
;   1. Instale o Inno Setup 6: https://jrsoftware.org/isinfo.php
;   2. Execute: iscc packaging\installer.iss  (a partir da raiz do projeto)
;   Ou abra este arquivo diretamente no Inno Setup Compiler.
; ============================================================================

#define MyAppName "NeuroTrace"
#define MyAppVersion "2.0.1"
#define MyAppPublisher "Rodrigo Orvate"
#define MyAppURL "https://github.com/RodrigoOrvate/NeuroTrace"
#define MyAppExeName "NeuroTrace.exe"
#define MyAppIconName "memorylab.ico"

[Setup]
; Identificador único do aplicativo (NÃO altere entre versões)
AppId={{A8F3B2D1-4E5C-6A7B-8C9D-0E1F2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Permite o usuário desabilitar a criação do atalho na área de trabalho
AllowNoIcons=yes
; Arquivo de licença (opcional — descomente se tiver um LICENSE)
; LicenseFile=LICENSE
; Diretório de saída do instalador compilado (relativo a este .iss)
OutputDir=..\installer_output
OutputBaseFilename=NeuroTrace_Setup_v{#MyAppVersion}
; Ícone do instalador (relativo a este .iss)
SetupIconFile=..\{#MyAppIconName}
; Compressão
Compression=lzma2/ultra64
SolidCompression=yes
; Visual moderno
WizardStyle=modern
; Requer privilégios de administrador para instalar em Program Files
PrivilegesRequired=admin
; Informações visuais
WizardSmallImageFile=compiler:WizModernSmallImage.bmp
; Versão mínima do Windows (Windows 10+)
MinVersion=10.0
; Desinstalar
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Executável principal (gerado pelo PyInstaller) — caminhos relativos a este .iss
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Ícone
Source: "..\{#MyAppIconName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Atalho no Menu Iniciar
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIconName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
; Atalho na Área de Trabalho (se o usuário marcar a opção)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIconName}"; Tasks: desktopicon

[Run]
; Opção de executar o programa após a instalação
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Fecha o NeuroTrace se estiver rodando antes de instalar/atualizar
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Tenta fechar o processo se estiver rodando
  Exec('taskkill.exe', '/F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
