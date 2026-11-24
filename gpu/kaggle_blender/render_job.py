"""Render the production modular character through the Kaggle Blender job."""
import shutil
import subprocess
import tarfile
from pathlib import Path

FRAMES = (1, 12)
SAMPLES = 48
RESOLUTION = '720x1280'
RECIPE = 'ronin-reference'
BLENDER_TAG = '4.5.16'


def render_shot(blender, repo, frames_dir, movie, *, frames=FRAMES, samples=SAMPLES, res=RESOLUTION,
                recipe=RECIPE, denoise=True):
    frames_dir.mkdir(parents=True, exist_ok=True)
    movie.parent.mkdir(parents=True, exist_ok=True)
    first, last = frames
    expected = [frames_dir / f'f{i:04d}.png' for i in range(first, last + 1)]
    for still in expected:
        still.unlink(missing_ok=True)
    log = movie.parent / 'blender.log'
    command = [str(blender), '-b', '--python-exit-code', '1', '-P', 'blender/character/character_shot.py', '--',
               '--recipe', recipe, '--frames', f'{first}-{last}', '--out', str(frames_dir),
               '--samples', str(samples), '--res', res]
    if not denoise:
        command.append('--no-denoise')
    with log.open('w', encoding='utf-8') as output:
        process = subprocess.run(command, cwd=repo, stdout=output, stderr=subprocess.STDOUT)
    missing = [f.name for f in expected if not f.is_file() or f.stat().st_size == 0]
    if process.returncode or missing:
        tail = log.read_text(encoding='utf-8', errors='replace').splitlines()[-12:]
        raise RuntimeError(f'Blender exit {process.returncode}; missing frames {missing}\n' + '\n'.join(tail))

    temporary = movie.with_name(movie.stem + '.encoding' + movie.suffix)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', '24',
                    '-start_number', str(first), '-i', str(frames_dir / 'f%04d.png'),
                    '-frames:v', str(len(expected)), '-threads', '2', '-c:v', 'libx264',
                    '-crf', '16', '-pix_fmt', 'yuv420p', str(temporary)], check=True)
    if not temporary.is_file() or not temporary.stat().st_size:
        raise RuntimeError(f'FFmpeg did not write {temporary}')
    temporary.replace(movie)
    for still in (expected[0], expected[-1]):
        shutil.copy2(still, movie.parent / still.name)
    print(f'Rendered {len(expected)} frames to {movie}', flush=True)


def main():
    temp = Path('/kaggle/tmp')
    temp.mkdir(parents=True, exist_ok=True)
    source, = Path('/kaggle/input').glob('**/repo.tgz')
    with tarfile.open(source) as archive:
        archive.extractall(temp, filter='data')
    blender_base = f'blender-{BLENDER_TAG}-linux-x64'
    release = f'https://download.blender.org/release/Blender4.5/{blender_base}.tar.xz'
    package = temp / (blender_base + '.tar.xz')
    subprocess.run(['curl', '-fLsS', release, '-o', str(package)], check=True)
    with tarfile.open(package) as archive:
        archive.extractall(temp, filter='data')
    subprocess.run(['apt-get', 'install', '-y', '-qq', 'libxi6', 'libxxf86vm1', 'libxfixes3',
                    'libxrender1', 'libgl1', 'libxkbcommon0', 'libsm6'],
                   stdout=subprocess.DEVNULL, check=False)
    render_shot(temp / blender_base / 'blender', temp / 'repo', temp / 'frames',
                Path('/kaggle/working/shot.mp4'))


if __name__ == '__main__':
    main()
