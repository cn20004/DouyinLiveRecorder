Unicode True
!include "MUI2.nsh"
Name "郑老师魔改版 · 抖音直播录制 v1.1.0"
OutFile "Zhenglaoshi-DouyinLive-Setup-v1.1.0.exe"
InstallDir "$LOCALAPPDATA\Zhenglaoshi-DouyinLive"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\Zhenglaoshi-DouyinLive-v1.1.0.exe"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
Section "Program"
  SetOutPath "$INSTDIR"
  File /r /x config /x data /x downloads /x backup_config /x logs /x exports "package\*"
  SetOverwrite off
  File /r "package\config"
  SetOverwrite on
  CreateDirectory "$INSTDIR\downloads"
  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\backup_config"
  CreateShortcut "$DESKTOP\郑老师抖音直播录制.lnk" "$INSTDIR\Zhenglaoshi-DouyinLive-v1.1.0.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd
Section "Uninstall"
  Delete "$DESKTOP\郑老师抖音直播录制.lnk"
  Delete "$INSTDIR\Zhenglaoshi-DouyinLive-v1.1.0.exe"
  Delete "$INSTDIR\DouyinLiveRecorder-Core.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\ffmpeg"
  RMDir /r "$INSTDIR\src"
  RMDir "$INSTDIR"
SectionEnd
