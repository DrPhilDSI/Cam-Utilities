description = "Analyze Kinematics";
vendor = "adsk";
legal = "Copyright (C) 2012-2023 by Autodesk, Inc.";
certificationLevel = 2;
minimumRevision = 45917;

longDescription = "Plot Kinematics axis into HTML.";

extension = "html";
programNameIsInteger = true;
setCodePage("ascii");

capabilities = CAPABILITY_MILLING | CAPABILITY_MACHINE_SIMULATION;
tolerance = spatial(0.002, MM);

minimumChordLength = spatial(0.25, MM);
minimumCircularRadius = spatial(0.01, MM);
maximumCircularRadius = spatial(1000, MM);
minimumCircularSweep = toRad(0.01);
maximumCircularSweep = toRad(180);
allowHelicalMoves = true;
allowedCircularPlanes = 0; // allow any circular motion
highFeedrate = unit == IN ? 500 : 5000;
probeMultipleFeatures = true;

function onOpen() {
  // define and enable machine configuration
  receivedMachineConfiguration = machineConfiguration.isReceived();
  if (typeof defineMachine == "function") {
    defineMachine(); // hardcoded machine configuration
  }
  activateMachine(); // enable the machine optimizations and settings
}

function onSection() {}

function onCycle() {}

function onCyclePoint(x, y, z) {}

function onCycleEnd() {}
function onSectionEnd() {}

// Start of onRewindMachine logic
/** Allow user to override the onRewind logic. */
function onRewindMachineEntry(_a, _b, _c) {
  return false;
}

/** Retract to safe position before indexing rotaries. */
function onMoveToSafeRetractPosition() {}

/** Rotate axes to new position above reentry position */
function onRotateAxes(_x, _y, _z, _a, _b, _c) {
  // position rotary axes
  invokeOnRapid5D(_x, _y, _z, _a, _b, _c);
  setCurrentABC(new Vector(_a, _b, _c));
}

/** Return from safe position after indexing rotaries. */
function onReturnFromSafeRetractPosition(_x, _y, _z) {}
// End of onRewindMachine logic

function onClose() {
  if (!getSection(0).isMultiAxis()) {
    writeFailed();
  } else {
    writeScript();
  }
}

// >>>>> INCLUDED FROM include_files/commonFunctions.cpi
// internal variables, do not change
var receivedMachineConfiguration;
var operationSupportsTCP;
var multiAxisFeedrate;
var sequenceNumber;
var optionalSection = false;
var currentWorkOffset;
var forceSpindleSpeed = false;
var retracted = false; // specifies that the tool has been retracted to the safe plane
var operationNeedsSafeStart = false; // used to convert blocks to optional for safeStartAllOperations

function activateMachine() {
  // disable unsupported rotary axes output
  if (
    !machineConfiguration.isMachineCoordinate(0) &&
    typeof aOutput != "undefined"
  ) {
    aOutput.disable();
  }
  if (
    !machineConfiguration.isMachineCoordinate(1) &&
    typeof bOutput != "undefined"
  ) {
    bOutput.disable();
  }
  if (
    !machineConfiguration.isMachineCoordinate(2) &&
    typeof cOutput != "undefined"
  ) {
    cOutput.disable();
  }

  if (!machineConfiguration.isMultiAxisConfiguration()) {
    return; // don't need to modify any settings for 3-axis machines
  }

  // save multi-axis feedrate settings from machine configuration
  var mode = machineConfiguration.getMultiAxisFeedrateMode();
  var type =
    mode == FEED_INVERSE_TIME
      ? machineConfiguration.getMultiAxisFeedrateInverseTimeUnits()
      : mode == FEED_DPM
      ? machineConfiguration.getMultiAxisFeedrateDPMType()
      : DPM_STANDARD;
  multiAxisFeedrate = {
    mode: mode,
    maximum: machineConfiguration.getMultiAxisFeedrateMaximum(),
    type: type,
    tolerance:
      mode == FEED_DPM
        ? machineConfiguration.getMultiAxisFeedrateOutputTolerance()
        : 0,
    bpwRatio:
      mode == FEED_DPM
        ? machineConfiguration.getMultiAxisFeedrateBpwRatio()
        : 1,
  };

  // setup of retract/reconfigure  TAG: Only needed until post kernel supports these machine config settings
  if (receivedMachineConfiguration && machineConfiguration.performRewinds()) {
    safeRetractDistance = machineConfiguration.getSafeRetractDistance();
    safePlungeFeed = machineConfiguration.getSafePlungeFeedrate();
    safeRetractFeed = machineConfiguration.getSafeRetractFeedrate();
  }
  if (
    typeof safeRetractDistance == "number" &&
    getProperty("safeRetractDistance") != undefined &&
    getProperty("safeRetractDistance") != 0
  ) {
    safeRetractDistance = getProperty("safeRetractDistance");
  }

  if (machineConfiguration.isHeadConfiguration()) {
    compensateToolLength =
      typeof compensateToolLength == "undefined" ? false : compensateToolLength;
  }

  if (machineConfiguration.isHeadConfiguration() && compensateToolLength) {
    for (var i = 0; i < getNumberOfSections(); ++i) {
      var section = getSection(i);
      if (section.isMultiAxis()) {
        machineConfiguration.setToolLength(getBodyLength(section.getTool())); // define the tool length for head adjustments
        section.optimizeMachineAnglesByMachine(
          machineConfiguration,
          OPTIMIZE_AXIS
        );
      }
    }
  } else {
    optimizeMachineAngles2(OPTIMIZE_AXIS);
  }
}

