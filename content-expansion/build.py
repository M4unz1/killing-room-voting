"""Build only original mod source; game and framework references stay external."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def build(dotnet, game, bepinex, framework, output):
    csc = sorted((dotnet.parent/'sdk').glob('*/Roslyn/bincore/csc.dll'))
    if not csc:
        raise ValueError('A .NET SDK installation is required, not only the runtime.')
    references = [framework/name for name in ['mscorlib.dll', 'System.dll', 'System.Core.dll']]
    references += [game/name for name in ['Assembly-CSharp.dll', 'Assembly-CSharp-firstpass.dll', 'UnityEngine.dll',
                  'UnityEngine.UI.dll', 'Behave.Unity.Runtime.dll', 'NewBehaveLibraryBuild.dll']]
    references += [bepinex/name for name in ['BepInEx.dll', '0Harmony.dll']]
    missing = [str(path) for path in references if not path.is_file()]
    if missing:
        raise ValueError('Missing build references: '+', '.join(missing))
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted(ROOT.glob('*.cs')) + sorted((ROOT/'Core').glob('*.cs'))
    command = [str(dotnet), str(csc[-1]), '-nologo', '-target:library', '-noconfig', '-nostdlib+', '-langversion:3',
               '-optimize+', '-deterministic+', '-out:'+str(output/'KillingRoomCommunity.Content.dll')]
    command += ['-reference:'+str(path) for path in references]
    command += [str(path) for path in sources]
    subprocess.run(command, check=True)
    print(output/'KillingRoomCommunity.Content.dll')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dotnet', required=True, type=Path)
    p.add_argument('--game-managed', required=True, type=Path)
    p.add_argument('--bepinex-core', required=True, type=Path)
    p.add_argument('--framework-refs', required=True, type=Path)
    p.add_argument('--output', type=Path, default=ROOT/'build')
    args = p.parse_args()
    try:
        build(args.dotnet.resolve(), args.game_managed.resolve(), args.bepinex_core.resolve(), args.framework_refs.resolve(), args.output.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        p.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
