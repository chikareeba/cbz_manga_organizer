echo "Installing required Python packages..."

pip install pillow tkinterdnd2

echo ""
echo "Done!"

# Get the folder this script is in
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Run the Python file in the same folder
python "$SCRIPT_DIR/cbz_manga_organizer.py"