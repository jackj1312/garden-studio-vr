#!/usr/bin/env python3
"""Serve this folder over HTTPS on the home network, so the Quest can open a
private build (WebXR needs a secure origin). Self-signed: the headset shows a
warning once — Advanced, then Proceed. Nothing here is reachable from outside
the wifi.

    python3 tools/https-serve.py [port]       # default 8443
"""
import http.server, ssl, os, sys, functools
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
cert = os.path.expanduser("~/.garden-vr-cert")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(os.path.join(cert, "cert.pem"), os.path.join(cert, "key.pem"))
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
print(f"https://0.0.0.0:{port}/", flush=True)
httpd.serve_forever()
