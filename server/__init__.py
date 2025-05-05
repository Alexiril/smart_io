from os import mkdir
from pathlib import Path
from sqlite3 import connect as sqlite_connect
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

server_path = Path(".") / "server"

# Database singleton
db = sqlite_connect("server.db")


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


create_devices_table()

# FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory=server_path / "static"), "static")

templates = Jinja2Templates(directory=server_path / "templates")


class DeviceId(BaseModel):
    device_id: int


class LEDModel(DeviceId):
    brightness: int


class DeviceWithPosition(DeviceId):
    coord_x: int
    coord_y: int


@app.get("/")
async def root(request: Request) -> HTMLResponse:
    with db:
        devices: list[tuple[int, str, str, str, int, int]] = db.execute(
            "SELECT id, device_name, device_ip, device_role, coord_x, coord_y FROM devices"
        ).fetchall()

    device_roles_icons = {
        "mixed": "lightbulb",
        "led": "chart-simple",
        "relay": "shuffle",
        "sensor": "arrow-up-right-dots",
    }

    devices = list(map(lambda x: (x[0], x[1], x[2], device_roles_icons[x[3]], x[4], x[5]), devices))

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "devices": devices,
        },
    )


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
            response = requests_get(
                f"http://{device_ip}/api/v1/status",
            ).json()
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
        relay_state = requests_get(
            f"http://{device_ip[0]}/api/v1/relay",
        ).json()["state"]

        requests_post(
            f"http://{device_ip[0]}/api/v1/relay",
            json={
                "state": "on" if relay_state == "off" else "off",
            },
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


def main() -> None:
    uvirun(app, host="0.0.0.0", port=80)


if __name__ == "__main__":
    main()
