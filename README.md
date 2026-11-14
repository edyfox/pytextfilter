# pyTextFilter

pyTextFilter is a tool that allows you to edit text files on a remote machine
using your favorite local text editor.

## Project History & Status

This project was originally inspired by
[TextEditAid](https://chrome.google.com/webstore/detail/textaid/ppoadiihggafnhokfkpphojggcdigllp),
a now-defunct Google Chrome extension that allowed editing textarea contents in
an external editor.
> [!NOTE] 
> The TextEditAid extension is no longer maintained or available. **This project
> is no longer relevant to that extension.**

Today, pyTextFilter is a standalone utility for seamless remote text editing.

## How It Works

The system consists of a local server and a remote client:
1.  **Remote Client**: You run a script (`edit-client` or `editclient.js`) on
    the remote machine (e.g., via SSH or in a VM).
2.  **Send**: The client sends the file content to the `pytextfilter` server
    running on your local machine.
3.  **Edit**: The local server spawns your configured text editor with the
    content.
4.  **Update**: Once you save and close the editor, the modified content is sent
    back to the remote client.
5.  **Overwrite**: The remote client overwrites the original file with the
    changes.

## Components

*   **Server**: `pytextfilter.py` (Runs on your local machine)
*   **Linux Client**: `edit-client` (Shell script for Linux SSH servers)
*   **Legacy Windows Client**: `editclient.js` (WSH script for older Windows
    versions, e.g., Windows 98, where PowerShell is unavailable)

## Networking & Security Recommendations

> [!IMPORTANT]
> **No Authentication**: `pytextfilter` involves NO permission checks or access
> control. Anyone who can connect to the port can read/write files through your
> editor.

### Listening Interface
It is strongly recommended to configure `pytextfilter` to listen **only** on
`127.0.0.1` (localhost). **Do not** configure it to listen on `0.0.0.0` (all
interfaces) unless you completely trust the network.

### Browser pages (CORS)

A page in a browser cannot talk to `127.0.0.1:31416` directly, and it is not a
setting you can flip in the page: the reply is cross-origin, so the browser
refuses to let the page read it unless the server sends `Access-Control-Allow-*`,
and a custom header or a JSON body additionally triggers a preflight `OPTIONS`
request, which `http.server` answers with `501 Unsupported method ('OPTIONS')`.

pyTextFilter now supports this, opt-in and off by default. Add the origins you
want to allow to `config["server"]["cors"]` (see `config.py.sample`):

```python
"cors": ["http://127.0.0.1:8080"]
```

*   Accepted values: `True` or `"*"` (any origin, echoed back), a single origin
    string, or a list of origins. An origin not in the list gets no
    `Access-Control-Allow-Origin`, so the browser blocks it.
*   A `*` **inside** an entry matches any run of characters, so
    `"cors": ["http://localhost:*"]` admits every port on localhost — what a dev
    server needs, since its port changes per project. A browser omits the default
    port entirely, and `host:*` admits that form too.
*   Hosts are **never aliased**. `localhost` and `127.0.0.1` are different origins,
    and on ChromeOS they can even resolve to different machines (the browser's
    localhost is not a Linux container's), so list each one you actually use:
    `["http://localhost:*", "http://127.0.0.1:*"]`.
*   Leave the key out and **nothing changes**: `OPTIONS` still answers `501` and
    no CORS header is sent, exactly like the stock server.
*   The restart matters: `config` is imported once, so a running server keeps the
    value it started with.
*   Prefer an allow-list over `True`. "Any origin" means any page you visit can
    post text to your editor — and this server has no authentication at all.

```bash
# what the browser asks before a POST, and what it should now get back
curl -si -X OPTIONS -H 'Origin: http://127.0.0.1:8080' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' \
  http://127.0.0.1:31416/ | grep -i access-control
```

### Connecting from Remote Linux (SSH)
Since the server listens on `127.0.0.1`, you need to forward the port so the
remote client can reach your local machine.

*   **SSH Remote Forwarding**: Use the `-R` option (or `RemoteForward` in
    `~/.ssh/config`) to map the remote's port 31416 back to your local port
    31416.
    *   Command: `ssh -R 31416:127.0.0.1:31416 user@hostname`
    *   Config: Add `RemoteForward 31416 127.0.0.1:31416` to your host
        configuration.

### Connecting from Windows VMs (QEMU)
If you are using QEMU with **User Mode Networking** to run Windows (e.g.,
Windows 98), the guest OS shares the host's network stack. You usually do not
need special port forwarding; the guest can often access the host IP directly,
or if using `hostfwd`, configuration varies.
*   However, if the guest sees the host as a gateway (often `10.0.2.2` in QEMU
    user networking), `editclient.js` should point to that IP.
*   *Note*: `editclient.js` in the repo has `var edit_server =
    "http://10.0.2.2:31416";`, which matches the QEMU default gateway address.

## Usage

1.  **Start Server**: Run `./pytextfilter.py` on your local machine.
2.  **Connect**: SSH to your remote server or open your Windows VM.
3.  **Edit**:
    *   **Linux**: `edit-client filename.txt`
    *   **Windows**: `cscript //nologo editclient.js filename.txt`

## Windows Context Menu Integration

To make it easier to launch the editor from Windows Explorer, you can add a
context menu item. Save the following content as a `.reg` file (e.g.,
`install_context_menu.reg`) and double-click to import it.

This adds an **"Open with Edit Client"** option to right-clicking any file.

```registry
REGEDIT4

[HKEY_CLASSES_ROOT\*\shell\editclient]
@="Open with Edit &Client"

[HKEY_CLASSES_ROOT\*\shell\editclient\command]
@="wscript C:\\Windows\\editclient.js \"%1\""
```

> [!NOTE]
> This registry script assumes you have placed `editclient.js` inside
> `C:\Windows\`. If you place it elsewhere, update the path in the script
> accordingly.