function writeBlock() {
  writeWords(arguments);
}

// <<<<< INCLUDED FROM include_files/commonFunctions.cpi
// >>>>> INCLUDED FROM include_files/defineMachine.cpi
var compensateToolLength = false; // add the tool length to the pivot distance for nonTCP rotary heads
function defineMachine() {
  var useTCP = true;
  if (!receivedMachineConfiguration) {
    // note: setup your machine here
    var aAxis = createAxis({
      coordinate: 0,
      table: true,
      axis: [1, 0, 0],
      range: [0, 360],
      preference: 0,
      cyclic: true,
      tcp: useTCP,
    });
    var bAxis = createAxis({
      coordinate: 1,
      table: true,
      axis: [0, 1, 0],
      range: [0, 360],
      preference: 0,
      cyclic: true,
      tcp: useTCP,
    });
    var cAxis = createAxis({
      coordinate: 2,
      table: true,
      axis: [0, 0, 1],
      range: [0, 360],
      preference: 0,
      cyclic: true,
      tcp: useTCP,
    });
    machineConfiguration = new MachineConfiguration(aAxis, bAxis, cAxis);

    setMachineConfiguration(machineConfiguration);
    if (receivedMachineConfiguration) {
      warning(
        localize(
          "The provided CAM machine configuration is overwritten by the postprocessor."
        )
      );
      receivedMachineConfiguration = false; // CAM provided machine configuration is overwritten
    }
  }

  if (!receivedMachineConfiguration) {
    // multiaxis settings
    if (machineConfiguration.isHeadConfiguration()) {
      machineConfiguration.setVirtualTooltip(false); // translate the pivot point to the virtual tool tip for nonTCP rotary heads
    }

    // retract / reconfigure
    var performRewinds = false; // set to true to enable the rewind/reconfigure logic
    if (performRewinds) {
      machineConfiguration.enableMachineRewinds(); // enables the retract/reconfigure logic
      safeRetractDistance = unit == IN ? 1 : 25; // additional distance to retract out of stock, can be overridden with a property
      safeRetractFeed = unit == IN ? 20 : 500; // retract feed rate
      safePlungeFeed = unit == IN ? 10 : 250; // plunge feed rate
      machineConfiguration.setSafeRetractDistance(safeRetractDistance);
      machineConfiguration.setSafeRetractFeedrate(safeRetractFeed);
      machineConfiguration.setSafePlungeFeedrate(safePlungeFeed);
      var stockExpansion = new Vector(
        toPreciseUnit(0.1, IN),
        toPreciseUnit(0.1, IN),
        toPreciseUnit(0.1, IN)
      ); // expand stock XYZ values
      machineConfiguration.setRewindStockExpansion(stockExpansion);
    }

    // multi-axis feedrates
    if (machineConfiguration.isMultiAxisConfiguration()) {
      machineConfiguration.setMultiAxisFeedrate(
        useTCP
          ? FEED_FPM
          : getProperty("useDPMFeeds")
          ? FEED_DPM
          : FEED_INVERSE_TIME,
        9999.99, // maximum output value for inverse time feed rates
        getProperty("useDPMFeeds") ? DPM_COMBINATION : INVERSE_MINUTES, // INVERSE_MINUTES/INVERSE_SECONDS or DPM_COMBINATION/DPM_STANDARD
        0.5, // tolerance to determine when the DPM feed has changed
        1.0 // ratio of rotary accuracy to linear accuracy for DPM calculations
      );
      setMachineConfiguration(machineConfiguration);
    }

    /* home positions */
    // machineConfiguration.setHomePositionX(toPreciseUnit(0, IN));
    // machineConfiguration.setHomePositionY(toPreciseUnit(0, IN));
    // machineConfiguration.setRetractPlane(toPreciseUnit(0, IN));
  }
}

