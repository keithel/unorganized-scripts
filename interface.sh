#!/bin/sh
ip -o a show | awk 'BEGIN { non192Subnets=0 }; { if ($3 == "inet" && $4 != "127.0.0.1/8") { if (substr($4, 0, 10) == "192.168.1.") { print $2; printedIntf=true } else { non192Subnets++; intf=$2 } } }; END { if ($non192Subnets >= 0 && !$printedIntf) print $intf }'
