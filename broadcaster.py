"""
broadcaster.py — Serves the current time to browsers every 5 seconds.
 
- HTTP  :8080/          -> the browser UI (single-page app)
- HTTP  :8080/events    -> Server-Sent Events stream (one per browser tab)
"""
 
import threading
import time
import queue
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
 
# Shared state
subscriber_queues: list[queue.Queue] = []
subscriber_lock = threading.Lock()
latest_time = "Waiting for first broadcast..."
 
 
# Threaded server (fixes liveness probe crash loop)
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
 
 
# Broadcaster thread
def broadcast() -> None:
    """Stamps the time and pushes it to every open browser tab on 5 sec interval."""
    global latest_time
    while True:
        time.sleep(5)
        curr_time = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        latest_time = curr_time
        print(f"[BROADCAST] {curr_time}")
        with subscriber_lock:
            for q in subscriber_queues:
                q.put(curr_time)
 
 
# Browser UI (single-page app, no external dependencies)
HTML_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Live Time Broadcaster</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: #0f1117;
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: #e2e8f0;
    }
    h1 {
      font-size: 1rem;
      font-weight: 500;
      letter-spacing: .18em;
      text-transform: uppercase;
      color: #475569;
      margin-bottom: 2.5rem;
    }
    #clock {
      font-size: clamp(2.8rem, 9vw, 5.5rem);
      font-weight: 700;
      letter-spacing: .06em;
      color: #38bdf8;
      text-shadow: 0 0 48px rgba(56,189,248,.4);
      transition: opacity .2s ease;
    }
    #status {
      margin-top: 1.75rem;
      display: flex;
      align-items: center;
      gap: .55rem;
      font-size: .78rem;
      color: #475569;
    }
    #dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #22c55e;
      animation: pulse 2s infinite;
    }
    #dot.disconnected { background: #ef4444; animation: none; }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.25; } }
    #history { margin-top: 3rem; width: min(480px, 90vw); }
    #history h2 {
      font-size: .7rem;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: #334155;
      margin-bottom: .8rem;
    }
    #history ul { list-style: none; display: flex; flex-direction: column; gap: .4rem; }
    #history li {
      background: #1e293b;
      border-radius: 6px;
      padding: .5rem .8rem;
      font-size: .85rem;
      color: #94a3b8;
      opacity: 0;
      animation: fadeIn .35s forwards;
    }
    @keyframes fadeIn { to { opacity:1; } }
  </style>
</head>
<body>
  <h1>&#128339; Live Time Broadcaster</h1>
  <div id="clock">connecting...</div>
  <div id="status">
    <div id="dot" class="disconnected"></div>
    <span id="status-text">Connecting...</span>
  </div>
  <div id="history">
    <h2>Recent broadcasts</h2>
    <ul id="history-list"></ul>
  </div>
  <script>
    const clock      = document.getElementById('clock');
    const dot        = document.getElementById('dot');
    const statusText = document.getElementById('status-text');
    const histList   = document.getElementById('history-list');
    const MAX_HIST   = 5;
 
    const es = new EventSource('/events');
 
    es.onopen = () => {
      dot.classList.remove('disconnected');
      statusText.textContent = 'Connected — updates every 5 s';
    };
    es.onmessage = ({ data }) => {
      clock.style.opacity = '0';
      setTimeout(() => { clock.textContent = data; clock.style.opacity = '1'; }, 180);
      const li = document.createElement('li');
      li.textContent = data;
      histList.prepend(li);
      while (histList.children.length > MAX_HIST) histList.removeChild(histList.lastChild);
    };
    es.onerror = () => {
      dot.classList.add('disconnected');
      statusText.textContent = 'Connection lost — retrying...';
    };
  </script>
</body>
</html>
"""
 
 
# HTTP handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default noise; we do our own logging
 
    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/events":
            self._serve_sse()
        else:
            self.send_error(404)
 
    def _serve_html(self):
        body = HTML_PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        print(f"[HTTP] {self.client_address[0]} loaded the page")
 
    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        print(f"[SSE ] {self.client_address[0]} subscribed")
 
        q: queue.Queue = queue.Queue()
        with subscriber_lock:
            subscriber_queues.append(q)
 
        try:
            self.wfile.write(f"data: {latest_time}\n\n".encode())
            self.wfile.flush()
        except Exception:
            pass
 
        try:
            while True:
                try:
                    ts = q.get(timeout=25)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(f"data: {ts}\n\n".encode())
                self.wfile.flush()
                print(f"[SSE ] -> {self.client_address[0]}  {ts}")
        except (BrokenPipeError, ConnectionResetError):
            print(f"[SSE ] {self.client_address[0]} disconnected")
        finally:
            with subscriber_lock:
                subscriber_queues.remove(q)
 
 
# Entry point
def main():
    host = "0.0.0.0"
    web_port = 8080
 
    t = threading.Thread(target=broadcast, daemon=True)
    t.start()
 
    server = ThreadedHTTPServer((host, web_port), Handler)
    print("Broadcaster running!")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
 
 
if __name__ == "__main__":
    main()