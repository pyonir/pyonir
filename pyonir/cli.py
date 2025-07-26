import os

def pyonir_setup():
    from pyonir import PYONIR_SETUPS_DIRPATH
    from pyonir.utilities import copy_assets, PrntColrs

    base_path = os.getcwd()
    backend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'backend')
    contents_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'contents')
    frontend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'frontend')
    entry_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, 'main.py')

    project_name = input(f"Whats your project name?").strip()
    project_path = os.path.join(base_path, project_name)
    if not os.path.exists(project_path):
        os.makedirs(project_path)

    copy_assets(entry_filepath, os.path.join(project_path, 'main.py'), False)
    copy_assets(contents_dirpath, os.path.join(project_path, 'contents'), False)
    copy_assets(backend_dirpath, os.path.join(project_path, 'backend'), False)

    use_frontend = input(f"{PrntColrs.RESET}Do you need a frontend? (y for yes, n for no)").strip()
    if use_frontend == 'y':
        copy_assets(frontend_dirpath, os.path.join(project_path, 'frontend'), False)

    summary = f'''{PrntColrs.OKGREEN}
Project {project_name} created!
- path: {project_path}
- use frontend: {use_frontend}{PrntColrs.RESET}
        '''
    print(summary)
