; Yasna Windows installer
#define AppName "Yasna"
#define AppVersion "1.0.0"
#define AppPublisher "Yasna"
#define AppExeName "Yasna.exe"

[Setup]
AppId={{B0D3A82C-7B0D-4C8D-A8C1-5D6D5F3A2026}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Yasna
DefaultGroupName=Yasna
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Yasna_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#AppExeName}

[Tasks]
Name: "desktopicon"; Description: "ساخت میان‌بر روی دسکتاپ"; GroupDescription: "میان‌برها:"; Flags: unchecked

[Files]
Source: "..\dist\Yasna\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Yasna"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Yasna"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "اجرای Yasna"; Flags: postinstall nowait skipifsilent


[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  if MsgBox(
    'آیا می‌خواهید بانک اطلاعاتی یسنا هم حذف شود؟' + #13#10 +
    'با انتخاب بله، تمام نامه‌ها، اشخاص، یادآوری‌ها و حساب‌های کاربری حذف می‌شوند.' + #13#10 +
    'در نصب مجدد، صفحه تعریف مدیر سیستم دوباره نمایش داده خواهد شد.' + #13#10#13#10 +
    'با انتخاب خیر، اطلاعات حفظ می‌شوند و مدیر قبلی باقی می‌ماند.',
    mbConfirmation, MB_YESNO
  ) = IDYES then
  begin
    DeleteFile(ExpandConstant('{app}\Yasna.db'));
    DeleteFile(ExpandConstant('{app}\Yasna.db-wal'));
    DeleteFile(ExpandConstant('{app}\Yasna.db-shm'));
  end;
end;
