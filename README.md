# Network Tracing Tool (MTR)

Use this tool to continually trace to all your favorite network endpoints at a low level to track response times, hop counts, packet loss and set the polling count and intervals to keep a tight view into how your network is behaving.  

The tool can import static files as the host list with parameters for SLA tolerances that way you can alert when a host gets out of tolerance.  You can keep that file updated via out of band automation it rechecks it each run.

The tool is setup to dump the host results of each run into Tcollector (print to stout) which then can be used for graphing or alerted on the TSD data independently. 

There are a bunch of functions for alternatives such as logging to Mysql, pulling previous run data from Mysql and alerting on baseline variances, etc.  There are also methods to do the same in a flat files.
