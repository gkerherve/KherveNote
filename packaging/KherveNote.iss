; Inno Setup script for KherveNote — per-user install, no admin rights.
;
; Not run by hand: packaging/build_installer.py freezes the app and then calls
;
;   ISCC.exe /DAPP_VERSION=0.26.N /DSRC_DIR=...\dist\KherveNote /DOUT_DIR=...\dist
;            /DICON_FILE=...\build\KherveNote.ico KherveNote.iss
;
; Installs to %LOCALAPPDATA%\Programs\KherveNote, so there is no elevation
; prompt, and associates .knote notes. tectonic and its TeX cache are
; inside the app folder; the Whisper speech model is NOT (downloaded once
; on first Listen, into the user's Hugging Face cache).
;
; Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0.

#ifndef APP_VERSION
  #define APP_VERSION "0.0.0"
#endif
#ifndef SRC_DIR
  #define SRC_DIR "..\dist\KherveNote"
#endif
#ifndef OUT_DIR
  #define OUT_DIR "..\dist"
#endif
#ifndef ICON_FILE
  #define ICON_FILE "..\build\KherveNote.ico"
#endif

#define AppName "KherveNote"
#define AppPublisher "Gwilherm Kerherve"
#define AppURL "https://khervetools.com/tools/khervenote"
#define AppExe "KherveNote.exe"

[Setup]
AppId={{6E2B9C41-5D7A-4F3B-9A1E-0C8D4B27F519}
AppName={#AppName}
AppVersion={#APP_VERSION}
AppVerName={#AppName} {#APP_VERSION}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
VersionInfoVersion={#APP_VERSION}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
SetupIconFile={#ICON_FILE}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#OUT_DIR}
OutputBaseFilename={#AppName}-Setup-{#APP_VERSION}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[InstallDelete]
; Inno never removes a file a newer build dropped, and the Python packages
; (numpy, PySide6, CTranslate2, onnxruntime) are ABI-bound to each other: an upgrade must
; not leave the old _internal tree beside the new one. It is all build
; output; nothing the user made lives under {app}.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\KhervePDF"

[Files]
Source: "{#SRC_DIR}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Per-user (HKCU) to match the per-user install.
Root: HKCU; Subkey: "Software\Classes\.knote"; ValueType: string; ValueName: ""; ValueData: "KherveNote.Note"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\KherveNote.Note"; ValueType: string; ValueName: ""; ValueData: "KherveNote note"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\KherveNote.Note\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\KherveNote.Note\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
