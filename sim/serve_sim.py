"""Serve the SPIKE folder locally and open the rover simulator.

The simulator page reads ../spike_all_in_one.py fresh on every Run. Browsers
only allow that over http, not from a page opened straight from disk, hence
this tiny server. Run it from anywhere:

    python sim/serve_sim.py

Ctrl+C stops it. Nothing here is uploaded to the hub.
"""
import functools
import http.server
import os
import socketserver
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Always serve the latest saved file, never a cached copy.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass    # keep the terminal quiet


if __name__ == "__main__":
    handler = functools.partial(Handler, directory=ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        url = "http://127.0.0.1:%d/sim/rover_sim.html" % PORT
        print("Serving %s at %s - Ctrl+C to stop" % (ROOT, url))
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
