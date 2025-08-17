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
# from libxmp.utils import file_to_dict
# from libxmp import XMPFiles, consts, XMPMeta


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

    def process_photo(self, f):
        photo_date = self.date_taken(f)
        gpx = self.gpx_path(photo_date)
        if self.verbose:
            print(f"{f}: {photo_date} -> {gpx}")
        self.update_exif(f, gpx)

    def apply(self):
        print(f"got path {self.input}")
        if os.path.isfile(self.input):
            print(f"Processing single file {self.input}")
            self.process_photo(self.input)
        else:
            input_dir = self.input
            if not os.path.isdir(input_dir):
                sys.exit(f"Directory {input_dir} was not found")

            print(f"Processing {input_dir}")
            print(f"searching for *.{self.match}")
            for f in pathlib.Path(input_dir).glob(f"*.{self.match}", case_sensitive=False):
                self.process_photo(f)


class SidecarTagger:
    def __init__(self, args):
        self.dry_run = args.dry_run
        self.verbose = args.verbose
        self.gpx = args.gpx
        self.input = args.input
        self.match = args.match

    def load_xmp(self, file):
        with open(file, "r") as content:
            return content.read()

    def apply(self):
        input_dir = self.input

        if not os.path.isdir(input_dir):
            sys.exit(f"{input_dir} was not found")

        print(f"Processing {input_dir}")
        print(f"searching for *.{self.match}")
        for f in pathlib.Path(input_dir).glob(f"*.{self.match}", case_sensitive=False):
            print(f)

            xmp = XMPMeta()
            xmp.parse_from_str(self.load_xmp(f), xmpmeta_wrap=True)
            print(xmp)
            print(xmp.get_property("http://ns.adobe.com/tiff/1.0/", "Model"))
            print(xmp.get_property("http://ns.adobe.com/exif/1.0/", "DateTimeOriginal"))
            if xmp.does_property_exist("http://ns.adobe.com/exif/1.0/", "GPSLatitude"):
                print(xmp.get_property("http://ns.adobe.com/exif/1.0/", "GPSLatitude"))
            if xmp.does_property_exist("http://ns.adobe.com/exif/1.0/", "GPSLatitude"):
                print(xmp.get_property("http://ns.adobe.com/exif/1.0/", "GPSLongitude"))
            # TODO: set_property value


