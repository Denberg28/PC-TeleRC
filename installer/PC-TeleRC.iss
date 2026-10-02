#define MyAppName "PC TeleRC"
#define MyAppVersion "0.1.0a7"
#define MyAppPublisher "Denberg28"
#define MyAppExeName "PC-TeleRC.exe"

[Setup]
AppId={{0A14B133-FEC1-5E89-97E2-D08281951913}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion=0.1.0.7
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=PC TeleRC Windows rover control bridge
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=0.1.0.7
DefaultDirName={localappdata}\Programs\PC TeleRC
DefaultGroupName=PC TeleRC
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer-dist
OutputBaseFilename=PC-TeleRC-Setup-v0.1.0a7
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=PC TeleRC
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
RestartApplications=no
UsePreviousAppDir=yes
ChangesAssociations=no
ChangesEnvironment=no

[Files]
Source: "..\dist\PC-TeleRC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PC TeleRC"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall PC TeleRC"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PC TeleRC"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PC TeleRC"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Deliberately do not remove %LOCALAPPDATA%\PC-TeleRC.
; Controller calibration/settings/logs are preserved across upgrades and uninstall.
