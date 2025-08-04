#!/usr/bin/python3
import argparse
import os
import json
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import datetime


def create_gpx_file(points, output_file):
    gpx = ET.Element("gpx", version="1.1", creator="https://github.com/deric/geotag")
    trk = ET.SubElement(gpx, "trk")
    trkseg = ET.SubElement(trk, "trkseg")

    for point in points:
        trkpt = ET.SubElement(
            trkseg, "trkpt", lat=str(point["lat"]), lon=str(point["lon"])
        )
        ET.SubElement(trkpt, "time").text = point["time"]

    # Generate pretty XML
    xml_str = xml.dom.minidom.parseString(ET.tostring(gpx)).toprettyxml(indent="  ")

    # Write the pretty XML to a file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)


def parse_json(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    points_by_date = {}

    # Extract data points
    for segment in data.get("semanticSegments", []):
        for path_point in segment.get("timelinePath", []):
            try:
                # Extract and parse data
                raw_coords = path_point["point"].replace("°", "").strip()
                coords = raw_coords.split(", ")
                lat, lon = float(coords[0]), float(coords[1])
                time = path_point["time"]

                # Extract date for grouping
                date = datetime.fromisoformat(time).date().isoformat()

                # Group by date
                if date not in points_by_date:
                    points_by_date[date] = []
                points_by_date[date].append({"lat": lat, "lon": lon, "time": time})
            except (KeyError, ValueError):
                continue  # Skip invalid points

    return points_by_date


def gpx_import(args):
    input_file = args.input
    output_dir = args.output

    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_file):
        print(f"Input file {input_file} was not found")
        return

    points_by_date = parse_json(input_file)

    for date, points in points_by_date.items():
        curr_date = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = curr_date.strftime("%d.gpx")
        dir_prefix = os.path.join(
            output_dir, curr_date.strftime("%Y"), curr_date.strftime("%m")
        )
        if not os.path.isdir(dir_prefix):
            os.makedirs(dir_prefix)
        output_file = os.path.join(dir_prefix, formatted_date)
        create_gpx_file(points, output_file)
        print(f"Created: {output_file}")


class ExifTagger:
    def __init__(self, args):
        self.dry_run = args.dry_run
        self.verbose = args.verbose
        self.gpx = args.gpx
        self.input = args.input
        self.match = args.match

    def date_taken(self, file):
        """
        Find out date when the photo was taken
        """
        try:
            cmd = ["exiftool", "-DateTimeOriginal", file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"erorr: {result.stderr.strip()}")
            pos = result.stdout.find(":")
            if pos > 0:
                str = result.stdout[(pos + 1) : -1].strip()
                # parse EXIF date
                taken = datetime.strptime(str, "%Y:%m:%d %H:%M:%S")
                return taken
        except subprocess.TimeoutExpired:
            if not self.dry_run:
                print("timeout")
        except Exception as e:
            print(f"Error: {e}")

    def gpx_path(self, curr_date):
        """
        Expand path to GPX file for given date
        """
        formatted_date = curr_date.strftime("%d.gpx")
        path = os.path.join(
            self.gpx, curr_date.strftime("%Y"), curr_date.strftime("%m"), formatted_date
        )
        if self.verbose:
            print(f"expecting GPX file: {path}")
        if not os.path.exists(path):
            print(f"Input GPX file {path} was not found")
        return path

    def to_str(self, array):
        return " ".join(str(x) for x in array)

    def update_exif(self, photo, gpx):
        """
        Update photo's GPS coordinates based on GPX file
        """
        try:
            cmd = ["exiftool", "-overwrite_original", "-geotag", gpx, str(photo)]
            if self.dry_run:
                print(f"DRY RUN: {self.to_str(cmd)}")
            else:
                print(f"cmd: {self.to_str(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                print(result.stdout)
                if result.returncode != 0:
                    print(f"erorr: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            if not self.dry_run:
                print("timeout")
        except Exception as e:
            print(f"Error: {e}")

    def apply(self):
        input_dir = self.input

        if not os.path.isdir(input_dir):
            sys.exit(f"{input_dir} was not found")

        print(f"Processing {input_dir}")
        print(f"searching for *.{self.match}")
        for f in pathlib.Path(input_dir).glob(f"*.{self.match}", case_sensitive=False):
            photo_date = self.date_taken(f)
            gpx = self.gpx_path(photo_date)
            if self.verbose:
                print(f"{f}: {photo_date} -> {gpx}")
            self.update_exif(f, gpx)


def cli():
    parser = argparse.ArgumentParser(
        description="Annotate RAW/sidecar files with GPS coordinates"
    )
    subparsers = parser.add_subparsers(dest="command")
    imp = subparsers.add_parser("import", help="import GPX data")
    imp.add_argument(
        "-i",
        "--input",
        type=str,
        help="path to timeline.json file",
        default="timeline.json",
    )
    imp.add_argument(
        "-o", "--output", type=str, help="path to GPX directory", default="gpx"
    )

    exif = subparsers.add_parser("exif", help="apply GPS data to RAW/sidecar files")
    exif.add_argument(
        "-g", "--gpx", type=str, help="path to GPX directory", default="gpx"
    )
    exif.add_argument(
        "-m", "--match", type=str, help="file extension to match", default="nef"
    )
    exif.add_argument(
        "-i", "--input", type=str, help="path to photos directory", required=True
    )
    exif.add_argument(
        "-n", "--dry-run", help="don't execute commands", action="store_true"
    )
    exif.add_argument("-v", "--verbose", help="verbose output", action="store_true")

    return parser.parse_args()


def main():
    args = cli()
    if args.command == "import":
        gpx_import(args)
    elif args.command == "exif":
        tagger = ExifTagger(args)
        tagger.apply()
    else:
        print("unknown command, use -h/--help")


if __name__ == "__main__":
    main()
