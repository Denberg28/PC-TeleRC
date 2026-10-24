"""Add one uniquely numbered device from a saved private network project."""
from pathlib import Path
from provision import create_project,add_device

def main():
    print('TeleRC Scalable LoRa 0.5.0rc1 — saved network project')
    project=Path(input('Private network project file (existing, or a new filename): ').strip()).expanduser()
    if project==Path('.'):raise ValueError('Choose a private project file')
    if not project.exists():
        create_project(project)
        print('Created network project. Back it up; keep it private.')
    role=(input('Board role [BASE / ROVER / NODE, default NODE]: ').strip() or 'NODE').upper()
    number=int(input('Unique device ID [default 1]: ').strip() or '1')
    parent=Path(input('Private sketch parent folder: ').strip()).expanduser()
    if parent==Path('.'):raise ValueError('Choose a private output folder')
    name=f'TeleRCFleet_{role}'+(f'_{number:03}' if role=='ROVER' else f'_{number}' if role=='NODE' else '')
    folder=add_device(project,parent/name,role,number)
    print('Generated:',folder)
    print('Upload only this board. Existing boards keep their keys and firmware.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as e:raise SystemExit(str(e))
