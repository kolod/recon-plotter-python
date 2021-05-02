﻿Unicode True

!include MUI2.nsh
!include FileFunc.nsh
!include EnumUsersReg.nsh

!define MUI_ICON "..\Recon Plotter\Icon.ico"
!define MUI_UNICON "..\Recon Plotter\Icon.ico"

!getdllversion "..\Recon Plotter\Recon Plotter.exe" ver
!define VERSION "${ver1}.${ver2}.${ver3}.${ver4}"

VIProductVersion "${VERSION}"
VIAddVersionKey "ProductName" "Recon Plotter"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "(C) Oleksandr Kolodkin"
VIAddVersionKey "FileDescription" "Recon Plotter"

;--------------------------------
;Perform Machine-level install, if possible

!define MULTIUSER_EXECUTIONLEVEL Highest
;Add support for command-line args that let uninstaller know whether to
;uninstall machine- or user installation:
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!include MultiUser.nsh
!include LogicLib.nsh

Function .onInit
  !insertmacro MULTIUSER_INIT
  ;Do not use InstallDir at all so we can detect empty $InstDir!
  ${If} $InstDir == "" ; /D not used
      SetRegView 64
      ${If} $MultiUser.InstallMode == "AllUsers"
          StrCpy $InstDir "$PROGRAMFILES64\Recon Plotter"
      ${Else}
          StrCpy $InstDir "$LOCALAPPDATA\Recon Plotter"
      ${EndIf}
  ${EndIf}
FunctionEnd

Function un.onInit
  !insertmacro MULTIUSER_UNINIT
FunctionEnd

;--------------------------------
;General

  Name "Recon Plotter"
  OutFile "..\Recon PlotterSetup.exe"

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of Recon Plotter.$\r$\n$\r$\n$\r$\nClick Next to continue."
  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
    !define MUI_FINISHPAGE_NOAUTOCLOSE
    !define MUI_FINISHPAGE_RUN
    !define MUI_FINISHPAGE_RUN_CHECKED
    !define MUI_FINISHPAGE_RUN_TEXT "Run Recon Plotter"
    !define MUI_FINISHPAGE_RUN_FUNCTION "LaunchLink"
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
;Languages

  !insertmacro MUI_LANGUAGE "English"
  !insertmacro MUI_LANGUAGE "Russian"
  !insertmacro MUI_LANGUAGE "Ukrainian"

;--------------------------------
;Installer Sections

!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Recon Plotter"
Section
  SetOutPath "$InstDir"
  File /r "..\Recon Plotter\*"
  WriteRegStr SHCTX "Software\Recon Plotter" "" $InstDir
  WriteUninstaller "$InstDir\uninstall.exe"
  CreateShortCut "$SMPROGRAMS\Recon Plotter.lnk" "$InstDir\Recon Plotter.exe"
  WriteRegStr SHCTX "${UNINST_KEY}" "DisplayName" "Recon Plotter"
  WriteRegStr SHCTX "${UNINST_KEY}" "UninstallString" "$\"$InstDir\uninstall.exe$\" /$MultiUser.InstallMode"
  WriteRegStr SHCTX "${UNINST_KEY}" "QuietUninstallString" "$\"$InstDir\uninstall.exe$\" /$MultiUser.InstallMode /S"
  WriteRegStr SHCTX "${UNINST_KEY}" "Publisher" "Oleksandr Kolodkin"
  WriteRegStr SHCTX "${UNINST_KEY}" "DisplayIcon" "$InstDir\uninstall.exe"
  ${GetSize} "$InstDir" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD SHCTX "${UNINST_KEY}" "EstimatedSize" "$0"

SectionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  RMDir /r "$InstDir"
  RMDir /r "$LOCALAPPDATA\Oleksandr Kolodkin\Recon Plotter"
  Delete "$SMPROGRAMS\Recon Plotter.lnk"
  DeleteRegKey /ifempty SHCTX "Software\Recon Plotter"
  DeleteRegKey SHCTX "${UNINST_KEY}"
  
  # Remove programm settings for all users
  !insertmacro ENUM_USERS_REG un.RemoveUserSettings temp

SectionEnd

Function LaunchLink
  !addplugindir "."
  ShellExecAsUser::ShellExecAsUser "open" "$SMPROGRAMS\Recon Plotter.lnk"
FunctionEnd

Function un.RemoveUserSettings
  Pop $0
  DeleteRegKey HKU "$0\SOFTWARE\Oleksandr Kolodkin\Recon Plotter"
  DetailPrint "Removed registry key: $0\SOFTWARE\Oleksandr Kolodkin\Recon Plotter"
FunctionEnd
