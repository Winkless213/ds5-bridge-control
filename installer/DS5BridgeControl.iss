; DS5 Bridge Control installer (Inno Setup 7)
; Build the PyInstaller onedir output first, then run:
;   ISCC.exe installer\DS5BridgeControl.iss

#define AppName "DS5 Bridge Control"
#define AppVersion "1.5.0"
#define AppPublisher "Winkless213"
#define AppURL "https://github.com/Winkless213/ds5-bridge-control"
#define AppExe "DS5 Bridge Control.exe"
#define AppSrc "..\dist\DS5 Bridge Control"

[Setup]
AppId={{2B9EB101-2FF9-411F-9375-232E81CB9B08}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion=1.5.0.0
VersionInfoDescription={#AppName} installer
VersionInfoProductName={#AppName}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\work\release\installer
OutputBaseFilename=DS5-Bridge-Control-Setup-{#AppVersion}
SetupIconFile=..\assets\ds5_bridge.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
LicenseFile=..\LICENSE
AllowNoIcons=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce

[Files]
Source: "{#AppSrc}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent; Check: ShouldLaunchApp

[Code]
var
  SelfTestPassed: Boolean;

function ShouldLaunchApp: Boolean;
begin
  Result := SelfTestPassed;
end;

function RuntimeFilesPresent: Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{app}\{#AppExe}')) and
    FileExists(ExpandConstant('{app}\_internal\VCRUNTIME140.dll')) and
    FileExists(ExpandConstant('{app}\_internal\PySide6\Qt6Core.dll')) and
    FileExists(ExpandConstant('{app}\_internal\PySide6\plugins\platforms\qwindows.dll')) and
    FileExists(ExpandConstant('{app}\_internal\ds5_bridge\qml\Main.qml'));
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not IsWin64 then
  begin
    MsgBox('DS5 Bridge Control 需要 64 位 Windows 10 或更高版本。', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;

  if not RuntimeFilesPresent then
  begin
    MsgBox('安装文件不完整：缺少 Qt 运行库、VC 运行库或 QML 资源。' + #13#10 +
           '请重新下载安装包。', mbError, MB_OK);
    Exit;
  end;

  if Exec(ExpandConstant('{app}\{#AppExe}'), '--self-test',
          ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) and
     (ResultCode = 0) then
  begin
    SelfTestPassed := True;
  end
  else
  begin
    MsgBox('安装完成，但启动自检失败。' + #13#10 +
           '请查看 %TEMP%\DS5BridgeControl-self-test.log，或到 GitHub Issues 反馈。',
           mbError, MB_OK);
  end;
end;
