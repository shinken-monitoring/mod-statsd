.. _statsd_module:

===========================
Statsd metrics
===========================

Shinken module for sending data to a StatsD server

This version is a rewriting of the previous StatsD module which allows:

   - run as an external broker module
   - do not manage metrics until initial hosts/services status are received (avoid to miss prefixes)
   - filter metrics warning and critical thresholds
   - filter metrics min and max values
   - configure filtered service/metrics (avoid sending all metrics to StatsD)
   - configure metrics types (counter, timer, meter)
   - manage host _GRAPHITE_PRE and service _GRAPHITE_POST to build metric id
   - manage host _GRAPHITE_GROUP as an extra hierarchy level for metrics (easier usage in metrics dashboard)


Hosts specific configuration
--------------------------------
The `_GRAPHITE_PRE` and `_GRAPHITE_GROUP` defined in the hosts configuration are used to prefix the requested metrics.


Services specific configuration
--------------------------------
The `_GRAPHITE_POST` defined in the services configuration are used to postfix the requested metrics.

Requirements
-------------------------

None.


Enabling module
-------------------------

To use the `statsd` module you must declare it in your main broker configuration.

::

      modules    	 ..., statsd


Configuring module
-------------------------

The module configuration is defined in the file: `statsd.cfg`.

Default configuration file is as is :
::

   ## Module:      statsd
   ## Loaded by:   Broker
   # Export host and service performance data to Statsd.
   define module {
      module_name     statsd
      module_type     statsd_perfdata

      # Statsd server parameters
      # default to localhost:8125
      #host            localhost
      #port            8125

      # Optionally specify a source identifier for the metric data sent to Graphite.
      # This can help differentiate data from multiple sources for the same hosts.
      #
      # Result is:
      # host.GRAPHITE_DATA_SOURCE.service.metric
      # instead of:
      # host.service.metric
      #
      # Note: You must set the same value in this module and in the Graphite UI module configuration.
      #
      # default: the variable is unset
      #graphite_data_source shinken

      # Optionally specify a service description for host check metrics
      #
      # Graphite stores host check metrics in the host directory whereas services
      # are stored in host.service directory. Host check metrics may be stored in their own
      # directory if it is specified.
      #
      # default: no sub directory, host checks metrics are stored in the host directory
      #hostcheck           __HOST__

      # Optionally specify filtered metrics
      # Filtered metrics will not be sent to Carbon/Graphite
      #
      # Declare a filter parameter for each service to be filtered:
      # filter    service_description:metrics
      #
      # metrics is a comma separated list of the metrics to be filtered
      # If metrics is an empty list, no metrics will be sent for the service
      # default: no filtered metrics
      #filter           cpu:1m,5m
      #filter           mem:3z
      #filter           disk:

      # Optionally specify metrics type
      # Allows to specify the StatsD metrics type (gauge, counter, timer, meter)
      # - gauge: A gauge is an instantaneous measurement of a value, like the gas gauge in a car.
      #   It differs from a counter by being calculated at the client rather than the server.
      # - counter: A counter is a gauge calculated at the server. Metrics sent by the client
      #   increment or decrement the value of the gauge rather than giving its current value.
      # - timer: A timer is a measure of the number of milliseconds elapsed between a start and
      #   end time
      # - meter: A meter measures the rate of events over time, calculated at the server.
      #   They may also be thought of as increment-only counters.
      #
      # Declare a type parameter for each service/perfdata:
      # timer    service_description:metrics
      # metrics is a comma separated list of the concerned metrics
      # If metrics is an empty list, all the metrics for the service are considered to be of the type
      #
      # default: metrics are gauges
      #timer Http:time
      #timer Https:time
      #timer __HOST__:rta

      # Optionally specify extra metrics
      # warning, critical, min and max information for the metrics are not often necessary
      # in Graphite
      # You may specify which one are to be sent or not
      # Default is to send only the metric value
      #send_warning      False
      #send_critical     False
      #send_min          False
      #send_max          False
   }
