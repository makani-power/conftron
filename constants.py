## This file is part of conftron.  
## 
## Copyright (C) 2011 Matt Peddie <peddie@jobyenergy.com>
## 
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
## 
## This program is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
## 
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
## 02110-1301, USA.

from xml.etree import ElementTree as ET
import xml.parsers.expat as expat
from os.path import dirname
import re

import baseio
import genconfig

class Constant(baseio.ImADictionary, baseio.Searchable):
    def __init__(self, node, prefix):
        self.name = ""
        if prefix != '':
            op = prefix.rstrip('_') + "." 
        else:
            op = ''
        if node.attrib.has_key('prefix'):
            self.prefix = prefix + node.attrib['prefix']
            self.octaveprefix = op + node.attrib['prefix'].rstrip('_') + "."
        elif node.tag not in ['section', 'include']:
            self.prefix = prefix + node.tag.upper()

            self.octaveprefix = op + node.tag.upper() + "."
        else:
            self.prefix = prefix
            self.octaveprefix = op
        self.defines = {}
        self.sub = {}
        for c in node.getchildren():
            if c.tag not in ['define', 'servo']:
                self.sub[c.attrib['name']] = Constant(c, self.prefix)
            elif c.tag == 'define':
                self.defines[c.attrib['name']] = c
            else:
                print "servos not implemented, sucka biznatch!"
        if node.attrib.has_key('subtree'):
            for k in node.attrib['subtree']:
                self.sub[k.attrib['name']] = Constant(k, self.prefix)
        if len(self.sub) == 0:
            self.name = node.attrib['name']
            
    def search(self, searchname):
        return self._dictrecsearch(self.sub, searchname)

    def to_define_h(self, cf):
        for n, d in self.defines.iteritems():
            cf.write("#define " + self.prefix + n + " " + d.attrib['value'] + "\n");
        for n, s in self.sub.iteritems():
            s.to_define_h(cf)
    def to_octave_struct(self, cf):
        for n, d in self.defines.iteritems():
            cf.write(self.octaveprefix + n + " = " + d.attrib['value'].replace("{", "[").replace("}", "]'") + ";\n")
        for n, s in self.sub.iteritems():
            s.to_octave_struct(cf)

class Constants(baseio.CHeader, baseio.OctaveCode, baseio.Searchable):
    def __init__(self, tree):
        self.name = tree.attrib['name']
        self.nodes = [Constant(tt, '') for tt in tree.getchildren()]

    def search(self, searchname):
        return self._recsearch(self.nodes, searchname)

    def textsearch(self, searchstring):
        pp = re.compile(searchstring)
        def searchme(x):
            found = pp.search(x.prefix + x.name)
            found.extend(x.textsearch(searchstring))
            return found

        return filter(searchme, self.nodes)

    def to_define_h(self):
        def define_h_writer(cf):
            for n in self.nodes:
                n.to_define_h(cf)
        print "writing defines file for ", self.name
        self.to_h("airframes/" + self.name, define_h_writer)

    def to_octave_structs(self):
        def octave_struct_writer(cf):
            for n in self.nodes:
                n.to_octave_struct(cf)
        print "writing octave struct file for ", self.name
        self.to_octave_code("airframes/" + self.name, octave_struct_writer)
                
class AirframeConstants(baseio.Searchable):
    def __init__(self, airframefile):
        af = genconfig.constants_config_folder + airframefile + ".xml"
        self.defines = self.parse_airframe_constants(af)
        
    def write(self):
        self.defines.to_define_h()
        self.defines.to_octave_structs()

    def search(self, searchname):
        return self._search(self.defines, searchname)
        
    def textsearch(self, searchname):
        pp = re.compile(searchstring)
        def searchme(x):
            found = pp.search(x.name)
            found.extend(x.textsearch(searchstring))
            return found

        return filter(searchme, self.defines)

    def parse_airframe_constants(self, airframe_constants_file):
        try: 
            af = ET.ElementTree().parse(airframe_constants_file)
        except IOError:
            raise IndexError ## i'm so, so sorry, but Greg needs this soon
        except expat.ExpatError as e:
            print "Error parsing airframe constants config file `" + airframe_constants_file + "':", e
            exit(1)
        dielater = False
        for k in af.getchildren():
            if k.attrib.has_key('href'):
                includename = dirname(airframe_constants_file) + "/" + k.attrib['href']
                try:
                    k.attrib['subtree'] = ET.ElementTree().parse(includename).getchildren()
                except expat.ExpatError as e:
                    print "Error parsing airframe constants config file `" + includename + "':", e
                    dielater = True
        return Constants(af)
