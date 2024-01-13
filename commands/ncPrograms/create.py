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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ncProgramsDefault'
CMD_NAME = 'NC Program Defaults'
CMD_Description = "Creates an NC Program with User defaults"
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
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', "create", '')

# Default values
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
    
    
    doc = app.activeDocument
    products = doc.products
    # Get the CAM product
    cam = adsk.cam.CAM.cast(products.itemByProductType("CAMProductType"))
    
    config = read_defaults(DEFAULTS_FILE)
    if config:
        userSettings = config.get('userSettings', {})

    # get setups
    setups = cam.setups

    # search active setup
    setup = None
    for s in setups:
        if s.isActive:
            setup = s
            break

    # check if setup found
    if not setup:
        #app.log('WARNING: No operation renamed!')  
        ui.messageBox('Ensure the setup to rename is active and try again...', 'Fusion 360',
                        adsk.core.MessageBoxButtonTypes.OKButtonType, adsk.core.MessageBoxIconTypes.WarningIconType)
        return

    # create NCProgramInput object
    ncInput = cam.ncPrograms.createInput()
    ncInput.displayName = userSettings.get('displayName')


    # change some nc program parameters...
    ncParameters = ncInput.parameters
    ncParameters.itemByName('nc_program_name').expression = str(userSettings.get('name'))
    ncParameters.itemByName('nc_program_filename').expression = str(userSettings.get('filename'))
    ncParameters.itemByName('nc_program_comment').expression = userSettings.get('comment')
    ncParameters.itemByName('nc_program_openInEditor').value.value = True
    # set user desktop as output directory (Windows and Mac)
    # make the path valid for Fusion360 by replacing \\ to / in the path
    desktopDirectory = os.path.expanduser("~/Desktop").replace('\\', '/') 
    
    if userSettings.get('filePath'):
        filePath = userSettings.get('filePath')
        if userSettings.get('createFolder'):
            print('create folder')
            
            outputFolder = userSettings.get('outputFolder')
            ncParameters.itemByName('nc_program_output_folder').expression = str("'" +filePath+'/'+"'+") + outputFolder
    else:
        ncParameters.itemByName('nc_program_output_folder').value.value = desktopDirectory

    postedOperations = []
    for operation in setup.operations:
        if operation.isValid:
            postedOperations.append(operation)
    ncInput.operations = postedOperations
    # add a new ncprogram from the ncprogram input
    newProgram = cam.ncPrograms.add(ncInput)




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

    

# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    #futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


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

def read_defaults(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Defaults file not found.")
    except json.JSONDecodeError:
        print("Error decoding JSON from the file.")