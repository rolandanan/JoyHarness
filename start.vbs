Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
python = root & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(python) Then python = "pythonw"
shell.Run """" & python & """ -m src", 0, False
