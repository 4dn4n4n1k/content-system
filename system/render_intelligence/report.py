"""Console summary of a render plan (the JSON itself is the artifact)."""


def summarize(plan: dict) -> None:
    shots = plan["shots"]
    kenburns = sum(1 for s in shots if s["camera"]["mode"] == "kenburns")
    punches = [s for s in shots if s.get("motion")]
    emphasized = sum(1 for s in shots if s.get("caption_emphasis") == "high")
    recs = [c for c in plan["cuts"] if c.get("recommendation")]

    print(f"Render plan: {len(shots)} shots over {plan['duration']:.1f}s @ {plan['fps']}fps")
    print(f"  camera   : {kenburns} Ken Burns still(s), "
          f"{len(shots) - kenburns} native-motion shot(s)")
    if punches:
        for s in punches:
            m = s["motion"]
            print(f"  motion   : shot {s['n']} zoom punch at +{m['zoom_punch_at_s']}s "
                  f"x{m['zoom_punch_scale']} ({m.get('reason', '')})")
    else:
        print("  motion   : no zoom punches needed")
    print(f"  sfx      : {len(plan['events'])} event(s) "
          f"({', '.join(sorted({e['sfx'] for e in plan['events']})) or 'none'})")
    a = plan["audio"]
    print(f"  audio    : music vol {a['music_volume']} "
          f"(fade {a['music_fade_in_s']}s/{a['music_fade_out_s']}s), "
          f"sfx vol {a['sfx_volume']}, loudnorm {'on' if a['loudnorm'] else 'off'}")
    print(f"  captions : {'on' if plan['captions']['enabled'] else 'off'}"
          + (f", {emphasized} emphasized shot(s)" if emphasized else ""))
    energies = [p["energy"] for p in plan["energy_curve"]]
    if energies:
        print(f"  energy   : min {min(energies):.2f} / avg "
              f"{sum(energies) / len(energies):.2f} / max {max(energies):.2f}")
    if recs:
        print(f"  pending  : {len(recs)} transition recommendation(s) not yet renderable")
    for note in plan["notes"]:
        print(f"  note     : {note}")
