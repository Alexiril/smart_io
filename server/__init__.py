from datetime import datetime
from os import mkdir
from pathlib import Path
from sqlite3 import connect as sqlite_connect
from threading import Thread
from time import sleep
from typing import Any

from fastapi import FastAPI, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from requests import get as requests_get
from requests import post as requests_post
from starlette import status
from uvicorn import run as uvirun

quitting = False

server_path = Path(".") / "server"

# Database singleton
db = sqlite_connect("server.db", check_same_thread=False)


def create_devices_table() -> None:
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                device_ip TEXT NOT NULL,
                device_role TEXT NOT NULL,
                coord_x INTEGER,
                coord_y INTEGER
            );
        """)


def create_timed_events_table() -> None:
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS timed_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_time TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices (id)
            );
        """)


create_devices_table()
create_timed_events_table()

# FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory=server_path / "static"), "static")

templates = Jinja2Templates(directory=server_path / "templates")

device_roles_icons = {
    "mixed": "lightbulb",
    "led": "chart-simple",
    "relay": "shuffle",
    "sensor": "arrow-up-right-dots",
}

EVENT_TYPES = {
    "relay-on": "Включить реле",
    "relay-off": "Выключить реле",
    "relay-toggle": "Переключить реле",
    "led-on": "Включить LED",
    "led-off": "Выключить LED",
    "led-toggle": "Переключить LED",
}


class ActualDevice:
    id: int
    name: str
    ip: str
    role: str
    role_icon: str
    coord_x: int
    coord_y: int

    def __init__(self, id: int, name: str, ip: str, role: str, coord_x: int, coord_y: int) -> None:
        self.id = id
        self.name = name
        self.ip = ip
        self.role = role
        self.coord_x = coord_x
        self.coord_y = coord_y

        self.role_icon = device_roles_icons.get(role, "question")


class ActualEvent:
    id: int
    device_id: int
    type: str
    time: str
    device: ActualDevice

    def __init__(self, id: int, device_id: int, type: str, time: str) -> None:
        self.id = id
        self.device_id = device_id
        self.type = type
        self.time = time
        self.device = list(filter(lambda x: x.id == self.device_id, get_devices()))[0]


class DeviceId(BaseModel):
    device_id: int


class LEDModel(DeviceId):
    brightness: int


class DeviceWithPosition(DeviceId):
    coord_x: int
    coord_y: int


class EventId(BaseModel):
    event_id: int


def get_devices() -> list[ActualDevice]:
    with db:
        devices: list[tuple[int, str, str, str, int, int]] = db.execute(
            "SELECT id, device_name, device_ip, device_role, coord_x, coord_y FROM devices"
        ).fetchall()

    return [ActualDevice(*device) for device in devices]


def get_events() -> list[ActualEvent]:
    with db:
        events: list[tuple[int, int, str, str]] = db.execute(
            "SELECT id, device_id, event_type, event_time FROM timed_events"
        ).fetchall()

    return [ActualEvent(*event) for event in events]


def handle_timed_events() -> None:
    global quitting

    events_db = sqlite_connect("server.db", check_same_thread=False)

    while not quitting:
        with events_db:
            events: list[tuple[int, int, str, str]] = events_db.execute(
                "SELECT id, device_id, event_type, event_time FROM timed_events"
            ).fetchall()

        for event in events:
            e = ActualEvent(*event)
            device_ip = e.device.ip
            hours, minutes = e.time.split(":")
            now = datetime.now()
            current_hours = now.hour
            current_minutes = now.minute
            if current_hours == int(hours) and current_minutes == int(minutes):
                try:
                    if e.type == "relay-on":
                        requests_post(
                            f"http://{device_ip}/api/v1/relay",
                            json={"state": "on"},
                            timeout=2,
                        )
                    elif e.type == "relay-off":
                        requests_post(
                            f"http://{device_ip}/api/v1/relay",
                            json={"state": "off"},
                            timeout=2,
                        )
                    elif e.type == "led-on":
                        requests_post(
                            f"http://{device_ip}/api/v1/led",
                            json={"state": 100},
                            timeout=2,
                        )
                    elif e.type == "led-off":
                        requests_post(
                            f"http://{device_ip}/api/v1/led",
                            json={"state": 0},
                            timeout=2,
                        )
                except Exception as exception:
                    print(f"Failed to execute event {e.id}: {exception}")
                print(f"Executed event {e.id} at {e.time} on device {e.device.name} ({device_ip})")
        sleep(60)


@app.get("/favicon.ico")
async def favicon() -> Response:
    return FileResponse(server_path / "static" / "img" / "favicon.png")


@app.get("/")
async def root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "devices": get_devices(),
            "events": get_events(),
        },
    )


@app.get("/add-timed-event")
async def add_timed_event(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "add_timed_event.html",
        {
            "devices": get_devices(),
            "event_types": EVENT_TYPES,
        },
    )


@app.post("/add-timed-event")
async def add_timed_event_post(request: Request) -> RedirectResponse:
    form_data = await request.form()
    device_id = form_data.get("device_id")
    event_type = form_data.get("event_type")
    event_time = form_data.get("event_time")

    with db:
        db.execute(
            "INSERT INTO timed_events (device_id, event_type, event_time) VALUES (?, ?, ?)",
            (device_id, event_type, event_time),
        )

    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


@app.get("/map-background")
async def map_background() -> Response:
    files_dir = server_path / "files"
    if not files_dir.is_dir():
        mkdir(files_dir)
    map_file = files_dir / "current-map"
    map_mediatype_file = files_dir / "current-map-mediatype"
    if not map_file.is_file() or not map_mediatype_file.is_file():
        return Response(None, 404)
    with open(map_mediatype_file, "r") as inp:
        mediatype = inp.read()
    return FileResponse(map_file, media_type=mediatype)


