; DropPoint+ NSIS installer
; Wraps dist/DropPointPlus/ (PyInstaller onedir output) into a setup.exe.
;
; Build (after `pyinstaller --noconfirm DropPointPlus.spec`):
;     makensis installer.nsi
; Produces DropPointPlus-Setup.exe in the current directory.

!define APPNAME "DropPoint+"
!define COMPANYNAME "DropPointPlus"
!define DESCRIPTION "Make drag and drop easier — a floating shelf for files"
!define VERSION "0.4.0"
!define OUTPUT "DropPointPlus-Setup-${VERSION}.exe"

; The PyInstaller onedir output to bundle (relative to this script).
!define BUNDLE_DIR "..\..\dist\DropPointPlus"

Name "${APPNAME}"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\DropPointPlus"
RequestExecutionLevel user          ; per-user install — no admin prompt
Unicode True
SetCompressor /SOLID lzma

!include "MUI2.nsh"

!define MUI_ICON "..\..\droppointplus\resources\icons\droppoint.ico"
!define MUI_UNICON "..\..\droppointplus\resources\icons\droppoint.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"

  ; Copy the whole PyInstaller onedir (exe + _internal) preserving layout.
  File /r "${BUNDLE_DIR}\*.*"

  ; Shortcuts.
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\DropPointPlus.exe"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\DropPointPlus.exe"

  ; Registry: uninstall entry + app path.
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\${COMPANYNAME}\${APPNAME}" "" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "Publisher" "${COMPANYNAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayIcon" "$INSTDIR\DropPointPlus.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "NoRepair" 1
SectionEnd

Section "Uninstall"
  ; Remove shortcuts and the install directory (including _internal).
  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  Delete "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk"
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"

  ; The app writes its config under %APPDATA%, not $INSTDIR — leave that alone.
  RMDir /r "$INSTDIR"

  DeleteRegKey HKCU "Software\${COMPANYNAME}\${APPNAME}"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
SectionEnd
