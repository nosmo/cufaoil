#!/usr/bin/env python

import argparse
import csv
import datetime
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


def should_reset(sleep_window) -> bool:
    """Are we within the time window that would warrant us reinitialising the total bucket?"""

    now = datetime.datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    min_time = start_of_month - datetime.timedelta(seconds=sleep_window/2.0)
    max_time = start_of_month + datetime.timedelta(seconds=sleep_window/2.0)

    if min_time < now and now < max_time:
        return True
    else:
        return False


def run_daemon(greyhound_obj, port, state_file=None, force_init=False):

    weight_g = Gauge('cufaoil_bin_weight',
                     'The weight of the observed bin collection', ["bincolour"])
    avg_g = Gauge('cufaoil_bin_monthly',
                  'Total bin weight over the last month', ["bincolour"])

    month_totals = {}
    last_timestamps = {}

    if force_init:
        last_timestamps = {"green": "1", "black": "1", "brown": "1"}

    if state_file and os.path.exists(state_file):
        with open(state_file) as f:
            state_data = json.load(f)

            if sorted(state_data.keys()) != ["black", "brown", "green"]:
                raise Exception("Loaded state file missing keys")

            #TODO load rolling total


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
            last_timestamp = sorted(pickups.keys())[-1]

            if colour not in last_timestamps:
                logging.info(f"Initialising data bucket for {colour}")
                last_timestamps[colour] = last_timestamp
                saw_update = True
            else:
                # the most recent timestamp has changed, let's emit a metric
                if last_timestamp > last_timestamps[colour]:

                    weight = pickups[last_timestamp]

                    logging.info(f"Saw an update for {colour} dated {last_timestamp}: {weight}")
                    weight_g.labels(bincolour=colour).set(weight)
                    last_timestamps[colour] = last_timestamp
                    saw_update = True

                    if colour in month_totals:
                        month_totals[colour] += weight
                    else:
                        month_totals[colour] = weight
                    logging.info(f"Updated total for {colour} to {month_totals[colour]}")
                    avg_g.labels(bincolour=colour).set(month_totals[colour])


        if saw_update:
            if state_file:
                with open(state_file, "w") as f:
                    json.dump(last_timestamps, f)
                #TODO save total

            if should_reset(SLEEP_INTERVAL):
                logging.info("Resetting monthly totals")
                for key, val in month_totals.items():
                    month_totals[key] = 0

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
