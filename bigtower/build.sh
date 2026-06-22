#!/bin/sh
pyinstaller main.py --onefile
DIR="dist/bigtower"
rm -rf "$DIR"
mkdir "$DIR"
cp -r dist/main assets/ "$DIR"
cd "$DIR"
mv main bigtower
zip --recurse-paths bigtower.zip assets bigtower

