from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({
            "status": "ok",
            "service": "dealframe",
            "message": "Vercel Python runtime is working",
        })
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        self.do_GET()
