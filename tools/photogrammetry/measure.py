"""Use solved photos as measuring instruments.

    from measure import Site
    site = Site("aligned.json", image_dir)
    site.ground("20260425_183023.jpg", 1480, 2210)          -> (x, y) on the ground, metres
    site.crop("20260425_183023.jpg", x0, y0, x1, y1, out)    -> a crop with pixel ticks, to read points from
    site.triangulate([(name, u, v), (name, u, v)])           -> 3D point from two or more photos

Pixel coordinates are in the original photo (as the camera saw it, before any
rotation in a viewer). Camera models: SIMPLE_RADIAL from the solve.
"""
import json, math
import numpy as np


class Site:
    def __init__(self, aligned_json, image_dir):
        self.d = json.load(open(aligned_json))
        self.S = self.d["scale"]; self.R = np.array(self.d["R"]); self.T = np.array(self.d["t"])
        self.dir = image_dir

    def cam(self, name):
        c = self.d["cameras"][name]
        M = np.array(c["cam_from_world"])            # 3x4 in the SfM frame
        return c, M[:, :3], M[:, 3], np.array(c["centre"])

    def ray(self, name, u, v):
        c, Rc, tc, C = self.cam(name)
        f, cx, cy, k = c["camera"]["params"][:4]
        # pixel -> normalised, undoing radial distortion (fixed-point)
        xd, yd = (u - cx) / f, (v - cy) / f
        x, y = xd, yd
        for _ in range(20):
            r2 = x * x + y * y
            x, y = xd / (1 + k * r2), yd / (1 + k * r2)
        d_cam = np.array([x, y, 1.0])
        d_sfm = Rc.T @ d_cam
        d = self.R @ d_sfm
        return C, d / np.linalg.norm(d)

    def ground(self, name, u, v, z=0.0):
        C, d = self.ray(name, u, v)
        if abs(d[2]) < 1e-6:
            return None
        s = (z - C[2]) / d[2]
        if s <= 0:
            return None
        P = C + s * d
        return float(P[0]), float(P[1])

    def triangulate(self, obs):
        """least-squares point closest to all rays; returns point and spread (m)"""
        A = np.zeros((3, 3)); b = np.zeros(3); rays = []
        for name, u, v in obs:
            C, d = self.ray(name, u, v)
            Pm = np.eye(3) - np.outer(d, d)
            A += Pm; b += Pm @ C; rays.append((C, d))
        X = np.linalg.solve(A, b)
        spread = max(np.linalg.norm((np.eye(3) - np.outer(d, d)) @ (X - C)) for C, d in rays)
        return X, spread

    def crop(self, name, x0, y0, x1, y1, out, tick=50):
        from PIL import Image, ImageDraw
        im = Image.open(f"{self.dir}/{name}")
        im = im.crop((x0, y0, x1, y1))
        dr = ImageDraw.Draw(im)
        for x in range((x0 // tick + 1) * tick, x1, tick):
            dr.line([(x - x0, 0), (x - x0, 12)], fill=(255, 255, 0)); dr.text((x - x0 + 2, 12), str(x), fill=(255, 255, 0))
        for y in range((y0 // tick + 1) * tick, y1, tick):
            dr.line([(0, y - y0), (12, y - y0)], fill=(255, 255, 0)); dr.text((14, y - y0 - 6), str(y), fill=(255, 255, 0))
        im.save(out)
        return out
