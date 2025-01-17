#!/usr/bin/env python

import argparse
import collections
import copy
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
                        help=("Set to force emitting a metric on startup. "
                              "Otherwise the service will wait for the first update"))

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

    return bool(min_time < now and now < max_time)

class Statefile:

    def __init__(self, filename):
        self.filename = filename

        self.state = {}
        self.month_totals = collections.defaultdict(int)

        self.reload()

    def __setitem__(self, key, val):
        self.state[key] = val

        self.month_totals[key] += val

    def __getitem__(self, key):
        return self.state[key]

    def total(self, colour):
        return self.month_totals[colour]

    def reset_totals(self):
        """Reset month totals to whatever the current weight is set to"""
        #TODO this is the wrong approach

        for colour, weight in self.state.items():
            self.month_totals[colour] = weight

    def reload(self):
        if os.path.exists(self.filename):
            with open(self.filename) as f:
                for key, val in json.load(f).items():
                    if key == "month_totals":
                        self.month_totals = val
                    else:
                        self.state[key] = val
                self._validate()

        # if file doesn't exist, default to empty state dict

    def save(self):
        with open(self.filename, "w") as f:
            output_dict = copy.copy(self.state)
            output_dict["month_totals"] = self.month_totals
            json.dump(output_dict, f)

    def _validate(self) -> bool:
        if sorted(self.state.keys()) != ["black", "brown", "green", "month_total"]:
            raise Exception("Loaded state file missing keys")

        return True

def run_daemon(greyhound_obj, port, state_file_path=None, force_init=False):

    weight_g = Gauge('cufaoil_bin_weight',
                     'The weight of the observed bin collection', ["bincolour"])
    avg_g = Gauge('cufaoil_bin_monthly',
                  'Total bin weight over the last month', ["bincolour"])

    last_timestamps = {}

    if force_init:
        last_timestamps = {"green": "1", "black": "1", "brown": "1"}

    state_file = None
    if state_file_path:
        state_file = Statefile(state_file_path)

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

                    weight = pickups[last_timestamp]

                    logging.info(f"Saw an update for {colour} dated {last_timestamp}: {weight}")
                    weight_g.labels(bincolour=colour).set(weight)
                    last_timestamps[colour] = last_timestamp
                    saw_update = True

                    if state_file:
                        state_file[colour] = weight
                        colour_total = state_file.total(colour)
                        logging.info(f"Updated total for {colour} to {colour_total}")
                        avg_g.labels(bincolour=colour).set(colour_total)

        if saw_update:
            if state_file:
                state_file.save()

            if should_reset(SLEEP_INTERVAL):
                logging.info("Resetting monthly totals")
                state_file.reset_totals()

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
