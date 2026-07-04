"""Camera planning: Ken Burns for stills, hands-off for video.

Defaults reproduce the renderer's historical look exactly
(zoom 0.0008/frame capped at 1.12, centered push-in); direction/pan
variation is available via config (render.camera.alternate) for operators
who want visible variety between consecutive stills.
"""
from .models import CameraPlan, ShotRender


def plan(shots: list[ShotRender], cfg: dict, reports: dict) -> None:
    cam = (cfg.get("render") or {}).get("camera") or {}
    rate = float(cam.get("kenburns_zoom_per_frame", 0.0008))
    zmax = float(cam.get("kenburns_max", 1.12))
    alternate = bool(cam.get("alternate", False))
    pans = ("center", "left", "right", "up", "down")

    still_index = 0
    for s in shots:
        if s.kind != "image":
            s.camera = CameraPlan(mode="none")
            continue
        direction = "in"
        pan = "center"
        if alternate:
            direction = "in" if still_index % 2 == 0 else "out"
            pan = pans[still_index % len(pans)]
        # Higher-energy stills push a touch faster (still subtle).
        energy_rate = rate * (1.0 + 0.5 * (s.energy - 0.6))
        s.camera = CameraPlan(mode="kenburns",
                              zoom_rate_per_frame=round(max(energy_rate, 0.0002), 6),
                              zoom_max=zmax, direction=direction, pan=pan)
        still_index += 1
