
import os

import adsk.cam
import adsk.core
import adsk.fusion

from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ropeThread'
CMD_NAME = 'Rope Thread'
CMD_Description = 'Creates threading operation based of rope thread parameters'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = config.cam_workspace
TAB_ID = config.cam_tab_id
TAB_NAME = config.cam_tab_name

PANEL_ID = config.camUtils_panel_id
PANEL_NAME = config.camUtils_panel_name
PANEL_AFTER = config.camUtils_panel_after

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []
index = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'html', 'index.html')
index = index.replace('\\', '/')


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    
    # Add the additional information for an extended tooltip.
    toolTipImage = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'toolTip.png')
    cmd_def.toolClipFilename = toolTipImage

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


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.log(f'{CMD_NAME} Command Created Event')
    
    app = adsk.core.Application.get()
    ui = app.userInterface
    doc = app.activeDocument
    products = doc.products
    # Get the CAM product
    cam = adsk.cam.CAM.cast(products.itemByProductType("CAMProductType"))
    camWS = ui.workspaces.itemById('CAMEnvironment')
    camWS.activate()
    
    inputs = args.command.commandInputs
    unitsMgr = cam.unitsManager
    defaultRopeDiam = round(unitsMgr.convert(10, 'mm', "cm"),3)
    defaultStepOver = round(unitsMgr.convert(0.3, 'mm', "cm"), 3)


    selections: adsk.core.Selections = ui.activeSelections
    selections.clear()
    selectedToolpath = inputs.addSelectionInput('selectedToolpath', 'Select Toolpath', 'Select the reference threading operation')

    ropeDiam = inputs.addDistanceValueCommandInput('rope_dia', 'Diameter of the rope', adsk.core.ValueInput.createByReal(defaultRopeDiam))
    stepOver = inputs.addDistanceValueCommandInput('stepOver', 'Step over', adsk.core.ValueInput.createByReal(defaultStepOver))


                
# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')
    app = adsk.core.Application.get()
    ui = app.userInterface
    product = app.activeProduct
    cam = adsk.cam.CAM.cast(product)
    units = adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput
    selectedToolpath: adsk.core.SelectionCommandInput = inputs.itemById('selectedToolpath')
    browserInput: adsk.core.BrowserCommandInput = inputs.itemById(f'{CMD_ID}_browser')
    outputFolder = cam.temporaryFolder
    postProcessor = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'Post', 'AnalyzeAxis.cps')
    programName = 'Analyze Axis'
    
    if selectedToolpath.selectionCount <= 0:
        browserInput.htmlFileURL = index
        return 

    operation = selectedToolpath.selection(0).entity
    if operation.classType() != 'adsk::cam::Operation':
        ui.messageBox(f'{operation.objectType} is not a toolpath')
        selectedToolpath.clearSelection()
        return
    
    if not operation.isToolpathValid:
        ui.messageBox(f'Operation: {operation.name} is out of date.')
        selectedToolpath.clearSelection()
        return

    futil.log('********** Selected Toolpath **********')
    futil.log(f'Name: {operation.name}')
    futil.log('***************************************')
    programName = operation.name
    postInput = adsk.cam.PostProcessInput.create(programName, postProcessor, outputFolder, units)
    postInput.isOpenInEditor = False
    try: 
        cam.postProcess(operation,postInput)
    except Exception as e:
        futil.log(f'Post processing failed  {e}')
        return
    # cam.postProcess(operation,postInput)
    futil.log(f'Post processed {programName}')

    # Create browser
    toolpath = os.path.join(outputFolder, programName + '.html')
    toolpath = toolpath.replace('\\', '/')
    futil.log(f"Opening {toolpath}")
    
    browserInput.htmlFileURL = toolpath
            
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')
    

    # Get a reference to your command's inputs.

    


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
