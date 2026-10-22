; geodoc — Inno Setup 6 definition. Produkt JEDNOMODELOWY (decyzja ownera
; 07.08): Qwen3-30B obsługuje obie role (worker/analityk) jako profile
; żądań. Model jest ZBUNDLOWANY w instalatorze (decyzja ownera 07.08
; 11:47 — jedna opcja, bez plików obok): Inno powyżej 2 GB skompresowanych
; danych wymaga DiskSpanning, więc wydanie to setup.exe + pliki
; geodoc-setup-<wersja>-N.bin obok (wzorzec GOG; klient klika wyłącznie
; setup.exe, biny czytają się same; wszystkie pliki muszą leżeć razem).
; Wagi idą z flagą nocompression — po kwantyzacji są nieściśliwe
; (zip 97,8 % / lzma2 98,0 % oryginału, zmierzone 06.08), a kompresja
; tylko spowalniałaby build i instalację.
;
; LICENCJA: MIT. Kreator pokazuje tekst LICENSE (LicenseFile) i kopiuje go
; do {app}; wykaz komponentów OSS: docs\THIRD-PARTY-LICENSES.md (instalowany
; z aplikacją), teksty OFL krojów pisma leżą obok nich w app\czcionki.
;
; models.json + models\manifest.json zapisuje instalator (launcher
; weryfikuje rozmiary przy każdym starcie, pełny sha256 raz po
; imporcie). Aplikacja działa w pełni offline.
;
; Build:  iscc installer\geodoc.iss     (Inno Setup 6.5+)
; Output: installer\Output\geodoc-setup-<wersja>.exe
;
; Checklist odporności wg badania 06.08 (źródła: ishelp + install.iss
; Git-for-Windows) — patrz docs/INSTALLER.md.

#define AppName "geodoc"
#define AppVersion "0.95"
#define AppPublisher "Norbert Marchewka"
#define AppURL "https://github.com/Check-It-Out-Dev/geodoc"
#define AppExe "src-tauri\geodoc-tray.exe"
#define Gguf30 "Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf"
; skąd kompilator bierze GGUF: domyślnie katalog models\ klonu (tam kładzie go
; tools\fetch_runtime.py); inny katalog: iscc /DGgufDir=D:\modele geodoc.iss
#ifndef GgufDir
  #define GgufDir "..\models"
#endif

