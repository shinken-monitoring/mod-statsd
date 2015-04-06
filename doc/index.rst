.. _statsd_module:

===========================
Statsd module
===========================


Overview 
=========

Shinken Statsd module is intended to send performance data metrics to a Statsd server.



Enabling Statsd module 
=============================

To use the statsd module you must declare it in your broker configuration and then restart the broker daemon.

::

      modules    	 ..., statsd


The module configuration is defined in the file: statsd.cfg.

::

	## Module:      statsd
	## Loaded by:   Broker
	# Export host and service performance data to Statsd.
	define module {
		 module_name     statsd
		 module_type     statsd_perfdata
		 
		 # Statsd server parameters
		 statsd_host		localhost
		 statsd_port		8125
		 
		 # Optionally specify a source identifier for the metric data sent to
		 # Statsd. This can help differentiate data from multiple sources for the
		 # same hosts. HostA.GRAPHITE_DATA_SOURCE.service
		 statsd_prefix		shinken
	}

It's done :)
