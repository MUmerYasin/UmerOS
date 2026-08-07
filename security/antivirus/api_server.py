"""REST API server for the antivirus engine (port 9095)."""

import asyncio
import json
import os
from aiohttp import web

from .engine import AntivirusEngine

engine = AntivirusEngine()


async def handle_dashboard(request):
    return web.json_response(engine.get_dashboard())


async def handle_scan_file(request):
    data = await request.json()
    file_path = data.get("path", "")
    if not file_path or not os.path.exists(file_path):
        return web.json_response({"error": "File not found"}, status=404)
    report = engine.scan_file(file_path)
    return web.json_response(report.to_dict())


async def handle_scan_directory(request):
    data = await request.json()
    dir_path = data.get("path", "")
    if not dir_path or not os.path.isdir(dir_path):
        return web.json_response({"error": "Directory not found"}, status=404)
    reports, stats = await engine.scan_directory(dir_path)
    return web.json_response({
        "reports": [r.to_dict() for r in reports],
        "stats": stats.to_dict(),
    })


async def handle_quarantine(request):
    data = await request.json()
    file_path = data.get("path", "")
    report_data = data.get("report", {})
    if not file_path:
        return web.json_response({"error": "No path provided"}, status=400)

    from .scanner import ScanReport, ScanResult
    report = ScanReport(
        file_path=file_path,
        result=ScanResult.THREAT_FOUND,
        threat_name=report_data.get("threat_name", "Unknown"),
        threat_level=report_data.get("threat_level", "medium"),
        detection_method=report_data.get("detection_method", "manual"),
        md5=report_data.get("md5", ""),
        sha256=report_data.get("sha256", ""),
    )
    entry = engine.quarantine_threat(report)
    if entry:
        return web.json_response({"status": "quarantined", "entry": entry.to_dict()})
    return web.json_response({"error": "Failed to quarantine"}, status=500)


async def handle_quarantine_list(request):
    return web.json_response({"entries": engine.get_quarantine_list()})


async def handle_quarantine_restore(request):
    data = await request.json()
    entry_id = data.get("id", "")
    success = engine.restore_quarantined(entry_id)
    return web.json_response({"success": success})


async def handle_quarantine_delete(request):
    data = await request.json()
    entry_id = data.get("id", "")
    success = engine.delete_quarantined(entry_id)
    return web.json_response({"success": success})


async def handle_realtime_start(request):
    await engine.start_realtime()
    return web.json_response({"status": "started"})


async def handle_realtime_stop(request):
    engine.stop_realtime()
    return web.json_response({"status": "stopped"})


async def handle_realtime_add_watch(request):
    data = await request.json()
    dir_path = data.get("path", "")
    success = engine.add_watch(dir_path)
    return web.json_response({"success": success})


async def handle_realtime_remove_watch(request):
    data = await request.json()
    dir_path = data.get("path", "")
    success = engine.remove_watch(dir_path)
    return web.json_response({"success": success})


async def handle_realtime_events(request):
    limit = request.query.get("limit", 50)
    events = engine.get_realtime_events(int(limit))
    return web.json_response({"events": events})


async def handle_watched_dirs(request):
    return web.json_response({"dirs": engine.get_watched_dirs()})


def create_app():
    app = web.Application()
    app.router.add_get("/api/dashboard", handle_dashboard)
    app.router.add_post("/api/scan/file", handle_scan_file)
    app.router.add_post("/api/scan/directory", handle_scan_directory)
    app.router.add_post("/api/quarantine", handle_quarantine)
    app.router.add_get("/api/quarantine/list", handle_quarantine_list)
    app.router.add_post("/api/quarantine/restore", handle_quarantine_restore)
    app.router.add_post("/api/quarantine/delete", handle_quarantine_delete)
    app.router.add_post("/api/realtime/start", handle_realtime_start)
    app.router.add_post("/api/realtime/stop", handle_realtime_stop)
    app.router.add_post("/api/realtime/watch", handle_realtime_add_watch)
    app.router.add_post("/api/realtime/unwatch", handle_realtime_remove_watch)
    app.router.add_get("/api/realtime/events", handle_realtime_events)
    app.router.add_get("/api/realtime/watched", handle_watched_dirs)
    return app


def main():
    app = create_app()
    web.run_app(app, host="127.0.0.1", port=9095)


if __name__ == "__main__":
    main()
