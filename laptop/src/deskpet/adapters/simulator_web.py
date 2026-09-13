"""Loopback-only HTTP interface for the clickable virtual Pico."""

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

from deskpet.adapters.simulator import SimulatorDeviceLink

MAX_REQUEST_BYTES = 4_096


class SimulatorWebServer:
    """Serve the development UI without exposing it beyond this computer."""

    def __init__(self, simulator: SimulatorDeviceLink, port: int = 8765) -> None:
        self._simulator = simulator
        self._requested_port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        server = self._server
        return self._requested_port if server is None else int(server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("simulator web server is already started")
        server = ThreadingHTTPServer(
            ("127.0.0.1", self._requested_port), _handler_for(self._simulator)
        )
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="deskpet-simulator-web",
            daemon=True,
        )
        self._thread.start()
        print(f"Desk Pet simulator: {self.url}")

    def stop(self) -> None:
        server = self._server
        if server is None:
            return
        thread = self._thread
        if thread is None:
            server.server_close()
            self._server = None
            return
        server.shutdown()
        server.server_close()
        if thread is not threading.current_thread():
            thread.join(timeout=2)
        self._thread = None
        self._server = None


def _handler_for(simulator: SimulatorDeviceLink) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/":
                self._send(
                    HTTPStatus.OK,
                    SIMULATOR_HTML.encode(),
                    "text/html; charset=utf-8",
                )
            elif self.path == "/api/state":
                self._send_json(HTTPStatus.OK, simulator.state())
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()
                result = self._dispatch(payload)
            except (ValueError, KeyError) as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._send_json(HTTPStatus.OK, result)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _dispatch(self, payload: dict[str, object]) -> dict[str, object]:
            if self.path == "/api/connect":
                simulator.connect()
            elif self.path == "/api/disconnect":
                simulator.disconnect()
            elif self.path == "/api/reboot":
                simulator.reboot()
            elif self.path == "/api/press":
                button = _integer(payload, "button")
                gesture = _string(payload, "gesture")
                if not simulator.press(button, gesture):
                    raise ValueError("button unavailable until a view is connected")
            elif self.path == "/api/advance":
                simulator.advance(_integer(payload, "seconds"))
            elif self.path == "/api/inject":
                simulator.inject(_string(payload, "raw"))
            elif self.path == "/api/trace/clear":
                simulator.clear_trace()
            elif self.path == "/api/trace/pause":
                paused = payload.get("paused")
                if not isinstance(paused, bool):
                    raise ValueError("paused must be a boolean")
                simulator.pause_trace(paused)
            else:
                raise KeyError("not_found")
            return {"ok": True}

        def _read_json(self) -> dict[str, object]:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError as error:
                raise ValueError("invalid content length") from error
            if not 0 <= length <= MAX_REQUEST_BYTES:
                raise ValueError("request body is too large")
            raw = self.rfile.read(length)
            try:
                value = json.loads(raw or b"{}")
            except ValueError as error:
                raise ValueError("request body must be JSON") from error
            if not isinstance(value, dict):
                raise ValueError("request body must be an object")
            return cast(dict[str, object], value)

        def _send_json(self, status: HTTPStatus, value: object) -> None:
            self._send(
                status,
                json.dumps(value, separators=(",", ":")).encode(),
                "application/json",
            )

        def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _integer(value: dict[str, object], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool):
        raise ValueError(f"{key} must be an integer")
    return result


