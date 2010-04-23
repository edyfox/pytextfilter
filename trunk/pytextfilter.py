#!/usr/bin/env python
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

import BaseHTTPServer
import SocketServer
import cgi
import os
import shutil
import tempfile

import filename_filter
from config import config

class EditServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  """An HTTP server that handles text filter requests"""

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
      self.end_headers()
      self.wfile.write(content)
    except:
      pass

  def do_POST(self):
    # Create the temp directory.
    tempdir = tempfile.mkdtemp(
        prefix = "edit-server-",
        dir = config["environment"]["tmpdir"])

    params = {}

    # Check x-id and x-url to keep compatible with emacs_chrome.
    id = self.headers.getheader("x-id")
    if id != None:
      params["id"] = id
    url = self.headers.getheader("x-url")
    if url != None:
      params["url"] = url

    # Extract the parameters from the query string.
    query = self.path.split("?", 1)
    if len(query) > 1:
      qs = cgi.parse_qs(query[1])
      for i in qs:
        params[i] = qs[i][-1]

    # Get the temp filename.
    filename = filename_filter.GetFilename(params)
    filename = filename.replace("/", "").replace("\\", "")
    tempname =  tempdir + os.sep + filename

    # Write the temp file.
    try:
      temp = file(tempname, "w")
      temp.write(
          self.rfile.read(int(self.headers.getheader("content-length"))))
      temp.close()
    except:
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
      os.spawnvp(os.P_WAIT, params[0], params)
    except:
      self.__cleanup(tempdir)
      self.__error()
      return

    # Read the edited file.
    try:
      temp = file(tempname, "r")
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
      self.send_header("Content-length", len(content))
      self.end_headers()
      self.wfile.write(content)
    except :
      self.__cleanup(tempdir)
      self.__error()
      return

    self.__cleanup(tempdir)

class ThreadedHTTPServer(
    SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
  """Handle requests in a separate thread."""

def main():
  try:
    server = ThreadedHTTPServer(
        ("127.0.0.1", config["server"]["port"]),
        EditServerHandler)
    print "Text filter server started..."
    server.serve_forever()
  except KeyboardInterrupt:
    print "Shutting down text filter server..."
    server.socket.close()

if __name__ == "__main__":
  main()
