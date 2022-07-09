from __future__ import absolute_import

from octoprint.settings import settings as s
import octoprint
import octoprint.plugin
import octoprint.filemanager
import octoprint.printer
import octoprint.util.gcodeInterpreter as gcodeInterpreter
from octoprint.events import Events
import math
import os
import base64
import zlib
import logging

from octoprint.settings import settings
from octoprint.util.gcodeInterpreter import Vector3D as Vector3D
from octoprint.util.gcodeInterpreter import MinMax3D as MinMax3D

class gcode_dimensions(object):

    
    def __init__(self):
        self._minMax = MinMax3D()

    @property
    def dimensions(self):
        size = self._minMax.size
        return dict(width=size.x,
                    depth=size.y,
                    height=size.z)

    @property
    def printing_area(self):
        return dict(minX=self._minMax.min.x,
                    minY=self._minMax.min.y,
                    minZ=self._minMax.min.z,
                    maxX=self._minMax.max.x,
                    maxY=self._minMax.max.y,
                    maxZ=self._minMax.max.z)
                    
                    
    def load(self, filename):
        if os.path.isfile(filename):
            self.filename = filename
            self._fileSize = os.stat(filename).st_size

            import codecs
            with codecs.open(filename, encoding="utf-8", errors="replace") as f:
                self._load(f)

    def _load(self, gcodeFile):
        lineNo = 0
        readBytes = 0
        pos = Vector3D(0.0, 0.0, 0.0)
        toolOffset = Vector3D(0.0, 0.0, 0.0)
        relativeE = False
        relativeMode = False
        scale = 1.0

        for line in gcodeFile:
            lineNo += 1
            readBytes += len(line)

            G = self.getCodeInt(line, 'G')

            if G is not None:
                if G == 0 or G == 1:    #Move
                    x = self.getCodeFloat(line, 'X')
                    y = self.getCodeFloat(line, 'Y')
                    z = self.getCodeFloat(line, 'Z')
                    e = self.getCodeFloat(line, 'E')
                    f = self.getCodeFloat(line, 'F')

                    if x is not None or y is not None or z is not None:
                        # this is a move
                        move = True
                    else:
                        # print head stays on position
                        move = False

                    oldPos = pos

                    # Use new coordinates if provided. If not provided, use prior coordinates (minus tool offset)
                    # in absolute and 0.0 in relative mode.
                    newPos = Vector3D(x if x is not None else (0.0 if relativeMode else pos.x - toolOffset.x),
                                      y if y is not None else (0.0 if relativeMode else pos.y - toolOffset.y),
                                      z if z is not None else (0.0 if relativeMode else pos.z - toolOffset.z))

                    if relativeMode:
                        # Relative mode: scale and add to current position
                        pos += newPos * scale
                    else:
                        # Absolute mode: scale coordinates and apply tool offsets
                        pos = newPos * scale + toolOffset

                    if e > 0.0 and move and pos.z > 0.2:
                            # extrusion and move -> relevant for print area & dimensions
                            self._minMax.record(pos)

    def getCodeInt(self,line, code):
        n = line.find(code) + 1
        if n < 1:
            return None
        m = line.find(' ', n)
        try:
            if m < 0:
                return int(line[n:])
            return int(line[n:m])
        except:
            return None


    def getCodeFloat(self,line, code):
        import math
        n = line.find(code) + 1
        if n < 1:
            return None
        m = line.find(' ', n)
        try:
            if m < 0:
                val = float(line[n:])
            else:
                val = float(line[n:m])
            return val if not (math.isnan(val) or math.isinf(val)) else None
        except:
            return None
            
class SmartABLPlugin(octoprint.plugin.EventHandlerPlugin,
                        octoprint.plugin.TemplatePlugin,
                        octoprint.plugin.SettingsPlugin):
    def __init__(self):
        self.grid = {"L" : 0.0, "R" : 0.0, "F" : 0.0, "B" : 0.0}
        
    def get_settings_defaults(self):
        return dict(do_g29=True,probe_x=6,probe_y=-37,inflate_x=5,inflate_y=5)
    
    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]
        
    def is_probeable(self,probe,position):
        if probe[0] <= position <= probe[1]:
            return True
        else:
            return False
                    
    def on_event(self, event, payload):
        do_g29 = self._settings.get(["do_g29"])
        #if event == Events.FILE_SELECTED and do_g29:
        if event == Events.METADATA_ANALYSIS_FINISHED and do_g29:
            #no choice here but to reload gcode and do an independent analysis
            gcode_path = self._file_manager.path_on_disk(payload["origin"], payload["path"])
            thecode = gcode_dimensions()
            thecode.load(gcode_path)
            printing_area = thecode.printing_area
            print printing_area
            printer_volume = self._printer_profile_manager.get_current_or_default().get('volume')
            #print printer_volume
            #calculate where our bounding area, taking into account probe offsets and bed size
            printer_x = printer_volume["width"]
            printer_y = printer_volume["depth"]
            probe_x = self._settings.get(["probe_x"])
            probe_y = self._settings.get(["probe_y"])
            inflate_x = self._settings.get(["inflate_x"])
            inflate_y = self._settings.get(["inflate_y"])
            
            #Define probeable area
            #TODO: More pythonic way of doing this?
            probe_area = dict()
            if probe_x <= 0:
                probe_area["x"] = (0,printer_x + probe_x)
            else:
                probe_area["x"] = (probe_x,printer_x)
            if probe_y <= 0:
                probe_area["y"] = (0,printer_y + probe_y)
            else:
                probe_area["y"] = (probe_y,printer_y)
            print probe_area    
            pos_L = printing_area["minX"] - inflate_x
            if self.is_probeable(probe_area["x"],pos_L):
                self.grid["L"] = pos_L
            else:
                self.grid["L"] = 10
                
            pos_R = printing_area["maxX"] + inflate_x
            if self.is_probeable(probe_area["x"],pos_R):
                self.grid["R"] = pos_R
            else:
                self.grid["R"] = probe_area["x"][1]
            
            pos_F = printing_area["minY"] - inflate_y
            if self.is_probeable(probe_area["y"],pos_F):
                self.grid["F"] = pos_F
            else:
                self.grid["F"] = 10
            
            pos_B = printing_area["maxY"] + inflate_y
            if self.is_probeable(probe_area["y"],pos_B):
                self.grid["B"] = pos_B
            else:
                self.grid["B"] = probe_area["y"][1]
                     
            print self.grid
            
    def rewrite_g29(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        if self._settings.get(["do_g29"]) and gcode and gcode == "G29":
            cmd = "G29 L%s R%s F%s B%s" % (self.grid["L"], self.grid["R"], self.grid["F"], self.grid["B"])
        return cmd
        
__plugin_name__ = "smartabl"
__plugin_version__ = "0.1.0"
__plugin_description__ = "Replace generic G29 ABL command to include just the region occupied by the model"
__plugin_implementation__ = SmartABLPlugin()
__plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.rewrite_g29
    }
