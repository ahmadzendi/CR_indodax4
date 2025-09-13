import asyncio
import websockets
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from datetime import datetime
import time
import os

TOKEN = os.getenv("TOKEN")
active_connections = set()
history = []
chat_timestamps = []

async def indodax_ws_listener():
    uri = "wss://chat-ws.indodax.com/ws/"
    while True:
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"params": {"token": TOKEN}, "id": 6}))
                await ws.recv()
                await ws.send(json.dumps({"method": 1, "params": {"channel": "chatroom_indodax"}, "id": 7}))
                await ws.recv()
                while True:
                    msg = await ws.recv()
                    try:
                        data = json.loads(msg)
                        if data.get("result", {}).get("channel") == "chatroom_indodax":
                            chat = data["result"]["data"]["data"]
                            WIB_OFFSET = 7 * 3600
                            ts = chat["timestamp"]
                            chat["timestamp_wib"] = datetime.utcfromtimestamp(ts + WIB_OFFSET).strftime('%Y-%m-%d %H:%M:%S')
                            history.append(chat)
                            history[:] = history[-1000:]
                            chat_timestamps.append(time.time())
                            now = time.time()
                            chat_timestamps[:] = [t for t in chat_timestamps if now - t <= 60]
                            for client in list(active_connections):
                                try:
                                    await client.send_text(json.dumps({"new": [chat]}))
                                except Exception:
                                    active_connections.discard(client)
                    except Exception as e:
                        print("Error parsing/broadcast:", e)
        except Exception as e:
            print("WebSocket Indodax error, reconnecting in 5s:", e)
            await asyncio.sleep(5)

