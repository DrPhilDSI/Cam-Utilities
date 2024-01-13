import adsk.core, adsk.cam
import os
import sys
import re
import json
from ...lib import fusion360utils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_setNcProgramDefaults'
CMD_NAME = 'Set NC Program Defaults'
CMD_Description = "Sets the user defaults for user NC Programs"
# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# prints the report
PRINT_REPORT = False

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = config.cam_workspace
TAB_ID = config.cam_tab_id
TAB_NAME = config.cam_tab_name

PANEL_ID = config.postUtils_panel_id
PANEL_NAME = config.postUtils_panel_name
PANEL_AFTER = config.postUtils_panel_after

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'setDefaults', '')
# imagePath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'help.png')

DEFAULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'defaults.json')


# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get target toolbar tab for the command and create the tab if necessary.
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if toolbar_tab is None:
        toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    # Get target panel for the command and and create the panel if necessary.
    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID)
    if panel is None:
        panel = toolbar_tab.toolbarPanels.add(
            PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def)

    # Specify if the command is promoted to the main toolbar.
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()
        
            # Delete the panel if it is empty
    if panel.controls.count == 0:
        panel.deleteMe()

    # Delete the tab if it is empty
    if toolbar_tab.toolbarPanels.count == 0:
        toolbar_tab.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    #futil.log(f'{CMD_NAME} Command Created Event')

    cmd = args.command
    # avoid the OK event to be raised when the form is closed by an external input
    cmd.isExecutedWhenPreEmpted = False

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = cmd.commandInputs
    config = read_config(DEFAULTS_FILE)
    userSettings = config["userSettings"]
    
    # Create inputs
    input_displayName = inputs.addTextBoxCommandInput('input_displayName', 'Display Name', userSettings.get('displayName'), 1, False)
    input_name = inputs.addTextBoxCommandInput('input_name', 'Program Name', userSettings.get('name'), 1, False)
    input_filename = inputs.addTextBoxCommandInput('input_filename', 'File Name', userSettings.get('filename'), 1, False)
    input_comment = inputs.addTextBoxCommandInput('input_comment', 'Program Comment', userSettings.get('comment'), 1, False)
    input_addFolder = inputs.addBoolValueInput('input_addFolder', 'Create new folder?', True, '', False)
    input_folderName = inputs.addTextBoxCommandInput('input_folderName', 'Folder Name', userSettings.get('outputFolder'), 1, False)
    input_saveFolder = inputs.addBoolValueInput('input_saveFolder', 'Select save folder', False, '', False)
    input_saveFolder.text = 'Select save folder'
    input_saveFolder.isFullWidth = True
    input_folderPath = inputs.addTextBoxCommandInput('input_folderPath', 'Folder Path', ' ', 1, True)


    # TODO Connect to the events that are needed by this command.
    futil.add_handler(cmd.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(cmd.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(cmd.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(cmd.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    input_displayName: adsk.core.TextBoxCommandInput = inputs.itemById('input_displayName')
    input_name: adsk.core.TextBoxCommandInput = inputs.itemById('input_name')
    input_filename: adsk.core.TextBoxCommandInput = inputs.itemById('input_filename')
    input_comment: adsk.core.TextBoxCommandInput = inputs.itemById('input_comment')
    input_addFolder: adsk.core.BoolValueCommandInput = inputs.itemById('input_addFolder')
    input_folderName: adsk.core.TextBoxCommandInput = inputs.itemById('input_folderName')
    input_saveFolder: adsk.core.TextBoxCommandInput = inputs.itemById('input_saveFolder')
    input_folderPath: adsk.core.TextBoxCommandInput = inputs.itemById('input_folderPath')
    
    
    
    config = read_config(DEFAULTS_FILE)
    if config:
        # Updating the userDefaults
        config["userSettings"]["displayName"] = input_displayName.text
        config["userSettings"]["name"] = input_name.text
        config["userSettings"]["filename"] = input_filename.text
        config["userSettings"]["comment"] = input_comment.text
        config["userSettings"]["createFolder"] = input_addFolder.value
        config["userSettings"]["outputFolder"] = input_folderName.text
        config["userSettings"]["filePath"] = input_folderPath.text

        # Writing the updated config back to the file
        write_config(DEFAULTS_FILE, config)
    


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    #futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')
    
            # Set styles of file dialog.
    folderDlg = ui.createFolderDialog()
    folderDlg.title = 'Select save folder'
        

    saveFolder: adsk.core.TextBoxCommandInput = inputs.itemById('input_saveFolder')
    folderPath: adsk.core.TextBoxCommandInput = inputs.itemById('input_folderPath')
    
    if changed_input.id == saveFolder.id:
        if saveFolder.value:
            dlgResult = folderDlg.showDialog()
            if dlgResult == adsk.core.DialogResults.DialogOK:
                folderPath.text = folderDlg.folder
            else:
                return
            saveFolder.value = False



# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    #futil.log(f'{CMD_NAME} Validate Input Event')
    pass
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    #futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []

def read_config(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Configuration file not found.")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON from the file.")
        return None
    
def write_config(file_path, config):
    try:
        with open(file_path, 'w') as file:
            json.dump(config, file, indent=4)
        print("Configuration updated successfully.")
    except IOError:
        print("Error writing to the configuration file.")