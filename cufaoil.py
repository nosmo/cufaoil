#!/usr/bin/env python

import argparse
import csv
import json
import pprint
import sys

import greyhound

def make_args():

    parser = argparse.ArgumentParser(
        prog='cufaoil',
        description='Pull data about Greyhound bin pickups and output it in various formats'
    )
    parser.add_argument('-j', '--json',
                        action='store_true', help="JSON output")
    parser.add_argument('-c', '--csv',
                        action='store_true', help="CSV output")
    parser.add_argument('-u', '--username', required=True, help="Account ID")
    parser.add_argument('-p', '--password', required=True, help="PIN")

    args = parser.parse_args()
    return args

def main():

    args = make_args()

    g = greyhound.Greyhound(args.username, args.password)
    g.login()

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
