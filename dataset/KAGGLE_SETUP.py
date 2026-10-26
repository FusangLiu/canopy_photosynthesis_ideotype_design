# Run this preparation cell once after starting/restarting the kernel.
# Finds normal, flattened, nested and ZIP-preserved course uploads.
from pathlib import Path
import sys,os,subprocess,hashlib,zipfile,shutil

def locate_canopy_runtime(input_root=None,local_roots=None,work=None,tag=None):
    tag=tag or ('win_amd64' if sys.platform=='win32' else 'manylinux_2_34_x86_64')
    expected=f'canopyteach-1.0.1-cp311-abi3-{tag}.whl'
    pattern=f'canopyteach-1.0.1-cp311-abi3-{tag}*.whl'
    work=Path(work or '/kaggle/working/canopyteach_practical_en')
    candidate_root=Path(input_root or '/kaggle/input')
    wheels=set();helpers=set();archives=set();observed=[];archive_errors=[]

    def consider(p):
        if p.name=='canopy_practical.py':helpers.add(p.resolve())
        elif p.match(pattern):wheels.add(p.resolve())
        elif p.suffix.lower()=='.zip':archives.add(p.resolve())
        if len(observed)<35 and p.is_file():observed.append(str(p))

    if candidate_root.is_dir():
        # Kaggle can add dataset/owner/version directories or flatten uploads.
        for p in candidate_root.rglob('*'):
            if p.is_file():consider(p)
    else:
        roots=local_roots if local_roots is not None else ([] if input_root is not None else [Path.cwd(),*Path.cwd().parents])
        for folder in map(Path,roots):
            if folder==Path(folder.anchor):continue
            for p in [folder/'canopy_practical.py',*folder.glob(pattern),*folder.glob('wheels/'+pattern)]:
                if p.is_file():consider(p)
        if input_root is not None:
            observed.append('Input directory does not exist: '+str(candidate_root))

    # Read only the runtime members of course ZIPs into a writable directory.
    # Never extract arbitrary archive paths or change the input Dataset.
    if not wheels or not helpers:
        for archive in sorted(archives):
            try:
                with zipfile.ZipFile(archive) as z:
                    selected=[n for n in z.namelist() if not n.endswith('/') and
                        (Path(n).name=='canopy_practical.py' or Path(n).match(pattern))]
                    if not selected:continue
                    key=hashlib.sha256(str(archive).encode()).hexdigest()[:12]
                    for i,name in enumerate(selected):
                        info=z.getinfo(name)
                        if info.file_size>30_000_000:raise ValueError('Runtime member exceeds 30 MB: '+name)
                        dest=work/'_runtime'/key/str(i)/Path(name).name
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        dest.write_bytes(z.read(name));consider(dest)
            except (zipfile.BadZipFile,OSError,ValueError) as exc:
                archive_errors.append(str(archive)+': '+str(exc))

    if not wheels or not helpers:
        missing=[]
        if not wheels:missing.append(expected)
        if not helpers:missing.append('canopy_practical.py')
        details='\n'.join(observed) or '(no mounted input files found)'
        raise FileNotFoundError(
            'Missing course runtime: '+', '.join(missing)+'\n'
            'Add the course Dataset as an input to THIS notebook; importing an .ipynb alone does not attach its Dataset.\n'
            'Searched input: '+str(candidate_root)+'\nObserved files (first 35):\n'+details+
            ('\nArchive errors:\n'+'\n'.join(archive_errors) if archive_errors else ''))

    # Prefer a nearby helper, without requiring the wheels/ directory layout.
    pairs=[]
    for wheel in sorted(wheels):
        for helper in sorted(helpers):
            shared=len(os.path.commonpath([str(wheel.parent),str(helper.parent)]).split(os.sep))
            nearby=helper.parent in (wheel.parent,wheel.parent.parent)
            pairs.append((not nearby,-shared,str(wheel),str(helper)))
    _,_,wheel_name,helper_name=min(pairs)
    wheel,helper=Path(wheel_name),Path(helper_name)
    # Browser downloads may add a suffix such as " (1)" to a wheel filename.
    if wheel.name!=expected:
        normalized=work/'_runtime'/'normalized'/expected
        normalized.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(wheel,normalized);wheel=normalized
    return wheel,helper

if __name__=='__main__':
    if sys.version_info<(3,11):raise RuntimeError('This course requires CPython 3.11 or newer.')
    input_override=os.environ.get('CANOPYTEACH_INPUT_ROOT')
    work_override=os.environ.get('CANOPYTEACH_WORK_ROOT')
    on_kaggle=Path('/kaggle/working').is_dir()
    WORK=Path(work_override) if work_override else (
        Path('/kaggle/working/canopyteach_practical_en') if on_kaggle else Path.cwd()/'results/practical_en')
    wheel,helper=locate_canopy_runtime(input_root=input_override,work=WORK)
    PACKAGE_ROOT=helper.parent
    WORK.mkdir(parents=True,exist_ok=True);site=WORK/'_packages';marker=site/'course_wheel.sha256'
    signature=hashlib.sha256(wheel.read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text().strip()!=signature:
        if 'canopyteach' in sys.modules:
            raise RuntimeError('Restart the kernel before installing a different course wheel, then run preparation again.')
        subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--disable-pip-version-check',
                        '--upgrade','--target',str(site),str(wheel)],check=True)
        marker.write_text(signature)
    sys.path.insert(0,str(site));sys.path.insert(0,str(PACKAGE_ROOT))
    import canopy_practical as cp
    import canopyteach
    if canopyteach.__version__!='1.0.1':raise RuntimeError('Unexpected canopyteach version; restart the kernel.')
    cp.style()
    try:get_ipython().run_line_magic('matplotlib','inline')
    except NameError:pass
    DEFAULT_STEP=int(os.environ.get('CANOPYTEACH_STEP_MINUTES','30'))
    DEFAULT_SPACING=float(os.environ.get('CANOPYTEACH_RAY_SPACING','.005'))
    print('Runtime wheel:',wheel)
    print('Teaching helper:',helper)
    print('Ready. Outputs:',WORK)
    print('Random whole-plant azimuth; central crop; XY periodic; C/OpenMP; synthetic direct light.')