// <<<<< INCLUDED FROM include_files/positionABC.cpi

// >>>>> INCLUDED FROM include_files/motionFunctions_fanuc.cpi
function onRapid(_x, _y, _z) {}

var valFormat = createFormat({
  decimals: 1,
  forceDecimal: true,
  force: true,
  scale: DEG,
});
var valOutput = createVariable({ prefix: "," }, valFormat);
let myAaxisArr = "";
let myBaxisArr = "";
let myCaxisArr = "";
let countStr = "";
let count = 0;
function onRapid5D(_x, _y, _z, _a, _b, _c) {
  var c = valOutput.format(_c);
  var b = valOutput.format(_b);
  var a = valOutput.format(_a);
  myCaxisArr += c;
  myBaxisArr += b;
  myAaxisArr += a;
  countStr += count + ",";
  count += 1;
}

function onLinear(_x, _y, _z, feed) {}

function onLinear5D(_x, _y, _z, _a, _b, _c, feed, feedMode) {
  var c = valOutput.format(_c);
  var b = valOutput.format(_b);
  var a = valOutput.format(_a);
  myCaxisArr += c;
  myBaxisArr += b;
  myAaxisArr += a;
  countStr += count + ",";
  count += 1;
}

// <<<<< INCLUDED FROM include_files/motionFunctions_fanuc.cpi
// >>>>> INCLUDED FROM include_files/workPlaneFunctions_fanuc.cpi
var currentWorkPlaneABC = undefined;
function forceWorkPlane() {
  currentWorkPlaneABC = undefined;
}

function cancelWorkPlane(force) {
  forceWorkPlane();
}

function checkString(str) {
  var arr = str.split(",").filter(function (value) {
    return value.trim() !== ""; // Remove empty strings or strings that are just whitespace
  });
  var found = arr.some(function (value) {
    return value.trim() !== "0.";
  });
  return found;
}

