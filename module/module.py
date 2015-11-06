#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    Frederic Mohier, frederic.mohier@gmail.com
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
    'external': True,
}


# Called by the plugin manager to get a broker
def get_instance(mod_conf):
    logger.info("[Statsd] Get a Statsd data module for plugin %s", mod_conf.get_name())
    instance = Statsd_broker(mod_conf)
    return instance


# Class for the Statsd Broker
# Get broks and send them to a Carbon instance of Statsd
class Statsd_broker(BaseModule):
    def __init__(self, modconf):
        BaseModule.__init__(self, modconf)

        self.hosts_cache = {}
        self.services_cache = {}

        # Separate perfdata multiple values
        self.multival = compile(r'_(\d+)$')

        # Specific filter to allow metrics to include '.' for Graphite
        self.illegal_char_metric = compile(r'[^a-zA-Z0-9_.\-]')

        self.host = getattr(modconf, 'host', 'localhost')
        self.port = int(getattr(modconf, 'port', '8125'))
        logger.info("[Statsd] Configuration - host/port: %s:%d", self.host, self.port)

        # service name to use for host check
        self.hostcheck = getattr(modconf, 'hostcheck', '')

        # optional "sub-folder" in graphite to signal shinken data source
        self.graphite_data_source = self.illegal_char_metric.sub('_', getattr(modconf, 'graphite_data_source', ''))
        logger.info("[Statsd] Configuration - Graphite data source: %s", self.graphite_data_source)

        # optional perfdatas to be filtered
        self.filtered_metrics = {}
        filters = getattr(modconf, 'filter', [])
        if isinstance(filters, str) or isinstance(filters, unicode):
            filters = [filters]
        for filter in filters:
            try:
                filtered_service, filtered_metric = filter.split(':')
                self.filtered_metrics[filtered_service] = []
                if filtered_metric:
                    self.filtered_metrics[filtered_service] = filtered_metric.split(',')
            except:
                logger.warning("[Statsd] Configuration - ignoring badly declared filtered metric: %s", filter)
                pass

        for service in self.filtered_metrics:
            logger.info("[Statsd] Configuration - Filtered metrics: %s - %s", service, self.filtered_metrics[service])

        # optional perfdatas types: timers
        self.timers = {}
        filters = getattr(modconf, 'timer', [])
        if isinstance(filters, str) or isinstance(filters, unicode):
            filters = [filters]
        for filter in filters:
            try:
                filtered_service, filtered_metric = filter.split(':')
                self.timers[filtered_service] = []
                if filtered_metric:
                    self.timers[filtered_service] = filtered_metric.split(',')
            except:
                logger.warning("[Statsd] Configuration - ignoring badly declared filter: %s", filter)
                pass

        for service in self.timers:
            logger.info("[Statsd] Configuration - Timer metrics: %s - %s", service, self.timers[service])

        # optional perfdatas types: counters
        self.counters = {}
        filters = getattr(modconf, 'counter', [])
        if isinstance(filters, str) or isinstance(filters, unicode):
            filters = [filters]
        for filter in filters:
            try:
                filtered_service, filtered_metric = filter.split(':')
                self.counters[filtered_service] = []
                if filtered_metric:
                    self.counters[filtered_service] = filtered_metric.split(',')
            except:
                logger.warning("[Statsd] Configuration - ignoring badly declared filter: %s", filter)
                pass

        for service in self.counters:
            logger.info("[Statsd] Configuration - Counter metrics: %s - %s", service, self.counters[service])

        # optional perfdatas types: meters
        self.meters = {}
        filters = getattr(modconf, 'meter', [])
        if isinstance(filters, str) or isinstance(filters, unicode):
            filters = [filters]
        for filter in filters:
            try:
                filtered_service, filtered_metric = filter.split(':')
                self.meters[filtered_service] = []
                if filtered_metric:
                    self.meters[filtered_service] = filtered_metric.split(',')
            except:
                logger.warning("[Statsd] Configuration - ignoring badly declared filter: %s", filter)
                pass

        for service in self.meters:
            logger.info("[Statsd] Configuration - Meter metrics: %s - %s", service, self.meters[service])

        # Send warning, critical, min, max
        self.send_warning = bool(getattr(modconf, 'send_warning', False))
        logger.info("[Statsd] Configuration - send warning metrics: %d", self.send_warning)
        self.send_critical = bool(getattr(modconf, 'send_critical', False))
        logger.info("[Statsd] Configuration - send critical metrics: %d", self.send_critical)
        self.send_min = bool(getattr(modconf, 'send_min', False))
        logger.info("[Statsd] Configuration - send min metrics: %d", self.send_min)
        self.send_max = bool(getattr(modconf, 'send_max', False))
        logger.info("[Statsd] Configuration - send max metrics: %d", self.send_max)

    # Called by Broker so we can do init stuff
    def init(self):
        logger.info("[Statsd] initializing connection to %s:%d ...", str(self.host), self.port)
        try:
            self.statsd_addr = (socket.gethostbyname(self.host), self.port)
            self.statsd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except (socket.error, socket.gaierror), exp:
            logger.error('[Statsd] Cannot create statsd socket: %s' % str(exp))
            raise

    def get_metric_and_value(self, service, perf_data):
        result = []
        metrics = PerfDatas(perf_data)

        for e in metrics:
            logger.debug("[Statsd] service: %s, metric: %s", e.name)
            if service in self.filtered_metrics:
                if e.name in self.filtered_metrics[service]:
                    logger.debug("[Statsd] Ignore metric '%s' for filtered service: %s", e.name, service)
                    continue

            name = self.illegal_char_metric.sub('_', e.name)
            name = self.multival.sub(r'.\1', name)

            # get metric value and its thresholds values if they exist
            name_value = {name: e.value}
            # bailout if no value
            if name_value[name] == '':
                continue

            # Get or ignore extra values depending upon module configuration
            if e.warning and self.send_warning:
                name_value[name + '_warn'] = e.warning

            if e.critical and self.send_critical:
                name_value[name + '_crit'] = e.critical

            if e.min and self.send_min:
                name_value[name + '_min'] = e.min

            if e.max and self.send_max:
                name_value[name + '_max'] = e.max

            for key, value in name_value.items():
                result.append((key, value))

        return result

    # Prepare service cache
    def manage_initial_service_status_brok(self, b):
        host_name = b.data['host_name']
        service_description = b.data['service_description']
        service_id = host_name+"/"+service_description
        logger.info("[Statsd] got initial service status: %s", service_id)

        if host_name not in self.hosts_cache:
            logger.error("[Statsd] initial service status, host is unknown: %s.", service_id)
            return

        self.services_cache[service_id] = {}
        if '_GRAPHITE_POST' in b.data['customs']:
            self.services_cache[service_id]['_GRAPHITE_POST'] = b.data['customs']['_GRAPHITE_POST']

        logger.debug("[Statsd] initial service status received: %s", service_id)

    # Prepare host cache
    def manage_initial_host_status_brok(self, b):
        host_name = b.data['host_name']
        logger.info("[Statsd] got initial host status: %s", host_name)

        self.hosts_cache[host_name] = {}
        if '_GRAPHITE_PRE' in b.data['customs']:
            self.hosts_cache[host_name]['_GRAPHITE_PRE'] = b.data['customs']['_GRAPHITE_PRE']
        if '_GRAPHITE_GROUP' in b.data['customs']:
            self.hosts_cache[host_name]['_GRAPHITE_GROUP'] = b.data['customs']['_GRAPHITE_GROUP']

        logger.debug("[Statsd] initial host status received: %s", host_name)

    # A service check result brok has just arrived ...
    def manage_service_check_result_brok(self, b):
        host_name = b.data['host_name']
        service_description = b.data['service_description']
        service_id = host_name+"/"+service_description
        logger.debug("[Statsd] service check result: %s", service_id)

        # If host and service initial status brokes have not been received, ignore ...
        if host_name not in self.hosts_cache:
            logger.warning("[Statsd] received service check result for an unknown host: %s", service_id)
            return
        if service_id not in self.services_cache:
            logger.warning("[Statsd] received service check result for an unknown service: %s", service_id)
            return

        if service_description in self.filtered_metrics:
            if len(self.filtered_metrics[service_description]) == 0:
                logger.debug("[Statsd] Ignore service '%s' metrics", service_description)
                return

        # Decode received metrics
        couples = self.get_metric_and_value(service_description, b.data['perf_data'])

        # If no values, we can exit now
        if len(couples) == 0:
            logger.debug("[Statsd] no metrics to send ...")
            return

        # Custom hosts variables
        hname = self.illegal_char.sub('_', host_name)
        if '_GRAPHITE_GROUP' in self.hosts_cache[host_name]:
            hname = ".".join((self.hosts_cache[host_name]['_GRAPHITE_GROUP'], hname))

        if '_GRAPHITE_PRE' in self.hosts_cache[host_name]:
            hname = ".".join((self.hosts_cache[host_name]['_GRAPHITE_PRE'], hname))

        # Custom services variables
        desc = self.illegal_char.sub('_', service_description)
        if '_GRAPHITE_POST' in self.services_cache[service_id]:
            desc = ".".join((desc, self.services_cache[service_id]['_GRAPHITE_POST']))

        # Graphite data source
        if self.graphite_data_source:
            path = '.'.join((hname, self.graphite_data_source, desc))
        else:
            path = '.'.join((hname, desc))

        # Send metrics values to Statsd
        for (metric, value) in couples:
            # Metric type
            metric_type = 'g'
            if service_description in self.timers:
                if metric in self.timers[service_description]:
                    metric_type = 'ms'
            elif service_description in self.counters:
                if metric in self.counters[service_description]:
                    metric_type = 'c'
            elif service_description in self.meters:
                if metric in self.meters[service_description]:
                    metric_type = 'm'

            # Send metrics as gauges ... probably should be refined to allow counts, sets and delays ?
            packet = '%s.%s:%d|%s' % (path, metric, value, metric_type)
            try:
                self.statsd_sock.sendto(packet, self.statsd_addr)
                logger.debug('[Statsd] sent: %s', packet)
            except IOError, exp:
                logger.error('[Statsd] Cannot send to statsd socket: %s' % str(exp))
                pass

    # A host check result brok has just arrived, we UPDATE data info with this
    def manage_host_check_result_brok(self, b):
        host_name = b.data['host_name']
        logger.debug("[Statsd] host check result: %s", host_name)

        # If host initial status brok has not been received, ignore ...
        if host_name not in self.hosts_cache:
            logger.warning("[Statsd] received service check result for an unknown host: %s", host_name)
            return

        # Decode received metrics
        couples = self.get_metric_and_value('host_check', b.data['perf_data'])

        # If no values, we can exit now
        if len(couples) == 0:
            logger.debug("[Statsd] no metrics to send ...")
            return

        # Custom hosts variables
        hname = self.illegal_char.sub('_', host_name)
        if '_GRAPHITE_GROUP' in self.hosts_cache[host_name]:
            hname = ".".join((self.hosts_cache[host_name]['_GRAPHITE_GROUP'], hname))

        if '_GRAPHITE_PRE' in self.hosts_cache[host_name]:
            hname = ".".join((self.hosts_cache[host_name]['_GRAPHITE_PRE'], hname))

        if self.hostcheck:
            hname = '.'.join((hname, self.hostcheck))

        # Graphite data source
        if self.graphite_data_source:
            path = '.'.join((hname, self.graphite_data_source))
        else:
            path = hname

        # Send metrics values to Statsd
        for (metric, value) in couples:
            # Send metrics as gauges ... probably should be refined to allow counts, sets and delays ?
            packet = '%s.%s:%d|g' % (path, metric, value)
            try:
                self.statsd_sock.sendto(packet, self.statsd_addr)
                logger.debug('[Statsd] sent: %s', packet)
            except IOError, exp:
                logger.error('[Statsd] Cannot send to statsd socket: %s' % str(exp))
                pass

    def main(self):
        self.set_proctitle(self.name)
        self.set_exit_handler()
        while not self.interrupted:
            l = self.to_q.get()
            for b in l:
                b.prepare()
                self.manage_brok(b)
