"""Small shims for Blender API changes, so the same scripts run on 4.5 LTS and 5.x.

Blender 4.4 introduced slotted actions and 5.x removed the legacy `Action.fcurves` shortcut, so
`obj.animation_data.action.fcurves` raises AttributeError on 5.x. Everything that walks an action's
curves goes through fcurves_of() instead.
"""


def fcurves_of(action):
    """Every F-curve in an action, on either API. Returns a plain list."""
    if action is None:
        return []
    legacy = getattr(action, 'fcurves', None)
    if legacy is not None:
        return list(legacy)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in getattr(layer, 'strips', []):
            for bag in getattr(strip, 'channelbags', []):
                out.extend(bag.fcurves)
    return out


def object_fcurves(ob):
    """Every F-curve animating this object, or an empty list if it has none."""
    ad = getattr(ob, 'animation_data', None)
    return fcurves_of(getattr(ad, 'action', None)) if ad else []
