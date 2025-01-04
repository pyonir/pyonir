import os, inquirer
from . import PYONIR_SETUPS_DIRPATH, utilities


class PyonirSetup:
    create_app_msg = "Create a new Pyonir app"
    exit_cli_msg = "Exiting Pyonir cli"

    def create_new_app(self):
        """Creates new pyonir application directories"""
        self.decide_clear_dir()
        backend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'backend')
        frontend_dirpath = os.path.join(PYONIR_SETUPS_DIRPATH, 'frontend')
        entry_filepath = os.path.join(PYONIR_SETUPS_DIRPATH, 'main.py')
        if not os.path.exists(self.app_path):
            utilities.copy_assets(backend_dirpath, os.path.join(self.app_path, 'backend'), False)
            utilities.copy_assets(entry_filepath, os.path.join(self.app_path, 'main.py'), False)
        if self.app_use_frontend:
            utilities.copy_assets(frontend_dirpath, os.path.join(self.app_path, 'frontend'), False)
            pass

    def __init__(self):
        self.app_path = None
        self.frontend_tool = None
        self.app_use_frontend = None
        self.app_name: str = ""
        self.user_dir: str = os.getcwd()
        self.action: str = ""
        self.action_step: str = ""
        self.summary: str = ""
        self.intro()

    def intro(self):
        print("Welcome to the Pyonir Web framework!")
        # Step 1: Choose an action
        self.action = inquirer.prompt([
            inquirer.List('action',
                          message="What would you like to do?",
                          choices=[self.create_app_msg, self.exit_cli_msg],
                          ),
        ])['action']

        # Process user selection
        if self.action == self.create_app_msg:
            self.decide_project_name()
            self.decide_use_frontend()
        elif self.action == self.exit_cli_msg:
            print(self.summary)
            exit(0)

    def outro(self):
        self.action_step = inquirer.prompt([
            inquirer.List('action_step',
                          message="What would you like to configure next?",
                          choices=['Go back to main menu', 'Run setup'],
                          ),
        ])['action_step']
        self.summary = f'''
Project {self.app_name} created!
- path: {self.app_path}
- use frontend: {self.app_use_frontend}
    - install frontend: {self.frontend_tool}
        '''
        if self.action_step == 'Go back to main menu':
            self.intro()
        else:
            print(self.summary)
            self.create_new_app()
            print("Exiting the app.")
            exit(0)

    def decide_project_name(self):
        # print("You chose Task 1!")
        # Additional options or tasks for Task 1
        # Choose an App Name
        self.app_name = inquirer.prompt([
            inquirer.Text('app_name',
                          message="What is your project named?"
                          ),
        ])['app_name']

        self.app_path = os.path.join(self.user_dir, self.app_name)

    def decide_clear_dir(self):
        if os.path.exists(self.app_path):
            override = inquirer.prompt([
                        inquirer.Text('override',
                      message="Pyonir app already exists. Would you like to start with a clean directory?"
                      ),
                    ])['override']
            if override:
                print('delete this directory', self.app_path)

    def decide_use_frontend(self):
        # Choose optional Frontend
        app_use_frontend = inquirer.prompt([
            inquirer.Text('app_use_frontend',
                          message="Would you like to use a frontend? (y=Yes or n=No)"
                          ),
        ])['app_use_frontend']
        self.app_use_frontend = True if app_use_frontend.lower() == 'y' else False
        if self.app_use_frontend:
            self.decide_frontend_tool()

        self.outro()

    def decide_frontend_tool(self):
        self.frontend_tool = inquirer.prompt([
            inquirer.List('use_frontend_tool',
                          message="Which frontend tool would you like to install?",
                          choices=["Deno", "Bun", "Vite"],
                          ),
        ])['use_frontend_tool']


PyonirSetup()
