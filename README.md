
StatsD module
=====================

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


Installation
--------------------------------

   su - shinken

   shinken install statsd

Configuration
--------------------------------


   vi /etc/shinken/brokers/broker-master.cfg

   => modules statsd

   vi /etc/shinken/modules/statsd.cfg

   => host statsd


Run
--------------------------------

   su -
   /etc/init.d/shinken restart


Hosts specific configuration
--------------------------------
Use `_GRAPHITE_PRE` in the host configuration to set a prefix to use before the host name.
You can set `_GRAPHITE_PRE` in a global host template for all hosts.

For example, this prefix may be the API key of an hosted Graphite account (http://hostedgraphite.com).

Use `_GRAPHITE_GROUP` in the host configuration to set a prefix to use after the prefix and before the host name.
You can set `_GRAPHITE_GROUP` in a specific host template to allow easier filtering and organization in the metrics of a dashboard.

For example, declare this custom variable in an hostgroup or an host template.


Services specific configuration
--------------------------------
Use `_GRAPHITE_POST` in the service configuration to set a postfix to use after the service name.

