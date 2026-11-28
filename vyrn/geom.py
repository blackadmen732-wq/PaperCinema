"""Shared geometry: three.js conventions (docs/TIMELINE-FORMAT.md §3): +y up, metres, quaternions [x, y, z, w],
the camera looks down its local -z with +y up and `fov` is the VERTICAL field of view in degrees."""
import math


def qrot(q, v):
    """rotate vector v by unit quaternion q = [x, y, z, w]"""
    x, y, z, w = q
    vx, vy, vz = v
    # t = 2 * cross(q.xyz, v)
    tx = 2 * (y * vz - z * vy); ty = 2 * (z * vx - x * vz); tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def quat_from_euler_y(a):
    return (0.0, math.sin(a / 2), 0.0, math.cos(a / 2))


def quat_mul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def quat_from_axis(axis, ang):
    s = math.sin(ang / 2)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(ang / 2))


def project(cam_pos, cam_q, fov_deg, aspect, p):
    """world point -> (sx, sy, depth) with sx, sy in 0..1 from the top-left; None when behind the lens"""
    d = qrot(qinv(cam_q), (p[0] - cam_pos[0], p[1] - cam_pos[1], p[2] - cam_pos[2]))
    if d[2] >= -1e-6:
        return None
    th = math.tan(math.radians(fov_deg) / 2)
    xn = (d[0] / -d[2]) / (th * aspect)
    yn = (d[1] / -d[2]) / th
    return ((xn + 1) / 2, (1 - yn) / 2, -d[2])


def look_quat(pos, target):
    """camera quaternion that looks from pos at target with world +y up (yaw then pitch, no roll)"""
    dx, dy, dz = target[0] - pos[0], target[1] - pos[1], target[2] - pos[2]
    yaw = math.atan2(-dx, -dz)
    pitch = math.atan2(dy, math.hypot(dx, dz))
    return quat_mul(quat_from_axis((0, 1, 0), yaw), quat_from_axis((1, 0, 0), pitch))
