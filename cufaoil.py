#!/usr/bin/env python

import argparse
import csv
import json
import logging
import os.path
import pprint
import sys
import time

from prometheus_client import start_http_server, Gauge

from cufaoil import greyhound

# Your bin info updates once a week, this should be pretty damn
# long. Default to checking once a day.
SLEEP_INTERVAL = 86400


def make_args():

    parser = argparse.ArgumentParser(
        prog='cufaoil',
        description='Pull data about Greyhound bin pickups and output it in various formats'
    )
    parser.add_argument('-j', '--json',
                        action='store_true', help="JSON output")
    parser.add_argument('-s', '--state-file',
                        help="Store state in the specified file")
    parser.add_argument('-c', '--csv',
                        action='store_true', help="CSV output")
    parser.add_argument('-d', '--daemonise',
                        action='store_true', help="Run as a daemon with a prometheus interface")
    parser.add_argument('--port', default=9095,
                        type=int, help="The port for the daemon to listen on")
    parser.add_argument('--force-init', action="store_true",
                        help="Set to force emitting a metric on startup. Otherwise the service will wait for the first update")

    parser.add_argument('-u', '--username', required=True, help="Account ID")
    parser.add_argument('-p', '--password', required=True, help="PIN")

    args = parser.parse_args()
    return args


def run_daemon(greyhound_obj, port, state_file=None, force_init=False):

    # TODO - compute monthly average

    g = Gauge('cufaoil_bin_weight', 'The weight of the observed bin collection', ["bincolour"])

    last_timestamps = {}
    if force_init:
        last_timestamps = {"green": "1", "black": "1", "brown": "1"}

    if state_file and os.path.exists(state_file):
        with open(state_file) as f:
            last_timestamps = json.load(f)

            if sorted(last_timestamps.keys()) != ["black", "brown", "green"]:
                raise Exception("Loaded state file missing keys")

    start_http_server(port)
    while True:
        logging.debug("Checking for bin update")
        try:
            greyhound_data = greyhound_obj.get_data()
        except Exception as e: # TODO better handling
            logging.error("Failed to get greyhound data: {}", e.message)
            # sleep and try again
            time.sleep(SLEEP_INTERVAL)
            continue

        saw_update = False

        for colour, pickups in greyhound_data.items():
            if not pickups:
                logging.info(f"Saw no data for {colour} - skipping (new year maybe?)")
                continue

            last_timestamp = sorted(pickups.keys())[-1]

            if colour not in last_timestamps:
                logging.info(f"Initialising data bucket for {colour}")
                last_timestamps[colour] = last_timestamp
                saw_update = True
            else:
                # the most recent timestamp has changed, let's emit a metric
                if last_timestamp > last_timestamps[colour]:
                    logging.info(f"Saw an update for {colour} dated {last_timestamp}: {greyhound_data[colour][last_timestamp]}")
                    g.labels(bincolour=colour).set(greyhound_data[colour][last_timestamp])
                    last_timestamps[colour] = last_timestamp
                    saw_update = True

        if state_file and saw_update:
            with open(state_file, "w") as f:
                json.dump(last_timestamps, f)

        time.sleep(SLEEP_INTERVAL)


def main():

    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    args = make_args()

    g = greyhound.Greyhound(args.username, args.password)
    g.login()
    logging.debug("Finished login")

    if args.daemonise:
        run_daemon(g, args.port, args.state_file, args.force_init)
    else:
        greyhound_data = g.get_data()

        if args.json:
            print(json.dumps(greyhound_data))

        if args.csv:
            writer = csv.writer(sys.stdout)
            writer.writerow(["colour", "date_time", "weight"])
            for colour, entries in greyhound_data.items():
                for date, weight in entries.items():
                    writer.writerow([colour, date, weight])

        if not args.csv and not args.json:
            pprint.pprint(greyhound_data)

if __name__ == "__main__":
    main()