@app.get("/create-map")
async def create_map(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "create_map.html",
        {},
    )


@app.post("/create-map")
async def create_map_post(map_image: UploadFile) -> RedirectResponse:
    files_dir = server_path / "files"
    if not files_dir.is_dir():
        mkdir(files_dir)
    map_file = files_dir / "current-map"
    map_mediatype_file = files_dir / "current-map-mediatype"
    with open(map_mediatype_file, "w") as out:
        out.write(map_image.content_type or "")
    with open(map_file, "wb") as out:
        out.write(await map_image.read())
    await map_image.close()
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


@app.post("/set-device-position")
async def set_device_position(inp: DeviceWithPosition) -> JSONResponse:
    device_id = inp.device_id
    coord_x = inp.coord_x
    coord_y = inp.coord_y
    with db:
        if (device_id,) not in db.execute("SELECT id FROM devices").fetchall():
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Device not found",
                },
                status_code=400,
            )

        db.execute(
            "UPDATE devices SET coord_x = ?, coord_y = ? WHERE id = ? ",
            (
                coord_x,
                coord_y,
                device_id,
            ),
        )

    return JSONResponse(
        content={
            "status": "success",
            "message": "Device moved successfully",
        },
        status_code=200,
    )


@app.get("/add-device")
async def add_device(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "add_device.html",
        {},
    )


@app.post("/add-device")
async def add_device_post(request: Request) -> JSONResponse:
    form_data = await request.form()
    device_name = form_data.get("device_name")
    device_ip = form_data.get("device_ip")
    device_role = form_data.get("device_role")

    with db:
        if (device_ip,) in db.execute("SELECT device_ip FROM devices").fetchall():
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Device already exists",
                },
                status_code=400,
            )

        db.execute(
            "INSERT INTO devices (device_name, device_ip, device_role) VALUES (?, ?, ?)",
            (device_name, device_ip, device_role),
        )

    return JSONResponse(
        content={
            "status": "success",
            "message": "Device added successfully",
        },
        status_code=200,
    )


@app.post("/remove-device")
async def remove_device(inp: DeviceId) -> JSONResponse:
    device_id = inp.device_id
    with db:
        if (device_id,) not in db.execute("SELECT id FROM devices").fetchall():
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Device not found",
                },
                status_code=400,
            )

        db.execute(
            "DELETE FROM devices WHERE id = ?",
            (device_id,),
        )

    return JSONResponse(
        content={
            "status": "success",
            "message": "Device removed successfully",
        },
        status_code=200,
    )


@app.get("/devices-data")
async def devices_data() -> JSONResponse:
    with db:
        devices: list[tuple[int, str]] = db.execute("SELECT id, device_ip FROM devices").fetchall()

    result: dict[int, dict[str, Any]] = {}
    for device in devices:
        device_id = device[0]
        device_ip = device[1]

        try:
            response = requests_get(f"http://{device_ip}/api/v1/status", timeout=2).json()
            result[device_id] = {
                "result": "success",
                "lightness": response["lightness"],
                "relay_state": response["relay"],
                "led_state": response["led-state"],
            }
        except Exception as e:
            result[device_id] = {
                "result": "error",
                "error": str(e),
            }
            continue

    return JSONResponse(
        content=result,
        status_code=200,
    )


@app.post("/toggle-relay")
async def toggle_relay(inp: DeviceId) -> JSONResponse:
    device_id = inp.device_id

    with db:
        device_ip = db.execute(
            "SELECT device_ip FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
        if device_ip is None:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Device not found",
                },
                status_code=400,
            )

    try:
        relay_state = requests_get(f"http://{device_ip[0]}/api/v1/relay", timeout=2).json()["state"]

        requests_post(
            f"http://{device_ip[0]}/api/v1/relay",
            json={
                "state": "on" if relay_state == "off" else "off",
            },
            timeout=2,
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to toggle relay: {e}",
            },
            status_code=500,
        )

    return JSONResponse(
        content={
            "status": "success",
            "message": f"Relay {device_id} toggled",
        },
        status_code=200,
    )


@app.post("/set-led")
async def set_led(inp: LEDModel) -> JSONResponse:
    device_id = inp.device_id
    brightness = inp.brightness

    with db:
        device_ip = db.execute(
            "SELECT device_ip FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
        if device_ip is None:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Device not found",
                },
                status_code=400,
            )

    try:
        requests_post(
            f"http://{device_ip[0]}/api/v1/led",
            json={
                "state": brightness,
            },
            timeout=2,
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to set LED state: {e}",
            },
            status_code=500,
        )

    return JSONResponse(
        content={
            "status": "success",
            "message": f"LED {device_id} set to {brightness}",
        },
        status_code=200,
    )


@app.post("/remove-event")
async def remove_event(inp: EventId) -> JSONResponse:
    event_id = inp.event_id
    with db:
        if (event_id,) not in db.execute("SELECT id FROM timed_events").fetchall():
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Event not found",
                },
                status_code=400,
            )

        db.execute(
            "DELETE FROM timed_events WHERE id = ?",
            (event_id,),
        )

    return JSONResponse(
        content={
            "status": "success",
            "message": "Event removed successfully",
        },
        status_code=200,
    )


def main() -> None:
    global quitting
    timed_events_thread = Thread(target=handle_timed_events)
    timed_events_thread.start()
    uvirun(app, host="0.0.0.0", port=80)
    quitting = True
    timed_events_thread.join()


if __name__ == "__main__":
    main()
