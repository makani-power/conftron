#!/usr/bin/env python

## This file is part of conftron.  
## 
## Copyright (C) 2011 Greg Horn <ghorn@stanford.edu>
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

from os import environ
import sys
import time
import select
import tarfile
import argparse
import lcm

select_timeout = 1.0

##################### set paths, import conftron, get genconfig #########################
# set up paths
ap_project_root = environ.get('AP_PROJECT_ROOT')
if ap_project_root == None:
    raise NameError("please set the AP_PROJECT_ROOT environment variable")
sys.path.append( ap_project_root+"/conftron/python/" )
sys.path.append( ap_project_root+"/conftron/" )

# get conftron configuration
import configuration, genconfig


############# a bunch of command line switches to thank matt for conftron ##################
parser = argparse.ArgumentParser(description='lightweight LCM logger')

parser.add_argument('-a', dest='airframe', type=str,
                    help='airframe name e.g. wing7 or m5 (for settings, currently all telemetry is the same)')
parser.add_argument('-f', dest='logfile', type=str, help='specify output logfile, if you do not include an extension then '+genconfig.logfile_extension+' is used')
parser.add_argument('-t', dest='end_time', type=float, help='specify a time to stop logging after')
parser.add_argument('-m', dest='max_log_size_MB', type=float, default=genconfig.default_max_log_size_MB, help='specify max logfile size in MB, default == '+str(genconfig.default_max_log_size_MB))
parser.add_argument('-o', dest='overwrite', action="store_true", default=False, help='overwrite logfile without asking')
parser.add_argument('-q', dest='quiet', action="store_true", default=False, help='suppress all non-error output')
parser.add_argument('-v', dest='verbose', action="store_true", default=False, help='extra output')


################# parse input arguments ######################
args = parser.parse_args()

# logfile
tm = time.localtime()
if args.logfile:
    # if it doesn't have an extension, add one
    if len(args.logfile.split('.')) < 2:
        logfile = args.logfile+genconfig.logfile_extension
else:
    # default logfile based on local date/time
    logfile = time.strftime( genconfig.logfile_name_format, time.localtime())

# print output
if not args.quiet:
    print '\n------ welcome to log-o-matic -------\n'

if args.verbose:
    print 'airframe: '+str(args.airframe)
    print 'end_time: '+str(args.end_time)
    print 'max log size: '+str(args.max_log_size_MB)+' MB'
    print 'overwrite files without asking? '+str(args.overwrite)
    print ''


###################  setup lcm  ###################
conf = configuration.Configuration(args.airframe)

lc = lcm.LCM()

# flatten the telemetry into a list of messages
telemetry = []
for tc in conf.telemetry:
    for t in tc['messages']:
        if not (t['has_key']('logger') and t['logger'] == "ignore"):
            telemetry.append(t)

# open the log
full_logfile = genconfig.logfile_directory+"/"+logfile+'_'+str(args.airframe)+genconfig.logfile_extension
if not args.quiet:
    print 'opening logfile \"'+full_logfile+'\"'

try:
    log = lcm.EventLog(full_logfile, mode="w", overwrite=args.overwrite)
except ValueError as ve:
    print ve
    exit(1)

# archive the conf folder
tar = tarfile.open( genconfig.logfile_directory+"/"+logfile+"_conf.tar.gz","w:gz")
tar.add( genconfig.config_folder, arcname=logfile+"_conf" )
tar.close()

# subscribe to all messages
def handler(channel, data):
    log.write_event( long(time.time()*1e6 + 0.5), channel, data)

subscriptions = []
for t in telemetry:
    subscriptions.append( lc.subscribe( t['channel'], handler ) )


###################  logging loop  #################
t0 = time.time()
humanreadable = lambda s:[(s%1024**i and "%.2f"%(s/1024.0**i) or str(s/1024**i))+x.strip() for i,x in enumerate(' KMGTPEZY') if s<1024**(i+1) or i==8][0]
next_message_size = 0
try:
    while True:
        if len(select.select([lc], [],[], select_timeout)[0]) != 0:
            lc.handle()

        size = log.size()
        if size > args.max_log_size_MB*1024*1024:
            exit_message = "logger reached max logfile size"
            break

        if size >= next_message_size:
            while size >= next_message_size:
                next_message_size += 2**17
            if not args.quiet:
                sys.stdout.write("\r                                                                 ")
                sys.stdout.write("\rlogging... "+str(humanreadable(log.size()))+"B ("+str(log.size())+" bytes)")
                sys.stdout.flush()

        if args.end_time:
            if time.time() > t0+args.end_time:
                exit_message = "finished logging by timeout"
                break
except KeyboardInterrupt:
    exit_message = "logger got user interrupt"
    pass
except:
    print "\n\nUnexpected error ", sys.exc_info()[0], " :("
    print "please email greg (ghorn@stanford.edu) the following information:"
    print "\n", sys.exc_info()

    log.close()
    raise

if not args.quiet:
    print "\n\n"+exit_message
    print "final log size: "+str(humanreadable(log.size()))+" ("+str(log.size())+" bytes)\n"

log.close()

for sub in subscriptions:
    lc.unsubscribe(sub)