[Setup]
; STAŁA tożsamość aktualizacji — nigdy nie zmieniać (upgrade-in-place,
; jeden wpis w Aplikacjach). Własny GUID wydania open source; kto buduje
; własną odmianę, niech wygeneruje swój, żeby instalacje się nie nadpisywały
AppId={{2319CCFB-738C-41E5-ACF9-867B7D75EB32}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
AppCopyright=© 2026 {#AppPublisher}, licencja MIT
; per-user bez UAC (konwencja VS Code: %LOCALAPPDATA%\Programs); dialog
; pozwala świadomie wybrać instalację dla wszystkich (/ALLUSERS)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\geodoc
DefaultGroupName=geodoc
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableWelcomePage=no
; instalator i deinstalator odmawiają pracy przy żywej aplikacji; tray
; trzyma ten mutex (main.rs) — zamykanie przez RestartManager, restart
; NIE (tray wstaje z wpisu postinstall)
AppMutex=geodoc-tray-mutex
SetupMutex=geodoc-setup-mutex
CloseApplications=yes
RestartApplications=no
MinVersion=10.0.17763
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=geodoc-setup-{#AppVersion}
OutputDir=Output
; model zbundlowany: >2 GB wymaga podzialu na woluminy .bin (GOG-style)
DiskSpanning=yes
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
SetupLogging=yes
; tożsamość wizualna: ikona znacznika osnowy + panele kreatora ze znakiem
; geodoc (multi-DPI, wildcard wybiera najbliższy rozmiar; tools\make_ikony.py)
SetupIconFile=branding\geodoc.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=branding\kreator-*.bmp
WizardSmallImageFile=branding\kreator-maly-*.bmp
; metadane setup.exe (Właściwości → Szczegóły); domyślne 0.0.0.0 wygląda
; amatorsko — badanie potwierdziło, że trzeba ustawić jawnie
VersionInfoVersion={#AppVersion}.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalator {#AppName} — kontrola operatów technicznych
VersionInfoCopyright=© 2026 {#AppPublisher}
VersionInfoProductName={#AppName}
; podpis Certum (OV wystarcza od 2024 — EV bez instant-reputation);
; kolejność: rcedit stempluje PRZED podpisem (build_tray.ps1)
; SignTool=certum $f

[Languages]
Name: "polski"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "Utwórz skrót na pulpicie"; \
  GroupDescription: "Dodatkowe skróty:"

[Files]
; kod aplikacji (źródła Python; środowisko wykonawcze = python-embed
; przygotowany przez tools/build_installer.ps1)
Source: "..\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs
Source: "..\prompts\golden\*"; DestDir: "{app}\prompts\golden"; Flags: recursesubdirs
Source: "..\schemas\*"; DestDir: "{app}\schemas"
Source: "..\tools\*"; DestDir: "{app}\tools"; Excludes: "bin\*,__pycache__\*"
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: recursesubdirs
Source: "..\start_geodoc.pyw"; DestDir: "{app}"
Source: "..\requirements.txt"; DestDir: "{app}"
Source: "..\README.md"; DestDir: "{app}"
; tekst licencji MIT pokazany w kreatorze — także na dysku, do wglądu offline
Source: "..\LICENSE"; DestDir: "{app}"
; python embeddable — PSF-podpisane binaria (zero fałszywych alarmów AV,
; w przeciwieństwie do PyInstallera — badanie #8164)
Source: "python-embed\*"; DestDir: "{app}\python-embed"; Flags: recursesubdirs
; llama.cpp CPU (runtime dispatch obsługuje każdy procesor); podkatalog
; z numerem buildu (llama-bin\b10155\) — pieczęć zapisuje go jako wersję silnika
Source: "llama-bin\*"; DestDir: "{app}\llama-bin"; Flags: recursesubdirs
; tray — punkt wejścia użytkownika (ikona + VersionInfo stemplowane w buildzie)
Source: "..\src-tauri\geodoc-tray.exe"; DestDir: "{app}\src-tauri"
; Konfiguracja: models.json (obie role → ten sam model 30B, ścieżki
; WZGLĘDNE rozwiązywane przez app/llm.py względem {app}) +
; models\manifest.json (kontrola integralności w launcherze).
Source: "manifesty\models-lekki.json"; DestDir: "{app}"; \
  DestName: "models.json"
Source: "manifesty\pack-lekki.json"; DestDir: "{app}\models"; \
  DestName: "manifest.json"
; MODEL ZBUNDLOWANY: GGUF wkompilowany w woluminy instalatora
; (nocompression — wagi nieściśliwe; kopiowanie = czysty zapis dysku).
; onlyifdoesntexist = aktualizacja aplikacji nie przepisuje 18,6 GB;
; naprawa uszkodzonego pliku (wykrywa launcher po sha256): usuń
; models\<plik>.gguf i uruchom instalator ponownie.
Source: "{#GgufDir}\{#Gguf30}"; \
  DestDir: "{app}\models"; Flags: nocompression onlyifdoesntexist

[Icons]
Name: "{autoprograms}\geodoc"; Filename: "{app}\{#AppExe}"; \
  WorkingDir: "{app}"; Comment: "Kontrola operatów technicznych"
Name: "{autodesktop}\geodoc"; Filename: "{app}\{#AppExe}"; \
  WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Uruchom geodoc"; \
  Flags: postinstall nowait skipifsilent

[UninstallDelete]
; katalogi tworzone w biegu przez aplikację (cache, logi) — dane
; użytkownika (jobs/, models/, profiles/, prompts\user/) zostają,
; chyba że operator zgodzi się w pytaniu poniżej
Type: filesandordirs; Name: "{app}\app\__pycache__"

[Code]
var
  StaryPack: String;
  MialModel: Boolean;

procedure CurStepChanged(CurStep: TSetupStep);
var
  S: AnsiString;
  Zmiana: Boolean;
begin
  // pełny sha256 w launcherze liczy się raz i jest buforowany znacznikiem
  // .verified — świeżo skopiowany model albo zmiana manifestu unieważnia
  // go, żeby najbliższy start policzył hash naprawdę
  if CurStep = ssInstall then
  begin
    if LoadStringFromFile(ExpandConstant('{app}\models\manifest.json'), S) then
      StaryPack := String(S)
    else
      StaryPack := '';
    MialModel := FileExists(ExpandConstant('{app}\models\{#Gguf30}'));
  end;
  if CurStep = ssPostInstall then
  begin
    Zmiana := False;
    if LoadStringFromFile(ExpandConstant('{app}\models\manifest.json'), S) then
      Zmiana := String(S) <> StaryPack;
    if not MialModel
       and FileExists(ExpandConstant('{app}\models\{#Gguf30}')) then
      Zmiana := True;
    if Zmiana then
      DeleteFile(ExpandConstant('{app}\models\.verified'));
  end;
end;

procedure UprzatnijProcesy();
var
  R: Integer;
  Cmd: String;
begin
  // drill 06.08: po awaryjnym zamknięciu tray'a konsola python.exe
  // przeżyła i BLOKOWAŁA kasowanie plików — deinstalator kończy pozostałe
  // procesy aplikacji spod {app} (tylko znane nazwy; nigdy własnego unins000)
  Cmd := '-NoProfile -Command "Get-CimInstance Win32_Process | ' +
         'Where-Object { $_.ExecutablePath -like ''' +
         ExpandConstant('{app}') + '\*'' -and $_.Name -in @(' +
         '''python.exe'',''pythonw.exe'',''geodoc-tray.exe'',' +
         '''llama-server.exe'') } | ForEach-Object { ' +
         'Stop-Process -Id $_.ProcessId -Force } "';
  Exec('powershell.exe', Cmd, '', SW_HIDE, ewWaitUntilTerminated, R);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    UprzatnijProcesy();
  if CurUninstallStep = usUninstall then
    // domyślnie ZACHOWAJ (przycisk NIE); usunięcie danych to świadoma
    // decyzja — wzorzec potwierdzony badaniem. MsgBox z [Code] NIE podlega
    // /SUPPRESSMSGBOXES i w cichej deinstalacji wisiałby w nieskończoność
    // (znalezisko E2E 11.08) — tryb cichy zachowuje dane bez pytania.
    if (not UninstallSilent) and (MsgBox('Czy usunąć również dane użytkownika?' + #13#10 + #13#10
              + 'Obejmuje to: przetworzone zadania (jobs), pakiet modeli, '
              + 'profile PODGiK oraz Twoje zmiany w instrukcjach agentów.'
              + #13#10 + 'Tej operacji nie można cofnąć.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    begin
      DelTree(ExpandConstant('{app}\jobs'), True, True, True);
      DelTree(ExpandConstant('{app}\models'), True, True, True);
      DelTree(ExpandConstant('{app}\profiles'), True, True, True);
      DelTree(ExpandConstant('{app}\prompts\user'), True, True, True);
      DelTree(ExpandConstant('{app}\contexts'), True, True, True);
      DelTree(ExpandConstant('{app}\uploads'), True, True, True);
    end;
end;