class On1Tagger:
    def __init__(self, args):
        self.dry_run = args.dry_run
        self.verbose = args.verbose
        self.gpx = args.gpx
        self.input = args.input
        self.match = args.match
        self.force = args.force
        self.ext = args.ext

    def load_json(self, file):
        with open(file) as f:
            return json.load(f)

    def read_geo(self, raw):
        """
        Extract GPS position from EXIF data
        -n for numerical precision
        """
        try:
            cmd = ["exiftool", "-n", "-GPSPosition", raw]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if self.verbose:
                print(f"exif: {result.stdout}")
            if result.returncode != 0:
                print(f"erorr: {result.stderr.strip()}")
            pos = result.stdout.find(":")
            if pos > 0:
                str = result.stdout[(pos + 1) : -1].strip()
                return str.split()
        except subprocess.TimeoutExpired:
            if not self.dry_run:
                print("timeout")
        except Exception as e:
            print(f"Error: {e}")

    def deg2dms(self, dd):
        negative = dd < 0
        dd = abs(dd)
        minutes, seconds = divmod(dd * 3600, 60)
        degrees, minutes = divmod(minutes, 60)
        if negative:
            if degrees > 0:
                degrees = -degrees
            elif minutes > 0:
                minutes = -minutes
            else:
                seconds = -seconds
        return (degrees, minutes, seconds)

    def geo_format(self, h, m, s):
        return f"{h:.0f}°{m:.0f}'{s:.6f}\""

    def gps_from_raw(self, file):
        filename, file_extension = os.path.splitext(file)
        raw1 = f"{filename}.{self.ext.upper()}"
        raw2 = f"{filename}.{self.ext.lower()}"
        geo = None
        if os.path.isfile(raw1):
            geo = self.read_geo(raw1)
        elif os.path.isfile(raw2):
            geo = self.read_geo(raw2)
        else:
            print(f"couldn't find RAW {raw1} nor {raw2}")

        if geo:
            if self.verbose:
                print(f"geo: {geo}")
            h, m, s = self.deg2dms(float(geo[0]))
            lat = self.geo_format(h, m, s)
            h, m, s = self.deg2dms(float(geo[1]))
            lon = self.geo_format(h, m, s)
            dms = f"{lat} N {lon} E"
            return dms

    def write_json(self, f, data):
        json_str = json.dumps(data)
        with open(f, "w") as f:
            f.write(json_str)

    def update_gps(self, file):
        print(f"checking GPS: {file}")
        filename, file_extension = os.path.splitext(file)
        # in case user provides path directly to RAW/jpg file
        if not file_extension == ".on1":
            f = f"{filename}.on1"
            if not os.path.isfile(f):
                print(f"could not find on1 sidecar: {f}")
                return
        else:
            f = file
        # TODO: check mime type?
        json = self.load_json(f)
        if "photos" in json:
            for val in json["photos"]:
                if "metadata" in json["photos"][val]:
                    meta = json["photos"][val]["metadata"]
                    if "GPS" in meta:
                        if self.force:
                            gps = self.gps_from_raw(f)
                            print(f"updated gps {meta['GPS']} -> {gps}")
                            meta["GPS"] = gps
                            self.write_json(str(f), json)
                        else:
                            if meta['GPS'] == None:
                                print("missing GPS data in image file")
                            else:
                                print(f"[noop] {meta['GPS']}")
                    else:
                        gps = self.gps_from_raw(f)
                        print(f"[write] {gps}")
                        meta["GPS"] = gps
                        # expected
                        # "GPS":"49°39'11.043217\" N 18°7'29.517118\" E",
                        self.write_json(str(f), json)

    def apply(self):
        print(f"got path {self.input}")
        if os.path.isfile(self.input):
            print(f"Processing single file {self.input}")
            self.update_gps(self.input)
        else:
            input_dir = self.input
            if not os.path.isdir(input_dir):
                sys.exit(f"Directory {input_dir} was not found")

            print(f"Processing {input_dir}")
            print(f"searching for *.{self.match}")
            for f in pathlib.Path(input_dir).glob(
                f"*.{self.match}", case_sensitive=False
            ):
                self.update_gps(f)


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

    exif = subparsers.add_parser("exif", help="apply GPS data to RAW files")
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

    sidecar = subparsers.add_parser("sidecar", help="apply GPS data to sidecar files")
    sidecar.add_argument(
        "-g", "--gpx", type=str, help="path to GPX directory", default="gpx"
    )
    sidecar.add_argument(
        "-m", "--match", type=str, help="file extension to match", default="xmp"
    )
    sidecar.add_argument(
        "-i", "--input", type=str, help="path to photos directory", required=True
    )
    sidecar.add_argument(
        "-n", "--dry-run", help="don't execute commands", action="store_true"
    )
    sidecar.add_argument("-v", "--verbose", help="verbose output", action="store_true")

    on1 = subparsers.add_parser("on1", help="apply GPS data to on1 files")
    on1.add_argument(
        "-g", "--gpx", type=str, help="path to GPX directory", default="gpx"
    )
    on1.add_argument(
        "-m", "--match", type=str, help="file extension to match", default="on1"
    )
    on1.add_argument(
        "-i", "--input", type=str, help="path to photos directory", required=True
    )
    on1.add_argument(
        "-n", "--dry-run", help="don't execute commands", action="store_true"
    )
    on1.add_argument("-v", "--verbose", help="verbose output", action="store_true")
    on1.add_argument(
        "-f", "--force", help="overwrite gps coordinates", action="store_true"
    )
    on1.add_argument(
        "-e", "--ext", type=str, help="Image (RAW) file extension", default="nef"
    )

    return parser.parse_args()


def main():
    args = cli()
    if args.command == "import":
        gpx_import(args)
    elif args.command == "exif":
        tagger = ExifTagger(args)
        tagger.apply()
    elif args.command == "sidecar":
        tagger = SidecarTagger(args)
        tagger.apply()
    elif args.command == "on1":
        tagger = On1Tagger(args)
        tagger.apply()
    else:
        print("unknown command, use -h/--help")


if __name__ == "__main__":
    main()
