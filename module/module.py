#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.

"""This Class is a plugin for the Shinken Broker. It is in charge
to brok information of the service/host perfdatas to a Statsd daemon
"""

import re
from re import compile
import socket

from shinken.basemodule import BaseModule
from shinken.log import logger
from shinken.misc.perfdata import PerfDatas

properties = {
    'daemons': ['broker'],
    'type': 'statsd_perfdata',
    'external': False,
}


# Called by the plugin manager to get a broker
def get_instance(mod_conf):
    logger.info("[Statsd broker] Get a Statsd data module for plugin %s", mod_conf.get_name())
    instance = Statsd_broker(mod_conf)
    return instance


# Class for the Statsd Broker
# Get broks and send them to a Carbon instance of Statsd
class Statsd_broker(BaseModule):
    def __init__(self, modconf):
        BaseModule.__init__(self, modconf)
        
        self.statsd_sock = None
        self.statsd_addr = 0
        
        self.statsd_host = getattr(modconf, 'host', 'localhost')
        self.statsd_port = int(getattr(modconf, 'port', 8125))

        # Specific filter to allow metrics to include '.' for Graphite
        self.illegal_char_metric = compile(r'[^a-zA-Z0-9_.\-]')
        
        # optional "sub-folder" in graphite to hold the data of a specific host
        self.statsd_prefix = self.illegal_char.sub('_', getattr(modconf, 'prefix', ''))

        self.host_dict = {}
        self.svc_dict = {}
        self.multival = re.compile(r'_(\d+)$')


    # Called by Broker so we can do init stuff
    def init(self):
        logger.info("[Statsd broker] Initializing the Statsd connection to %s:%d" % (str(self.statsd_host), self.statsd_port))
        try:
            self.statsd_addr = (socket.gethostbyname(self.statsd_host), self.statsd_port)
            self.statsd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)            
        except (socket.error, socket.gaierror), exp:
            logger.error('[Statsd broker] Cannot create statsd socket: %s' % str(exp))
            raise

    # For a perf_data like /=30MB;4899;4568;1234;0  /var=50MB;4899;4568;1234;0 /toto=
    # return ('/', '30'), ('/var', '50')
    def get_metric_and_value(self, perf_data):
        res = []
        metrics = PerfDatas(perf_data)

        for e in metrics:
            name = self.illegal_char_metric.sub('_', e.name)
            name = self.multival.sub(r'.\1', name)
            logger.debug("[Statsd broker] metrics: %s", e.name)

            # get metric value and its thresholds values if they exist
            name_value = {name: e.value}
            if e.warning and e.critical:
                name_value[name + '_warn'] = e.warning
                name_value[name + '_crit'] = e.critical
            # bailout if needed
            if name_value[name] == '':
                continue

            for key, value in name_value.items():
                logger.debug("[Statsd broker] metrics: %s - %s/%s", e.name, key, value)
                res.append((key, value))
        return res


    # Prepare service custom vars
    def manage_initial_service_status_brok(self, b):
        logger.debug("[Statsd broker] Initial service status : %s/%s", b.data['host_name'], b.data['service_description'])
        self.svc_dict[(b.data['host_name'], b.data['service_description'])] = b.data['customs']


    # Prepare host custom vars
    def manage_initial_host_status_brok(self, b):
        logger.debug("[Statsd broker] Initial host status : %s", b.data['host_name'])
        self.host_dict[b.data['host_name']] = b.data['customs']


    # A service check result brok has just arrived, we UPDATE data info with this
    def manage_service_check_result_brok(self, b):
        logger.debug("[Statsd broker] service check result: %s/%s : %s", b.data['host_name'], b.data['service_description'], b.data['perf_data'])
        data = b.data

        perf_data = data['perf_data']
        couples = self.get_metric_and_value(perf_data)

        # If no values, we can exit now
        if len(couples) == 0:
            return

        hname = self.illegal_char.sub('_', data['host_name'])
        if data['host_name'] in self.host_dict:
            customs_datas = self.host_dict[data['host_name']]
            if '_GRAPHITE_PRE' in customs_datas:
                hname = ".".join((customs_datas['_GRAPHITE_PRE'], hname))

        desc = self.illegal_char.sub('_', data['service_description'])
        if (data['host_name'], data['service_description']) in self.svc_dict:
            customs_datas = self.svc_dict[(data['host_name'], data['service_description'])]
            if '_GRAPHITE_POST' in customs_datas:
                desc = ".".join((desc, customs_datas['_GRAPHITE_POST']))
        else:
            # Not received initial service status
            return

        if self.statsd_prefix:
            path = '.'.join((hname, self.statsd_prefix, desc))
        else:
            path = '.'.join((hname, desc))

        # Send metrics values to Statsd
        for (metric, value) in couples:
            # Send metrics as gauges ... probably should be refined to allow counts, sets and delays ?
            packet = '%s.%s:%d|g' % (path, metric, value)
            try:
                self.statsd_sock.sendto(packet, self.statsd_addr)
                logger.debug('[Statsd broker] sent: %s', packet)
            except IOError, exp:
                logger.error('[Statsd broker] Cannot send to statsd socket: %s' % str(exp))
                pass



    # A host check result brok has just arrived, we UPDATE data info with this
    def manage_host_check_result_brok(self, b):
        logger.debug("[Statsd broker] host check result: %s", b.data['host_name'])
        data = b.data

        perf_data = data['perf_data']
        couples = self.get_metric_and_value(perf_data)

        # If no values, we can exit now
        if len(couples) == 0:
            return

        hname = self.illegal_char.sub('_', data['host_name'])
        if data['host_name'] in self.host_dict:
            customs_datas = self.host_dict[data['host_name']]
            if '_GRAPHITE_PRE' in customs_datas:
                hname = ".".join((customs_datas['_GRAPHITE_PRE'], hname))
        else:
            # Not received initial host status
            return
        
        if self.statsd_prefix:
            path = '.'.join((hname, self.statsd_prefix))
        else:
            path = hname

        # Send metrics values to Statsd
        for (metric, value) in couples:
            # Send metrics as gauges ... probably should be refined to allow counts, sets and delays ?
            packet = '%s.%s:%d|g' % (path, metric, value)
            try:
                self.statsd_sock.sendto(packet, self.statsd_addr)
                logger.debug('[Statsd broker] sent: %s', packet)
            except IOError, exp:
                logger.error('[Statsd broker] Cannot send to statsd socket: %s' % str(exp))
                pass

