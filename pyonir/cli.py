from __future__ import annotations

import os, sys
import shutil
from pyonir.utilities import copy_assets, PrntColrs
from pyonir import PYONIR_SETUPS_DIRPATH

backend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'backend')
contents_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'contents')
frontend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'frontend')
entry_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, 'main.py')
theme_readme_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, 'frontend', 'README.md')
pkg_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, '__init__.py')
env_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, '.env.example')

def pyonir_new_project(args):

    base_path = os.getcwd()
    project_name = input(f"Whats your project name?").strip()
    project_path = os.path.join(base_path, project_name.replace(' ', '_').lower())
    if not os.path.exists(project_path):
        os.makedirs(project_path)
        os.makedirs(os.path.join(project_path, 'frontend'))
    copy_assets(pkg_filepath, os.path.join(project_path, '__init__.py'), False)
    copy_assets(env_filepath, os.path.join(project_path, '.env.example'), False)
    copy_assets(entry_filepath, os.path.join(project_path, 'main.py'), False)
    copy_assets(theme_readme_filepath, os.path.join(project_path, 'frontend', 'README.md'), False)
    copy_assets(backend_dirpath, os.path.join(project_path, 'backend'), False)
    copy_assets(contents_dirpath, os.path.join(project_path, 'contents'), False)

    summary = f'''{PrntColrs.OKGREEN}
Project {project_name} created!
- path: {project_path}
        '''
    print(summary)

def pyonir_create(args):
    """Create a demo project based on pre configured templates"""
    use_demo = input(f"{PrntColrs.OKBLUE}Do you want to install the demo project?(y for yes, n for no){PrntColrs.RESET}").strip()


def pyonir_install(args: list):
    """Installs plugin_names or themes into pyonir application from the pyonir registry"""
    import requests, zipfile, io
    gh_zip_address = "https://github.com/{repo_path}/archive/refs/heads/{repo_branch}.zip"
    project_base_dir = os.getcwd()
    action, *contexts = args
    action, *action_context = action.split(':')
    action_context = action_context.pop(0)
    # dir_name, repo_context = action.split(':')

    if action == 'theme':
        print(f"Installing {action} theme...")
        pass
    if action == 'plugin':
        # dir_name, repo_context = action.split(':')
        repo_path, *repo_branch = action_context.split('#')
        repo_branch = repo_branch.pop(0) if repo_branch else 'main'
        repo_owner, repo_name = repo_path.split('/')
        repo_zip = gh_zip_address.format(repo_path=repo_path, repo_branch=repo_branch)
        temp_dst_path = os.path.join(project_base_dir,'plugins', "."+repo_name)
        dst_path = os.path.join(project_base_dir,'plugins', repo_name)
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


def pyonir_setup():
    action, *contexts = sys.argv[1:]
    # print(action, contexts)

    if action == 'init':
        pyonir_new_project(contexts)
        print('initializing...', contexts)
    elif action == 'install':
        print('installing...', contexts)
        pyonir_install(contexts)
        pass
    elif action == 'help':
        print(f"""
Pyonir CLI - Commands
---------------------

init       Create a new empty project
install    Install a plugin or theme from GitHub registry
help       Show CLI documentation

Usage:
  pyonir <command> [options]

Examples:
  pyonir init
  pyonir install plugin:<repo_owner>/<repo_name>#<repo_branch>
  pyonir install theme:<repo_owner>/<repo_name>#<repo_branch>
  pyonir help
""")
    else:
        print(f"Pyonir expects arguments of: init (creating a new site), install (installing plugins or themes)")

if __name__ == '__main__':
    pyonir_setup()