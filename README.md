# geotag

This tool might help to annotate photos (RAW) based on GPX data.

## Usage

 1. Download GPS log. e.g from Google location timeline (note the data is no longer part of Google takeout, it's availble only on your device)
   - Android: Settings > Location > Services > Timeline > Export
 2. Convert data to gpx:
```
./src/geotag/geotag.py import -i timeline.json -o gpx
```
This should convert Google Timeline into a tree structure `gpx/{year}/{month}/{day}.gpx`. Try using e.g. [GPXSee](https://www.gpxsee.org) to inspect the data.
 
 3. Update GPS EXIF data based on GPX data:
```
./src/geotag/geotag.py exif -i ~/photos/foo
```

see `-h` for more details
```
$ ./src/geotag/geotag.py -h
usage: geotag.py [-h] {import,exif,sidecar,on1} ...

Annotate RAW/sidecar files with GPS coordinates

positional arguments:
  {import,exif,sidecar,on1}
    import              import GPX data
    exif                apply GPS data to RAW files
    sidecar             apply GPS data to sidecar files
    on1                 apply GPS data to on1 files

optional arguments:
  -h, --help            show this help message and exit
```

## Development

Note this tool is currently experimental, alpha state.

 - [x] exif sync
 - [ ] sidecar (not fully implemented)
 - [x] `*.on1` sync to on1 sidecar files
 
Use [mise](https://mise.jdx.dev/getting-started.html) to install dev dependencies. Then from project dir:
```
mise install
```

## requirements

 - Python 3.12
 - `exiftool`
 - `exempi`

### MacOS
```
brew install exiftool
brew install exempi
```
