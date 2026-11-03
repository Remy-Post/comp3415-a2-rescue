#!/bin/sh
# Runs a fixed set of CLI commands against a fresh save file and prints
# every output + exit status. Used to compare behaviour before and after
# refactoring:  sh tools/cli_snapshot.sh > after.txt ; diff before.txt after.txt
DATA=$(mktemp -d)/snap.json
PY=${PYTHON:-python3}
run() { echo "\$ supplydesk $*"; $PY -m supplydesk --data "$DATA" "$@" 2>&1; echo "[exit $?]"; }
run quote --customer regular --item notebook:2
run quote --customer student --fulfillment delivery --item hoodie:2
run quote --customer regular --fulfillment delivery --item hoodie:3
run quote --customer student --item bag:2
run quote --customer student --fulfillment delivery --item hoodie:2 --item bag:1 --item notebook:1
run quote --item laptop:1
run quote --item notebook:0
run quote --item notebook:abc
run place --customer student --item hoodie:1 --item mug:2
run place --item bag:9
run place --item pen-pack:3 --fulfillment delivery
run orders
run show ORD-0002
run show ORD-0404
run cancel ORD-0001
run catalog
run place --item mug:1
run orders
