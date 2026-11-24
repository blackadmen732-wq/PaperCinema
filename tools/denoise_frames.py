"""Optional CPU denoiser for studio frames when Cycles lacks native denoising."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
import oidn


def to_linear(rgb):
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def to_display(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= .0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - .055)


def denoise(source, out):
    device = oidn.NewDevice(oidn.DEVICE_TYPE_CPU)
    oidn.CommitDevice(device)
    out.mkdir(parents=True, exist_ok=True)
    try:
        for path in sorted(source.glob('*.png')):
            with Image.open(path) as image:
                rgb = np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0
            linear = np.ascontiguousarray(to_linear(rgb))
            result = np.empty_like(linear)
            height, width = linear.shape[:2]
            filt = oidn.NewFilter(device, 'RT')
            try:
                oidn.SetSharedFilterImage(filt, 'color', linear, oidn.FORMAT_FLOAT3, width, height)
                oidn.SetSharedFilterImage(filt, 'output', result, oidn.FORMAT_FLOAT3, width, height)
                oidn.CommitFilter(filt)
                oidn.ExecuteFilter(filt)
                if oidn.GetDeviceError(device) or not np.isfinite(result).all():
                    raise RuntimeError(f'OIDN failed for {path}')
            finally:
                oidn.ReleaseFilter(filt)
            # Preserve a small amount of the rendered paper texture at the fill and shoulder edges.
            display = to_display(result) * .88 + rgb * .12
            Image.fromarray(np.round(display * 255).astype(np.uint8)).save(out / path.name)
    finally:
        oidn.ReleaseDevice(device)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    denoise(args.source, args.out)
