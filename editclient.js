// editclient.js
// This script is written in WSH (Windows Scripting Host), and is intended to be
// used for older Windows versions that don't support PowerShell.

var fso = new ActiveXObject("Scripting.FileSystemObject");
var shell = new ActiveXObject("WScript.Shell");

var edit_server = "http://10.0.2.2:31416";

if (WScript.Arguments.Length < 1) {
    WScript.Echo("Usage: cscript //nologo editclient.js filename");
    WScript.Quit(1);
}

var fullPath = WScript.Arguments(0);
if (!fso.FileExists(fullPath)) {
    WScript.Echo("File not found: " + fullPath);
    WScript.Quit(1);
}

var fileObj = fso.GetFile(fullPath);
var fileName = fileObj.Name;

// URL encode just the filename
function urlEncode(str) {
    var result = "";
    for (var i = 0; i < str.length; i++) {
        var c = str.charCodeAt(i);
        if ((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) ||
            c == 45 || c == 46 || c == 95 || c == 126) {
            result += str.charAt(i);
        } else if (c == 32) {
            result += "+";
        } else {
            result += "%" + c.toString(16).toUpperCase();
        }
    }
    return result;
}

var encodedName = urlEncode(fileName);
var url = edit_server + "/edit?file=" + encodedName;

// Get ACP from registry
var acp = shell.RegRead("HKLM\\SYSTEM\\CurrentControlSet\\Control\\Nls\\CodePage\\ACP");

// Map common ACP numbers to ADODB charset names (add more if you switch locales often!)
var charsetMap = {
    "936": "gb2312",    // or "gbk" / "cp936" 鈥?all work on Win98 for GBK
    "950": "big5",
    "932": "shift_jis",
    "1252": "windows-1252",
    "1251": "windows-1251",
    "1250": "windows-1250",
    "874": "windows-874",
    "437": "ibm437"     // US default OEM, if needed
};

var localCharset = charsetMap[acp] || "windows-1252";  // fallback to Western European

// Step 1: Read local file in detected charset -> convert to UTF-8 bytes
var adoIn = new ActiveXObject("ADODB.Stream");
adoIn.Type = 2; // text
adoIn.Charset = localCharset;
adoIn.Open();
adoIn.LoadFromFile(fullPath);
var utf8Text = adoIn.ReadText();
adoIn.Close();

// Step 2: Send UTF-8 bytes to server
var xmlhttp = new ActiveXObject("MSXML2.XMLHTTP");
xmlhttp.open("POST", url, false);
xmlhttp.setRequestHeader("Content-Type", "text/plain");
xmlhttp.send(utf8Text);

if (xmlhttp.Status == 200) {
    var fileChanged = xmlhttp.getResponseHeader("X-File-Changed");
    if (fileChanged != "false") {
        var editedText = xmlhttp.responseText;

        // Step 3: Convert edited UTF-8 back to local charset and save
        var adoOut = new ActiveXObject("ADODB.Stream");
        adoOut.Type = 2; // text
        adoOut.Charset = localCharset;
        adoOut.Open();
        adoOut.WriteText(editedText);
        adoOut.SaveToFile(fullPath, 2); // overwrite
        adoOut.Close();
    }
}

WScript.Quit(0);
