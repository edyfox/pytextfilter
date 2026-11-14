#!/usr/bin/env python3
#
# Copyright 2010 Edward Leap Fox (edyfox@gmail.com).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import http.server
import socketserver
import urllib.parse
import os
import shutil
import subprocess
import tempfile
import hashlib

import filename_filter
from config import config

class EditServerHandler(http.server.BaseHTTPRequestHandler):
  """An HTTP server that handles text filter requests"""

  # --- jsbarevi CORS begin ---
  def __allowed_origins(self):
    """Return the configured allow-list, True for any origin, or None."""
    try:
      setting = config["server"].get("cors", False)
    except Exception:
      return None
    if setting is True or setting == "*":
      return True
    if isinstance(setting, str):
      setting = [setting]
    if isinstance(setting, (list, tuple, set)):
      entries = [o.rstrip("/") for o in setting if isinstance(o, str)]
      return [o for o in entries if o] or None
    return None

  def __origin_allowed(self, origin, allowed):
    """Does this request's Origin match an entry?

    An entry is an origin, and a `*` inside it matches any run of characters, so
    "http://localhost:*" admits every port on localhost. Hosts are NOT aliased:
    "localhost" and "127.0.0.1" are different origins to a browser (and on ChromeOS
    they are not even the same network path), so list each one you want.
    """
    import re
    if allowed is True:
      return True
    if not origin:
      return False
    for pattern in allowed:
      # "host:*" also has to admit the DEFAULT port, which a browser omits entirely.
      forms = (pattern, pattern[:-2]) if pattern.endswith(":*") else (pattern,)
      for form in forms:
        if origin.lower() == form.lower():
          return True
        if "*" not in form:
          continue
        rx = "^" + ".*".join(re.escape(part) for part in form.split("*")) + "$"
        if re.match(rx, origin, re.IGNORECASE):
          return True
    return False

  def __cors(self):
    """Send CORS headers when config["server"]["cors"] permits this origin."""
    allowed = self.__allowed_origins()
    if not allowed:
      return
    origin = self.headers.get("Origin", "")
    if self.__origin_allowed(origin, allowed):
      # Echo the request's own origin rather than "*": a wildcard answer cannot carry
      # credentials, and an exact echo is accepted everywhere.
      self.send_header("Access-Control-Allow-Origin", origin or "*")
    else:
      self.send_header("Vary", "Origin")
      return
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    # Every request header the transport can send, or the preflight rejects it: the
    # token is real (X-Edit-Token) and only appears when a session configures one.
    self.send_header("Access-Control-Allow-Headers",
                     "content-type, x-url, x-id, authorization, x-edit-token")
    self.send_header("Access-Control-Max-Age", "600")
    self.send_header("Vary", "Origin")

  def do_OPTIONS(self):
    """Answer the CORS preflight — when CORS is enabled, that is.

    With `cors` unset this answers exactly what the stock server answers (501), so
    installing the patch on a server nobody configured is a true no-op rather than a
    subtle behaviour change.
    """
    if not self.__allowed_origins():
      self.send_error(501, "Unsupported method (%r)" % self.command)
      return
    self.send_response(204)
    self.__cors()
    self.send_header("Content-length", "0")
    self.end_headers()
  # --- jsbarevi CORS end ---

  def do_GET(self):
    try:
      if self.path.endswith("/favicon.ico"):
        self.send_response(404)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write("File not found.")
      else:
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.__cors()
        self.end_headers()
        self.wfile.write(
            "Server is up and running.  " +
            "To use it, issue a POST request with the file to edit " +
            "as the content body.")
    except:
      # Swallow the exceptions.
      pass

  def __cleanup(self, tempdir):
    try:
      shutil.rmtree(tempdir)
    except:
      pass

  def __error(self):
    try:
      content = "Invalid request"
      self.send_response(500)
      self.send_header("Content-length", len(content))
      self.send_header("Content-type", "text/plain")
      self.__cors()
      self.end_headers()
      self.wfile.write(content)
    except:
      pass

  def do_POST(self):
    # Create the temp directory.
    try:
      tempdir = tempfile.mkdtemp(
          prefix = "edit-server-",
          dir = config["environment"]["tmpdir"])
    except:
      self.__error()
      return

    params = {}

    # Check x-id and x-url to keep compatible with emacs_chrome.
    id = self.headers.get("x-id")
    if id != None:
      params["id"] = id
    url = self.headers.get("x-url")
    if url != None:
      params["url"] = url

    # Extract the parameters from the query string.
    query = self.path.split("?", 1)
    if len(query) > 1:
      qs = urllib.parse.parse_qs(query[1])
      for i in qs:
        params[i] = qs[i][-1]

    # Get the temp filename.
    filename = filename_filter.GetFilename(params)
    filename = filename.replace("/", "").replace("\\", "").replace(os.sep, "")
    tempname =  tempdir + os.sep + filename

    # Write the temp file.
    temp = None
    try:
      temp = open(tempname, "wb")
      content = self.rfile.read(int(self.headers.get("content-length")))
      original_hash = hashlib.sha256(content).hexdigest()
      temp.write(content)
      temp.close()
    except:
      if temp:
        temp.close()
      self.__cleanup(tempdir)
      self.__error()
      return

    # Launch the text editor.
    params = []
    for i in config["environment"]["editor"]:
      if i == "%s":
        params.append(tempname)
      else:
        params.append(i)

    try:
      subprocess.call(params)
    except:
      self.__cleanup(tempdir)
      self.__error()
      return

    # Read the edited file.
    try:
      temp = open(tempname, "rb")
      content = temp.read()
      temp.close()
    except:
      self.__cleanup(tempdir)
      self.__error()
      return

    # Write the response.
    try:
      self.send_response(200)
      self.send_header("Content-type", "text/plain")
      self.__cors()
      self.send_header("Content-length", len(content))
      new_hash = hashlib.sha256(content).hexdigest()
      if original_hash == new_hash:
        self.send_header("X-File-Changed", "false")
      else:
        self.send_header("X-File-Changed", "true")
      self.end_headers()
      self.wfile.write(content)
    except :
      self.__cleanup(tempdir)
      self.__error()
      return

    self.__cleanup(tempdir)

class ThreadedHTTPServer(
    socketserver.ThreadingMixIn, http.server.HTTPServer):
  """Handle requests in a separate thread."""

def main():
  try:
    server = ThreadedHTTPServer(
        (config["server"]["interface"], config["server"]["port"]),
        EditServerHandler)
    print("Text filter server started...")
    server.serve_forever()
  except KeyboardInterrupt:
    print("Shutting down text filter server...")
    server.socket.close()

if __name__ == "__main__":
  main()
