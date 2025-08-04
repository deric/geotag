#!/usr/bin/python3
import argparse
import os
import json
import pathlib
import rdflib
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
        formatted_date = curr_date.strftime("%d")
        dir_prefix = os.path.join(
            output_dir, curr_date.strftime("%Y"), curr_date.strftime("%m")
        )
        if not os.path.isdir(dir_prefix):
            os.makedirs(dir_prefix)
        output_file = os.path.join(dir_prefix, f"{formatted_date}.gpx")
        create_gpx_file(points, output_file)
        print(f"Created: {output_file}")


def apply(args):
    input_dir = args.input

    if not os.path.isdir(input_dir):
        sys.exit(f"{input_dir} was not found")

    print(f"Processing {input_dir}")
    print(f"searching for *.{args.match}")
    for f in pathlib.Path(input_dir).glob(f"*.{args.match}"):
        print(f)
        g = Graph()
        g.parse(f)
        print(f"Graph g has {len(g)} statements.")
        print(g.serialize(format="turtle"))


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
    imp.add_argument("--dry-run", help="just pretend", action="store_true")

    apply = subparsers.add_parser("apply", help="apply GPS data to RAW/sidecar files")
    apply.add_argument(
        "-g", "--gpx", type=str, help="path to GPX directory", default="gpx"
    )
    apply.add_argument(
        "-m", "--match", type=str, help="file extension to match", default="xmp"
    )
    apply.add_argument(
        "-i", "--input", type=str, help="path to photos directory", required=True
    )

    return parser.parse_args()


def main():
    args = cli()
    if args.command == "import":
        gpx_import(args)
    elif args.command == "apply":
        apply(args)
    else:
        print("unknown command, use -h/--help")


if __name__ == "__main__":
    main()
