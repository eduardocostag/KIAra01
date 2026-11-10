Option Explicit

Dim scriptPath, command
If WScript.Arguments.Count <> 1 Then
  WScript.Quit 2
End If

scriptPath = WScript.Arguments(0)
command = "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptPath & """"
CreateObject("WScript.Shell").Run command, 0, False
