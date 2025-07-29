import os, sys
import shutil


def pyonir_setup():
    from pyonir import PYONIR_SETUPS_DIRPATH
    from pyonir.utilities import copy_assets, PrntColrs

    base_path = os.getcwd()
    backend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'backend')
    contents_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'contents')
    contents_slim_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'contents-slim')
    frontend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'frontend')
    entry_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, 'main.py')

    project_name = input(f"Whats your project name?").strip()
    project_path = os.path.join(base_path, project_name)
    use_demo = input(f"{PrntColrs.OKBLUE}Do you want to install the demo project?(y for yes, n for no){PrntColrs.RESET}").strip()
    if not os.path.exists(project_path):
        os.makedirs(project_path)
    use_frontend = input(f"{PrntColrs.OKBLUE}Do you need a frontend? (y for yes, n for no){PrntColrs.RESET}").strip()

    if use_demo.lower() == 'y':
        copy_assets(entry_filepath, os.path.join(project_path, 'main.py'), False)
        copy_assets(contents_dirpath, os.path.join(project_path, 'contents'), False)
        copy_assets(backend_dirpath, os.path.join(project_path, 'backend'), False)

        if use_frontend == 'y':
            copy_assets(frontend_dirpath, os.path.join(project_path, 'frontend'), False)

    summary = f'''{PrntColrs.OKGREEN}
Project {project_name} created!
- path: {project_path}
- use frontend: {use_frontend}{PrntColrs.RESET}
        '''
    print(summary)

def pyonir_install():
    import requests, zipfile, io
    """Installs plugins into pyonir application from the pyonir registry"""
    GIT_HUB_ZIP = "https://github.com/{repo_path}/archive/refs/heads/{repo_branch}.zip"
    project_base_dir = os.getcwd()
    action, context = sys.argv[1:]
    if action == 'install':
        if context.startswith('plugins:'):
            dir_name, repo_context = context.split(':')
            repo_path, repo_branch = repo_context.split('#')
            _, repo_name = repo_path.split('/')
            repo_zip = GIT_HUB_ZIP.format(repo_path=repo_path, repo_branch=repo_branch)
            temp_dst_path = os.path.join(project_base_dir, dir_name, "."+repo_name)
            dst_path = os.path.join(project_base_dir, dir_name, repo_name)
            print(f"pyonir is downloading {repo_zip} ...")
            response = requests.get(repo_zip)
            response.raise_for_status()
            if not os.path.exists(temp_dst_path):
                os.makedirs(temp_dst_path)
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                zf.extractall(temp_dst_path)
            extracted_folder = os.path.join(temp_dst_path, f"{repo_name}-{repo_branch}")
            shutil.move(extracted_folder, dst_path)
            shutil.rmtree(temp_dst_path)

    print(action, context)
    pass

if __name__ == '__main__':
    pyonir_install()