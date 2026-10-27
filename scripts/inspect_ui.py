import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading
import time
from start_app import run_fastapi_server, find_free_port
import webview

port = find_free_port()
t = threading.Thread(target=run_fastapi_server, args=(port,), daemon=True)
t.start()
time.sleep(1.5)

url = f"http://127.0.0.1:{port}"

def check_window(w):
    time.sleep(2.0)
    res = w.evaluate_js("""
    (function() {
        var link = document.querySelector('link[rel="stylesheet"]');
        return {
            linkHref: link ? link.href : null,
            sheet: link && link.sheet ? 'EXISTS' : 'NULL_OR_BLOCKED',
            allSheets: Array.from(document.styleSheets).map(s => {
                var txt = '';
                try {
                    txt = Array.from(s.cssRules).map(r => r.cssText).slice(0, 3).join(' | ');
                } catch(e) {
                    txt = 'ACCESS_ERROR: ' + e.message;
                }
                return { href: s.href, preview: txt };
            })
        };
    })()
    """)
    print("DETAILED CSS INSPECTION:")
    print(res)
    w.destroy()

window = webview.create_window("Test", url=url, width=800, height=600)
threading.Thread(target=check_window, args=(window,), daemon=True).start()
webview.start(debug=False)