def _string(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ValueError(f"{key} must be a string")
    return result


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Desk Pet Simulator</title><style>
:root{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:#28231f;background:#f4ead7}body{margin:0;padding:24px}.layout{max-width:1100px;margin:auto;display:grid;grid-template-columns:360px 1fr;gap:24px}.card{background:#fffaf0;border:2px solid #443b33;border-radius:16px;padding:16px;box-shadow:5px 5px 0 #bca98d}.status{display:flex;justify-content:space-between;margin-bottom:12px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#c34}.dot.on{background:#3a5}.lcd{width:256px;height:320px;margin:auto;background:#172127;color:#f4efdf;border:14px solid #383838;border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;box-sizing:border-box;text-align:center}.pet{font-size:64px}.timer{font-size:44px}.mood{color:#f0bd58}.buttons{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}button,input{font:inherit}button{padding:9px;border:1px solid #443b33;border-radius:8px;background:#e8d7b8;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.trace{height:420px;overflow:auto;background:#171717;color:#ddd;padding:10px;border-radius:8px;font-size:12px}.entry{padding:4px 0;border-bottom:1px solid #333}.ok{color:#8bd49c}.bad{color:#ff8d86}.raw{white-space:pre-wrap;word-break:break-all;color:#bbb}input{padding:8px;min-width:80px}.wide{flex:1}@media(max-width:800px){.layout{grid-template-columns:1fr}}
</style></head><body><main class="layout"><section class="card"><div class="status"><strong>Simulated Pico</strong><span><i id="dot" class="dot"></i> <span id="connection">disconnected</span></span></div><div class="lcd"><div id="clock"></div><div id="pet" class="pet">=^.^=</div><div id="screen">Waiting for laptop</div><div id="timer" class="timer"></div><div id="mood" class="mood"></div><div id="feedback"></div></div><div id="buttons" class="buttons"></div><div class="row"><button onclick="post('/api/connect')">Connect</button><button onclick="post('/api/disconnect')">Disconnect</button><button onclick="post('/api/reboot')">Reboot</button></div><div class="row"><input id="seconds" type="number" min="0" max="3600" value="60"><button onclick="advance()">Advance seconds</button></div><div class="row"><input id="invalid" class="wide" value="{bad json"><button onclick="inject()">Inject line</button></div></section><section class="card"><div class="status"><strong>Bounded JSON trace</strong><span id="clockNow"></span></div><div class="row"><button onclick="post('/api/trace/clear')">Clear</button><button id="pause" onclick="togglePause()">Pause trace</button><button onclick="copyTrace()">Copy</button><button onclick="exportTrace()">Export</button></div><div id="trace" class="trace"></div></section></main><script>
let current={trace:[],trace_paused:false};async function post(path,data={}){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!response.ok){alert((await response.json()).error)}await refresh()}async function refresh(){current=await(await fetch('/api/state')).json();document.getElementById('dot').className='dot '+(current.connected?'on':'');document.getElementById('connection').textContent=current.connected?'connected':'disconnected';document.getElementById('clockNow').textContent=current.clock;document.getElementById('pause').textContent=current.trace_paused?'Resume trace':'Pause trace';const view=current.view;document.getElementById('screen').textContent=view?view.screen:'Waiting for laptop';document.getElementById('mood').textContent=view?'mood: '+view.mood:'';document.getElementById('clock').textContent=view?.clock_text||'';document.getElementById('timer').textContent=view?.timer_seconds==null?'':Math.floor(view.timer_seconds/60)+':'+String(view.timer_seconds%60).padStart(2,'0');document.getElementById('feedback').textContent=view?.feedback||'';document.getElementById('pet').textContent=view?.mood==='sad'?'=;.;=':view?.mood==='happy'?'=^o^=':'=^.^=';const buttons=document.getElementById('buttons');buttons.replaceChildren();for(const id of current.buttons){const b=view?.buttons.find(x=>x.button===id);const wrap=document.createElement('div');const press=document.createElement('button');press.textContent=(b?.label||'-')+' ['+id+']';press.disabled=!current.connected||!b?.enabled;press.onclick=()=>post('/api/press',{button:id,gesture:'press'});const hold=document.createElement('button');hold.textContent='Hold';hold.disabled=!current.connected||!b?.enabled;hold.onclick=()=>post('/api/press',{button:id,gesture:'hold'});wrap.append(press,hold);buttons.append(wrap)}const trace=document.getElementById('trace');trace.innerHTML=current.trace.map(e=>`<div class="entry"><span class="${e.accepted?'ok':'bad'}">${e.direction} · ${e.message_type||'-'} · ${e.result}</span><div class="raw"></div></div>`).join('');[...trace.querySelectorAll('.raw')].forEach((node,i)=>node.textContent=current.trace[i].raw);trace.scrollTop=trace.scrollHeight}function advance(){post('/api/advance',{seconds:Number(document.getElementById('seconds').value)})}function inject(){post('/api/inject',{raw:document.getElementById('invalid').value})}function togglePause(){post('/api/trace/pause',{paused:!current.trace_paused})}function copyTrace(){navigator.clipboard.writeText(current.trace.map(e=>JSON.stringify(e)).join('\n'))}function exportTrace(){const blob=new Blob([JSON.stringify(current.trace,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='deskpet-trace.json';a.click();URL.revokeObjectURL(a.href)}setInterval(refresh,250);refresh();
</script></body></html>"""


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError("simulator UI template does not match its transformations")
    return source.replace(old, new, 1)


# Keep the compact embedded page dependency-free while applying its behavioral
# transformations as checked, readable fragments.
_html = _replace_once(
    _HTML_TEMPLATE,
    '<div class="lcd"><div id="clock"></div>',
    '<div class="lcd"><div id="clock"></div><div id="progression"></div>'
    '<div id="settings"></div>',
)
_html = _replace_once(
    _html,
    "const hold=document.createElement('button');hold.textContent='Hold';"
    "hold.disabled=!current.connected||!b?.enabled;"
    "hold.onclick=()=>post('/api/press',{button:id,gesture:'hold'});"
    "wrap.append(press,hold);",
    "wrap.append(press);",
)
_html = _replace_once(
    _html,
    "document.getElementById('clock').textContent=view?.clock_text||'';",
    "document.getElementById('clock').textContent=view?.clock_text||'';"
    "const progression=view?.progression;"
    "document.getElementById('progression').textContent=progression?"
    "'Lv '+progression.level+' · XP '+progression.xp_into_level+'/' +"
    "progression.xp_for_next_level+' · '+progression.yarn_balance+' yarn':'';",
)
_html = _replace_once(
    _html,
    "document.getElementById('mood').textContent=view?'mood: '+view.mood:'';",
    "document.getElementById('mood').textContent=view?'mood: '+view.mood:'';"
    "const settings=view?.settings;"
    "document.getElementById('settings').innerText=settings?"
    "(settings.selected_row===0?'> ':'  ')+'Keyboard: '+"
    "(settings.keyboard_available?(settings.keyboard_enabled?'ON':'OFF'):'Unavailable')+'\\n'+"
    "(settings.selected_row===1?'> ':'  ')+'Camera: '+"
    "(settings.camera_available?(settings.camera_enabled?'ON':'OFF'):'Unavailable'):'';",
)
_html = _replace_once(
    _html,
    "press.onclick=()=>post('/api/press',{button:id,gesture:'press'});",
    "let holdTimer=null;let held=false;"
    "press.onpointerdown=()=>{held=false;holdTimer=setTimeout(()=>{held=true;"
    "post('/api/press',{button:id,gesture:'hold'})},600)};"
    "press.onpointerup=()=>{clearTimeout(holdTimer);if(!held)"
    "post('/api/press',{button:id,gesture:'press'})};"
    "press.onpointerleave=()=>clearTimeout(holdTimer);",
)
_html = _replace_once(
    _html,
    "document.getElementById('timer').textContent=view?.timer_seconds==null?'':"
    "Math.floor(view.timer_seconds/60)+':'+"
    "String(view.timer_seconds%60).padStart(2,'0');",
    "document.getElementById('timer').textContent=view?.focus_minutes!=null?"
    "view.focus_minutes+' min':view?.timer_seconds==null?'':"
    "Math.floor(view.timer_seconds/60)+':'+"
    "String(view.timer_seconds%60).padStart(2,'0');",
)
_html = _replace_once(
    _html,
    "document.getElementById('feedback').textContent=view?.feedback||'';",
    "document.getElementById('feedback').textContent=view?.feedback||"
    "(view?.focus_minutes!=null&&view?.break_minutes!=null?"
    "'break: '+view.break_minutes+' min':view?.earned_rewards?"
    "'earned: '+view.earned_rewards.xp+' XP · '+view.earned_rewards.yarn+' yarn':'');",
)
_html = _replace_once(
    _html,
    "const buttons=document.getElementById('buttons');buttons.replaceChildren();"
    "for(const id of current.buttons){",
    "const buttons=document.getElementById('buttons');"
    "const buttonSignature=JSON.stringify([current.connected,current.buttons,"
    "view?.buttons]);if(buttons.dataset.signature!==buttonSignature){"
    "buttons.dataset.signature=buttonSignature;buttons.replaceChildren();"
    "for(const id of current.buttons){",
)
_html = _replace_once(
    _html,
    "wrap.append(press);buttons.append(wrap)}const trace=",
    "wrap.append(press);buttons.append(wrap)}}const trace=",
)
_html = _replace_once(
    _html,
    "const trace=document.getElementById('trace');trace.innerHTML=",
    "const trace=document.getElementById('trace');"
    "const stickToBottom=!current.trace_paused&&"
    "trace.scrollHeight-trace.scrollTop-trace.clientHeight<80;trace.innerHTML=",
)
_html = _replace_once(
    _html,
    "trace.scrollTop=trace.scrollHeight}function advance()",
    "if(stickToBottom)trace.scrollTop=trace.scrollHeight}function advance()",
)
SIMULATOR_HTML = _html
