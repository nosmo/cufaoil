Cú Faoil
======
###### _[Cú Faoil](https://www.tearma.ie/q/c%C3%BA%20faoil/ga/) is the Irish word for wolfhound. Due to convention and restriction, the fada is dropped in various places_

`cufaoil.py` is a simple script for logging into and then dumping or serving historical information about bin collections from the [Greyhound bin company](https://greyhound.ie/). The `greyhound` module it uses contains all of the login/query logic and can be reused elsewhere.

`cufaoil.py` always requires a username and password to run (username in this case is what Greyhound calls an account ID, password is the PIN).

Prometheus
--------
Cú Faoil can serve bin collection data using Prometheus when invoked with the `-d` switch. The daemon will mostly sleep but once a day (default configuration) it will check for updates to the bin data. If a new bin weight is seen, a metric will be emitted. This gauge is named `cufaoil_bin_weight`:

```
# HELP cufaoil_bin_weight The weight of the observed bin collection
# TYPE cufaoil_bin_weight gauge
cufaoil_bin_weight{bincolour="green"} 13.0
cufaoil_bin_weight{bincolour="brown"} 15.5
cufaoil_bin_weight{bincolour="black"} 3.0
```
Graphing this data is the main reason I wrote this tool. It's dumb as hell and I love it. Fight me.

Dumping bin info
--------
When no other arguments are provided, a simple pretty-print of the data is emitted. `-c` and `-j` CSVify and JSONise the output respectively.

Bugs
------
Oh yeah it'll do that.