function writeScript() {
  var hasA = checkString(myAaxisArr);
  var hasB = checkString(myBaxisArr);
  var hasC = checkString(myCaxisArr);
  var animation = "animation: true";
  if (
    myAaxisArr.length > 1000 ||
    myBaxisArr.length > 1000 ||
    myCaxisArr.length > 1000
  ) {
    animation = "animation: false";
  }
  writeBlock(
    '<body><div><canvas id="myChart"></canvas></div><button onClick="resetZoomChart()">Reset</button><script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/hammer.js/2.0.8/hammer.min.js" integrity="sha512-UXumZrZNiOwnTcZSHLOfcTs0aos2MzBWHXOHOuB0J/R44QB0dwY5JgfbvljXcklVf65Gc4El6RjZ+lnwd2az2g==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>',
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-zoom/2.0.1/chartjs-plugin-zoom.min.js" integrity="sha512-wUYbRPLV5zs6IqvWd88HIqZU/b8TBx+I8LEioQ/UC0t5EMCLApqhIAnUg7EsAzdbhhdgW07TqYDdH3QEXRcPOQ==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>'
  );
  writeBlock("<script>");
  hoverMarker();
  writeBlock(" const ctx = document.getElementById('myChart');");
  writeBlock("new Chart(ctx, {");
  writeBlock("type: 'line',");
  writeBlock("data: {");
  writeBlock("labels: [" + countStr.substring(0, countStr.length - 1) + "],");
  writeBlock("datasets: [");
  if (hasC) {
    writeBlock("{");
    writeBlock("label: 'C Axis',");
    writeBlock("data:[" + myCaxisArr.substring(1, myCaxisArr.length) + "],");
    writeBlock("borderWidth: 1");
    writeBlock("},");
  }
  if (hasA) {
    writeBlock("{");
    writeBlock("label: 'A Axis',");
    writeBlock("data:[" + myAaxisArr.substring(1, myAaxisArr.length) + "],");
    writeBlock("borderWidth: 1");
    writeBlock("},");
  }
  if (hasB) {
    writeBlock("{");
    writeBlock("label: 'B Axis',");
    writeBlock("data:[" + myBaxisArr.substring(1, myBaxisArr.length) + "],");
    writeBlock("borderWidth: 1");
    writeBlock("},");
  }
  writeBlock("]},");
  writeBlock(
    "options:{" + scale,
    ",",
    animation,
    ",",
    interaction,
    ",",
    pointStyle,
    ",",
    elements,
    ",",
    plugins,
    ",",
    responsive,
    ",",
    toolTips,
    ",",
    hover + "},"
  );
  writeBlock("plugins: [hoverMarkerBackground]});");
  writeBlock("function resetZoomChart(){");
  writeBlock("Chart.getChart(ctx).resetZoom();");
  writeBlock("}");

  writeBlock("Chart.register(zoomPlugin);");
  writeBlock("</script></body>");
}

// OPTIONS

var interaction = "interaction:{mode:'index',intersect:false}";
var scale = "scales:{y:{beginAtZero:false}}";
var pointStyle = "pointStyle:false";
var elements = 'elements:{line:{cubicInterpolationMode:"monotone"}}';
var plugins =
  'plugins:{zoom:{pan:{enabled:true, mode:"xy", overScaleMode: "xy"},zoom:{mode:"x",wheel:{enabled:true},drag:{enabled:true,backgroundColor:"rgba(225,155,155,0.5)",borderColor:"rgba(0,0,0,1)", borderWidth:1}}}}';
var responsive =
  'responsive: true,title: {display: true,text: "Chart.js Line Chart - Pan and Zoom"}';
var toolTips = 'tooltips:{mode:"index",intersect:false}';
var hover = 'hover:{mode:"index",intersect:false}';

function hoverMarker() {
  writeBlock("let hoverMarker;");
  writeBlock(
    "const hoverMarkerBackground = {id: 'hoverMarkerBackground',afterDatasetsDraw(chart, args, plugins){const {ctx, chartArea:{top, bottom, left, right, width, height}} = chart;"
  );
  writeBlock(
    "if(hoverMarker === undefined){return '';} ctx.save(); ctx.beginPath(); ctx.strokeStyle = 'rgba(0,0,0,1)';ctx.fillStyle = 'rgba(0,0,0,0.1)';ctx.lineWidth =1;"
  );
  writeBlock(
    "ctx.moveTo(hoverMarker, top); ctx.lineTo(hoverMarker, bottom); ctx.stroke();},"
  );
  writeBlock(
    "afterEvent(chart, args) {const xCoor = args.event.x; if(args.inChartArea){hoverMarker = xCoor;}else{hoverMarker = undefined;}"
  );
  writeBlock("args.changed = true;}}");
}

function writeFailed() {
  writeBlock(
    "<!DOCTYPE html>",
    "<html>",
    "<head>",
    "    <style>",
    "      html,",
    "      body {",
    "        height: 100%;",
    "        margin: 0;",
    "        display: flex;",
    "        align-items: center;",
    "        justify-content: center;",
    "        background-color: white;",
    "        font-family: Arial, sans-serif;",
    "      }",
    "    </style>",
    "  </head>",
    "  <body>",
    "    <div id=''message''>Toolpath has no rotary moves </div>",
    "  </body>",
    "</html>"
  );
}