async def speedometer_broadcast():
    while True:
        now = time.time()
        chat_timestamps[:] = [t for t in chat_timestamps if now - t <= 60]
        speed_per_minute = len(chat_timestamps)
        for client in list(active_connections):
            try:
                await client.send_text(json.dumps({
                    "speedometer": {
                        "per_minute": speed_per_minute
                    }
                }))
            except Exception:
                active_connections.discard(client)
        await asyncio.sleep(2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task1 = asyncio.create_task(indodax_ws_listener())
    task2 = asyncio.create_task(speedometer_broadcast())
    yield
    task1.cancel()
    task2.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def websocket_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chatroom Indodax</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
        <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 8px; padding: 0; background: #fff;}
            table.dataTable thead th { font-weight: bold; border-bottom: 2px solid #ddd; }
            table.dataTable { border-bottom: 2px solid #ddd; }
            .cusername {
                color: #1976d2;
                font-weight: bold;
                cursor: pointer;
            }
            .level-0 { color: #5E5E5E; }
            .level-1 { color: #5B2D00; }
            .level-2 { color: #FF8200; text-shadow: 1px 1px #CCCCCC; }
            .level-3 { color: #034AC4; text-shadow: 1px 1px #CCCCCC; }
            .level-4 { color: #00E124; text-shadow: 1px 1px #00B31C; }
            .level-5 { color: #B232B2 }
            .chat{ color: #000; text-shadow: none;}
            th, td { vertical-align: top; }
            th:nth-child(1), td:nth-child(1) { width: 130px; min-width: 110px; max-width: 150px; white-space: nowrap; }
            th:nth-child(2), td:nth-child(2) { width: 120px; min-width: 90px; max-width: 160px; white-space: nowrap; }
            th:nth-child(3), td:nth-child(3) { width: auto; word-break: break-word; white-space: pre-line; }
            .header-chatroom { display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-top: 0; margin-left: 10px; padding-top: 0; }
            .header-chatroom a {color: red;}
            .gauge-container {
                margin-left: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
                user-select: none;
            }
        </style>
    </head>
    <body>
    <div class="header-chatroom">
        <h2 style="color:#222;">Chatroom Indodax</h2>
        <a>* Maksimal 1000 chat terakhir</a>
<div class="gauge-container">
    <svg id="half-gauge" width="120" height="90" viewBox="0 0 120 90">
        <defs>
            <linearGradient id="gauge-gradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#8fdb8f"/>
                <stop offset="70%" stop-color="#ffe680"/>
                <stop offset="85%" stop-color="#ffb380"/>
                <stop offset="100%" stop-color="#e57373"/>
            </linearGradient>
        </defs>
        <!-- Arc -->
        <path d="M13,60 A47,47 0 0,1 107,60" fill="none" stroke="url(#gauge-gradient)" stroke-width="6"/>
        <!-- Ticks & numbers -->
        <g id="half-gauge-ticks"></g>
        <!-- Needle -->
        <g id="half-needle-group">
            <line id="half-needle" x1="60" y1="60" x2="13" y2="60" stroke="#607080" stroke-width="4" stroke-linecap="round"/>
            <circle cx="60" cy="60" r="5" fill="#607080" stroke="#fff" stroke-width="1.5"/>
        </g>
        <!-- Value and unit below gauge -->
        <text id="half-gauge-value" x="60" y="78" text-anchor="middle" font-size="15" fill="#607080" font-family="Arial" font-weight="bold">0</text>
        <text id="half-gauge-unit" x="60" y="88" text-anchor="middle" font-size="10" fill="#607080" font-family="Arial">chat/menit</text>
    </svg>
</div>
    </div>
    <table id="history" class="display" style="width:100%">
        <thead>
            <tr>
                <th>Waktu</th>
                <th>Username</th>
                <th>Chat</th>
                <th style="display:none;">Timestamp</th>
                <th style="display:none;">ID</th>
                <th style="display:none;">SortKey</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
    <script>
        var table = $('#history').DataTable({
            "ordering": false,
            "paging": false,
            "info": false,
            "searching": true,
            "columnDefs": [
                { "targets": [3,4,5], "visible": false }
            ],
            "language": {
                "emptyTable": "Belum ada chat"
            }
        });

        let allChats = [];

        function updateTable(newChats) {
            newChats.forEach(function(chat) {
                if (!allChats.some(c => c.id === chat.id)) {
                    chat.sort_key = chat.timestamp * 1000000 + chat.id;
                    allChats.push(chat);
                }
            });
            allChats.sort(function(a, b) {
                return b.sort_key - a.sort_key;
            });
            table.clear();
            allChats.forEach(function(chat) {
                var level = chat.level || 0;
                var row = [
                    chat.timestamp_wib || "",
                    '<span class="level-' + level + ' cusername ">' + (chat.username || "") + '</span>',
                    '<span class="level-' + level + ' chat ">' + (chat.content || "") + '</span>',
                    chat.timestamp,
                    chat.id,
                    chat.sort_key
                ];
                table.row.add(row);
            });
            table.draw(false);
        }

const minValue = 0, maxValue = 80, minAngle = -180, maxAngle = 0;
const cx = 60, cy = 60, radius = 47;
function drawHalfGaugeTicks() {
    let g = document.getElementById("half-gauge-ticks");
    g.innerHTML = "";
    let majorStep = 10;
    let minorStep = 5;
    let totalTicks = (maxValue - minValue) / minorStep;
    for (let i = 0; i <= totalTicks; i++) {
        let val = minValue + i * minorStep;
        let angle = minAngle + (val - minValue) / (maxValue - minValue) * (maxAngle - minAngle);
        let rad = angle * Math.PI / 180;
        let isMajor = val % majorStep === 0;
        let len = isMajor ? 8 : 4;
        let x1 = cx + (radius - len) * Math.cos(rad);
        let y1 = cy + (radius - len) * Math.sin(rad);
        let x2 = cx + radius * Math.cos(rad);
        let y2 = cy + radius * Math.sin(rad);
        g.innerHTML += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#888" stroke-width="${isMajor ? 1.5 : 1}"/>`;
        if (isMajor) {
            let lx = cx + (radius - 15) * Math.cos(rad);
            let ly = cy + (radius - 15) * Math.sin(rad) + 4;
            g.innerHTML += `<text x="${lx}" y="${ly}" font-size="8" text-anchor="middle" fill="#607080">${val}</text>`;
        }
    }
}
drawHalfGaugeTicks();

function updateHalfGauge(val) {
    // Jarum dibatasi, angka tidak
    let jarumVal = Math.max(minValue, Math.min(val, maxValue));
    let angle = minAngle + (jarumVal - minValue) / (maxValue - minValue) * (maxAngle - minAngle);
    let rad = angle * Math.PI / 180;
    let x2 = cx + 32 * Math.cos(rad);
    let y2 = cy + 32 * Math.sin(rad);
    document.getElementById("half-needle").setAttribute("x1", cx);
    document.getElementById("half-needle").setAttribute("y1", cy);
    document.getElementById("half-needle").setAttribute("x2", x2);
    document.getElementById("half-needle").setAttribute("y2", y2);
    document.getElementById("half-gauge-value").textContent = val;
}

        function connectWS() {
            var ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
            ws.onmessage = function(event) {
                var data = JSON.parse(event.data);
                if (data.history) {
                    allChats = [];
                    updateTable(data.history);
                } else if (data.new) {
                    updateTable(data.new);
                } else if (data.speedometer) {
                    updateHalfGauge(data.speedometer.per_minute);
                }
            };
            ws.onclose = function() {
                setTimeout(connectWS, 1000);
            };
        }
        connectWS();
    </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        await websocket.send_text(json.dumps({"history": history[-1000:]}))
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"ping": True}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print("WebSocket error:", e)
    finally:
        active_connections.discard(websocket)
