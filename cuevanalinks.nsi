SetCompressor /solid lzma
XPStyle on

!include EnvVarUpdate.nsh

Page license
Page directory
Page instfiles

RequestExecutionLevel admin

# set license page
LicenseText ""
LicenseData "LICENSE.txt"
LicenseForceSelection checkbox

Name "CuevanaLinks ${VERSION}"
OutFile "cuevanalinks-${VERSION}-installer.exe"
InstallDir "$PROGRAMFILES\CuevanaLinks"
InstallDirRegKey HKLM "Software\CuevanaLinks" "Install_Dir"

Section "Install"  
    SectionIn RO
    SetOutPath $INSTDIR
    File /r dist\*.*
    WriteRegStr HKLM "Software\CuevanaLinks" "Install_Dir" "$INSTDIR"
    WriteUninstaller "$INSTDIR\uninstall.exe"
    ${EnvVarUpdate} $0 "PATH" "A" "HKLM" "$INSTDIR"  #set instdir in env path
SectionEnd

Section "Shortcuts"
    CreateDirectory "$SMPROGRAMS\CuevanaLinks"
    CreateShortCut "$SMPROGRAMS\CuevanaLinks\CuevanaLinks.lnk" "$INSTDIR\cuevanalinks.exe" "" "$INSTDIR\cuevanalinks.exe"
    CreateShortCut "$SMPROGRAMS\CuevanaLinks\CuevanaLinks-GUI.lnk" "$INSTDIR\cuevanalinks-gui.exe" "" "$INSTDIR\cuevanalinks-gui.exe"
    CreateShortCut "$SMPROGRAMS\CuevanaLinks\uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\uninstall.exe"
    RMDir /r $INSTDIR
    RMDir /r "$PROFILE\CuevanaLinks\"
    RMDir /r "$SMPROGRAMS\CuevanaLinks"
    #Delete "$DESKTOP\CuevanaLinks.lnk"
    ${un.EnvVarUpdate} $0 "LIB" "R" "HKLM" "$INSTDIR"
    DeleteRegKey HKLM "Software\CuevanaLinks"
SectionEnd